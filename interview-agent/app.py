"""InterviewAI Streamlit application."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from agents.evaluation_agent import EvaluationAgent
from agents.question_agent import QuestionGenerationAgent
from agents.resume_agent import ResumeAnalyzerAgent
from agents.roadmap_agent import RoadmapAgent
from utils.pdf_reader import extract_text_from_pdf


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "sqlite.db"

resume_agent = ResumeAnalyzerAgent()
question_agent = QuestionGenerationAgent()
evaluation_agent = EvaluationAgent()
roadmap_agent = RoadmapAgent()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS interviews(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                company_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                focus_areas TEXT,
                ats_score INTEGER,
                score REAL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS resume_analyses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL UNIQUE,
                summary TEXT,
                skills TEXT NOT NULL,
                skill_categories TEXT NOT NULL,
                education TEXT NOT NULL,
                projects TEXT NOT NULL,
                experience TEXT NOT NULL,
                FOREIGN KEY(interview_id) REFERENCES interviews(id)
            );

            CREATE TABLE IF NOT EXISTS questions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                expected_points TEXT NOT NULL,
                score INTEGER,
                feedback TEXT,
                FOREIGN KEY(interview_id) REFERENCES interviews(id)
            );

            CREATE TABLE IF NOT EXISTS roadmaps(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL UNIQUE,
                weak_topics TEXT NOT NULL,
                study_plan TEXT NOT NULL,
                FOREIGN KEY(interview_id) REFERENCES interviews(id)
            );
            """
        )


def json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def create_interview(
    name: str,
    email: str,
    company: str,
    difficulty: str,
    focus_areas: str,
    resume_data: dict[str, Any],
    questions: list[dict[str, Any]],
) -> int:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO users(name, email)
            VALUES (?, ?)
            ON CONFLICT(email) DO UPDATE SET name = excluded.name
            """,
            (name, email.lower()),
        )
        user_id = connection.execute(
            "SELECT id FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()["id"]
        cursor = connection.execute(
            """
            INSERT INTO interviews(
                user_id, date, company_type, difficulty, focus_areas, ats_score, status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'in_progress')
            """,
            (
                user_id,
                datetime.now().isoformat(timespec="seconds"),
                company,
                difficulty,
                focus_areas,
                resume_data["ats_score"],
            ),
        )
        interview_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO resume_analyses(
                interview_id, summary, skills, skill_categories, education, projects, experience
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interview_id,
                resume_data["summary"],
                json.dumps(resume_data["skills"]),
                json.dumps(resume_data["skill_categories"]),
                json.dumps(resume_data["education"]),
                json.dumps(resume_data["projects"]),
                json.dumps(resume_data["experience"]),
            ),
        )
        connection.executemany(
            """
            INSERT INTO questions(
                interview_id, question, category, difficulty, expected_points
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    interview_id,
                    question["question"],
                    question["category"],
                    question["difficulty"],
                    json.dumps(question["expected_points"]),
                )
                for question in questions
            ],
        )
    return interview_id


def list_interviews(status: str | None = None) -> list[dict[str, Any]]:
    condition = "WHERE i.status = ?" if status else ""
    parameters = (status,) if status else ()
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                i.id,
                i.date,
                i.company_type,
                i.difficulty,
                i.ats_score,
                i.score,
                i.status,
                u.name,
                u.email,
                COUNT(q.id) AS question_count,
                SUM(CASE WHEN q.answer IS NOT NULL THEN 1 ELSE 0 END) AS answered_count
            FROM interviews i
            JOIN users u ON u.id = i.user_id
            LEFT JOIN questions q ON q.interview_id = i.id
            {condition}
            GROUP BY i.id
            ORDER BY i.date DESC
            """,
            parameters,
        ).fetchall()
    return rows_to_dicts(rows)


def get_interview(interview_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT i.*, u.name, u.email
            FROM interviews i
            JOIN users u ON u.id = i.user_id
            WHERE i.id = ?
            """,
            (interview_id,),
        ).fetchone()
    return dict(row) if row else None


def get_questions(interview_id: int) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM questions WHERE interview_id = ? ORDER BY id",
            (interview_id,),
        ).fetchall()
    return rows_to_dicts(rows)


def get_resume_analysis(interview_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM resume_analyses WHERE interview_id = ?",
            (interview_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    for key in ["skills", "skill_categories", "education", "projects", "experience"]:
        result[key] = json_load(result[key], [] if key != "skill_categories" else {})
    return result


def save_answer(question_id: int, answer: str, evaluation: dict[str, Any]) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE questions
            SET answer = ?, score = ?, feedback = ?
            WHERE id = ?
            """,
            (answer, evaluation["score"], json.dumps(evaluation), question_id),
        )


def get_roadmap(interview_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT study_plan FROM roadmaps WHERE interview_id = ?",
            (interview_id,),
        ).fetchone()
    return json_load(row["study_plan"], {}) if row else None


def complete_interview(interview_id: int) -> tuple[float, dict[str, Any]]:
    questions = get_questions(interview_id)
    evaluations = [
        {"category": question["category"], "score": question["score"]}
        for question in questions
        if question["score"] is not None
    ]
    if not evaluations:
        raise ValueError("Answer at least one question before completing the interview.")

    score = round(sum(item["score"] for item in evaluations) / len(evaluations), 1)
    roadmap = roadmap_agent.create(evaluations)
    with connect() as connection:
        connection.execute(
            "UPDATE interviews SET score = ?, status = 'completed' WHERE id = ?",
            (score, interview_id),
        )
        connection.execute(
            """
            INSERT INTO roadmaps(interview_id, weak_topics, study_plan)
            VALUES (?, ?, ?)
            ON CONFLICT(interview_id)
            DO UPDATE SET weak_topics = excluded.weak_topics, study_plan = excluded.study_plan
            """,
            (
                interview_id,
                json.dumps(roadmap.get("weak_topics", [])),
                json.dumps(roadmap),
            ),
        )
    return score, roadmap


def dashboard_data() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with connect() as connection:
        stats_row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_interviews,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_interviews,
                ROUND(AVG(CASE WHEN status = 'completed' THEN score END), 1) AS average_score,
                MAX(ats_score) AS best_ats_score
            FROM interviews
            """
        ).fetchone()
        category_rows = connection.execute(
            """
            SELECT category, ROUND(AVG(score), 1) AS score
            FROM questions
            WHERE score IS NOT NULL
            GROUP BY category
            ORDER BY score DESC
            """
        ).fetchall()
    return dict(stats_row), rows_to_dicts(category_rows)


def request_page(page: str) -> None:
    st.session_state.requested_page = page
    st.rerun()


def render_tags(values: list[str]) -> None:
    if not values:
        st.caption("No items detected.")
        return
    tags = "".join(f"<span class='tag'>{value}</span>" for value in values)
    st.markdown(tags, unsafe_allow_html=True)


def render_evaluation(evaluation: dict[str, Any]) -> None:
    score = int(evaluation.get("score", 0))
    st.markdown(f"### Evaluation: {score}/10")
    columns = st.columns(4)
    metrics = [
        ("Accuracy", evaluation.get("technical_accuracy", 0)),
        ("Completeness", evaluation.get("completeness", 0)),
        ("Communication", evaluation.get("communication", 0)),
        ("Confidence", evaluation.get("confidence", 0)),
    ]
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, f"{value}/10")

    st.info(evaluation.get("feedback", "No feedback available."))
    left, right = st.columns(2)
    with left:
        st.markdown("**Strengths**")
        for item in evaluation.get("strengths", []):
            st.markdown(f"- {item}")
    with right:
        st.markdown("**Improve next**")
        for item in evaluation.get("weaknesses", []):
            st.markdown(f"- {item}")
    with st.expander("Actionable suggestions"):
        for item in evaluation.get("improvement_suggestions", []):
            st.markdown(f"- {item}")


def render_dashboard() -> None:
    st.title("Performance Dashboard")
    st.caption("Track interview readiness, resume quality, and topic-level progress.")
    stats, category_scores = dashboard_data()
    interviews = list_interviews()

    columns = st.columns(4)
    columns[0].metric("Total interviews", stats["total_interviews"] or 0)
    columns[1].metric("Completed", stats["completed_interviews"] or 0)
    columns[2].metric(
        "Average score",
        f"{stats['average_score']}/10" if stats["average_score"] is not None else "No score",
    )
    columns[3].metric(
        "Best ATS score",
        f"{stats['best_ats_score']}/100" if stats["best_ats_score"] is not None else "No resume",
    )

    st.markdown("### Topic performance")
    if category_scores:
        frame = pd.DataFrame(category_scores).set_index("category")
        st.bar_chart(frame, horizontal=True)
    else:
        st.info("Complete a mock interview to unlock topic-level analytics.")

    st.markdown("### Recent interviews")
    if not interviews:
        st.info("No interviews yet. Start by analyzing a resume.")
        if st.button("Create first interview", type="primary"):
            request_page("New Interview")
        return

    display = pd.DataFrame(interviews)[
        ["date", "name", "company_type", "difficulty", "ats_score", "score", "status"]
    ]
    display.columns = ["Date", "Candidate", "Company", "Difficulty", "ATS", "Score", "Status"]
    display["Date"] = pd.to_datetime(display["Date"]).dt.strftime("%d %b %Y, %I:%M %p")
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_new_interview() -> None:
    st.title("Create a Personalized Interview")
    st.caption(
        "The Resume Analyzer and Question Generation agents will prepare a focused mock interview."
    )

    with st.form("new_interview_form"):
        candidate_left, candidate_right = st.columns(2)
        with candidate_left:
            name = st.text_input("Candidate name", placeholder="Payal Sobhani")
        with candidate_right:
            email = st.text_input("Email", placeholder="payal@example.com")

        uploaded_resume = st.file_uploader("Upload resume PDF", type=["pdf"])

        left, middle, right = st.columns(3)
        with left:
            company = st.selectbox(
                "Company style",
                ["General", "TCS", "Infosys", "Accenture", "Google", "Amazon", "Microsoft"],
            )
        with middle:
            difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
        with right:
            question_count = st.slider("Number of questions", 5, 10, 7)

        focus_areas = st.text_input(
            "Focus areas",
            placeholder="SQL, Python OOP, system design",
            help="Optional comma-separated topics.",
        )
        submitted = st.form_submit_button(
            "Analyze Resume and Generate Interview", type="primary", use_container_width=True
        )

    if not submitted:
        st.markdown("### Agent workflow")
        workflow = [
            ("1", "Resume Analyzer", "Extracts skills, education, projects, and experience."),
            ("2", "Skill Classifier", "Groups skills into technical domains."),
            ("3", "Question Generator", "Creates personalized company-style questions."),
            ("4", "Evaluation Agent", "Scores every answer and gives feedback."),
            ("5", "Roadmap Agent", "Turns weak topics into a four-week study plan."),
        ]
        for number, title, description in workflow:
            st.markdown(
                f"<div class='workflow'><b>{number}. {title}</b><br><span>{description}</span></div>",
                unsafe_allow_html=True,
            )
        return

    if not name.strip() or not email.strip() or "@" not in email:
        st.error("Enter a valid candidate name and email.")
        return
    if uploaded_resume is None:
        st.error("Upload a PDF resume to continue.")
        return

    try:
        with st.spinner("Resume Analyzer Agent is reading the resume..."):
            resume_text = extract_text_from_pdf(uploaded_resume)
            if not resume_text:
                st.error("The PDF has no extractable text. Use a text-based PDF resume.")
                return
            resume_data = resume_agent.analyze(resume_text)

        with st.spinner("Question Generation Agent is preparing the mock interview..."):
            questions = question_agent.generate(
                resume_data,
                company,
                difficulty,
                focus_areas,
                question_count,
            )
            interview_id = create_interview(
                name.strip(),
                email.strip(),
                company,
                difficulty,
                focus_areas.strip(),
                resume_data,
                questions,
            )

        st.session_state.current_interview_id = interview_id
        st.session_state.question_index = 0
        st.success(
            f"Resume analyzed with an ATS score of {resume_data['ats_score']}/100. "
            f"{len(questions)} personalized questions are ready."
        )
        with st.expander("Resume analysis", expanded=True):
            st.write(resume_data["summary"])
            st.markdown("**Detected skills**")
            render_tags(resume_data["skills"])
        if st.button("Start Mock Interview", type="primary"):
            request_page("Mock Interview")
    except Exception as error:
        st.error(f"Could not prepare the interview: {error}")


def render_mock_interview() -> None:
    st.title("Mock Interview")
    in_progress = list_interviews("in_progress")
    if not in_progress:
        st.info("There is no interview in progress.")
        if st.button("Create an interview", type="primary"):
            request_page("New Interview")
        return

    options = {f"#{item['id']} - {item['name']} - {item['company_type']}": item["id"] for item in in_progress}
    current_id = st.session_state.get("current_interview_id")
    labels = list(options)
    default_index = next(
        (index for index, label in enumerate(labels) if options[label] == current_id),
        0,
    )
    selected_label = st.selectbox("Active interview", labels, index=default_index)
    interview_id = options[selected_label]
    if current_id != interview_id:
        st.session_state.current_interview_id = interview_id
        st.session_state.question_index = 0

    interview = get_interview(interview_id)
    questions = get_questions(interview_id)
    answered_count = sum(question["answer"] is not None for question in questions)

    info_columns = st.columns(4)
    info_columns[0].metric("Company", interview["company_type"])
    info_columns[1].metric("Difficulty", interview["difficulty"])
    info_columns[2].metric("ATS score", f"{interview['ats_score']}/100")
    info_columns[3].metric("Answered", f"{answered_count}/{len(questions)}")

    index = min(st.session_state.get("question_index", 0), len(questions) - 1)
    st.session_state.question_index = index
    question = questions[index]
    st.progress(answered_count / len(questions))
    st.caption(
        f"Question {index + 1} of {len(questions)} | "
        f"{question['category']} | {question['difficulty']}"
    )
    st.markdown(f"<div class='question-card'>{question['question']}</div>", unsafe_allow_html=True)

    if question["answer"] is None:
        answer = st.text_area(
            "Your answer",
            key=f"answer_{question['id']}",
            height=180,
            placeholder="Explain your reasoning, add an example, and discuss the result or trade-offs.",
        )
        if st.button("Submit Answer for Evaluation", type="primary", use_container_width=True):
            if len(answer.strip()) < 5:
                st.warning("Write a more complete answer before submitting.")
            else:
                with st.spinner("Evaluation Agent is reviewing your answer..."):
                    evaluation = evaluation_agent.evaluate(
                        question["question"],
                        answer.strip(),
                        question["category"],
                        question["difficulty"],
                        json_load(question["expected_points"], []),
                    )
                    save_answer(question["id"], answer.strip(), evaluation)
                st.rerun()
    else:
        st.markdown("**Your answer**")
        st.write(question["answer"])
        render_evaluation(json_load(question["feedback"], {}))

    st.divider()
    previous, center, next_column = st.columns([1, 2, 1])
    with previous:
        if st.button("Previous", disabled=index == 0, use_container_width=True):
            st.session_state.question_index = index - 1
            st.rerun()
    with center:
        if st.button("Complete Interview", use_container_width=True):
            try:
                with st.spinner("Roadmap Agent is creating your learning plan..."):
                    complete_interview(interview_id)
                st.session_state.current_interview_id = interview_id
                request_page("Final Report")
            except ValueError as error:
                st.warning(str(error))
    with next_column:
        if st.button("Next", disabled=index == len(questions) - 1, use_container_width=True):
            st.session_state.question_index = index + 1
            st.rerun()


def render_final_report() -> None:
    st.title("Final Interview Report")
    completed = list_interviews("completed")
    if not completed:
        st.info("Complete a mock interview to generate a report and learning roadmap.")
        return

    options = {f"#{item['id']} - {item['name']} - {item['company_type']}": item["id"] for item in completed}
    current_id = st.session_state.get("current_interview_id")
    labels = list(options)
    default_index = next(
        (index for index, label in enumerate(labels) if options[label] == current_id),
        0,
    )
    selected_label = st.selectbox("Completed interview", labels, index=default_index)
    interview_id = options[selected_label]
    interview = get_interview(interview_id)
    questions = get_questions(interview_id)
    roadmap = get_roadmap(interview_id) or {}
    resume = get_resume_analysis(interview_id) or {}
    answered = [question for question in questions if question["score"] is not None]

    metrics = st.columns(4)
    metrics[0].metric("Overall score", f"{interview['score']}/10")
    metrics[1].metric("ATS score", f"{interview['ats_score']}/100")
    metrics[2].metric("Questions answered", f"{len(answered)}/{len(questions)}")
    metrics[3].metric("Company", interview["company_type"])

    summary_tab, review_tab, roadmap_tab, resume_tab = st.tabs(
        ["Performance", "Answer Review", "Learning Roadmap", "Resume Analysis"]
    )

    with summary_tab:
        category_data = []
        categories: dict[str, list[int]] = {}
        for question in answered:
            categories.setdefault(question["category"], []).append(question["score"])
        for category, scores in categories.items():
            category_data.append({"Category": category, "Score": round(sum(scores) / len(scores), 1)})

        st.markdown("### Category scores")
        if category_data:
            frame = pd.DataFrame(category_data).set_index("Category")
            st.bar_chart(frame, horizontal=True)

        left, right = st.columns(2)
        with left:
            st.markdown("### Strong topics")
            strong = roadmap.get("strong_topics", [])
            if strong:
                for topic in strong:
                    st.success(f"{topic['topic']}: {topic['score']}/10")
            else:
                st.caption("No strong topic identified yet.")
        with right:
            st.markdown("### Weak topics")
            weak = roadmap.get("weak_topics", [])
            if weak:
                for topic in weak:
                    st.warning(f"{topic['topic']}: {topic['score']}/10")
            else:
                st.success("No weak topics below 7/10.")

    with review_tab:
        for number, question in enumerate(questions, start=1):
            label = f"{number}. {question['category']} - {question['score'] if question['score'] is not None else 'Not answered'}/10"
            with st.expander(label):
                st.markdown(f"**Question:** {question['question']}")
                st.markdown(f"**Answer:** {question['answer'] or 'Not answered'}")
                if question["feedback"]:
                    render_evaluation(json_load(question["feedback"], {}))

    with roadmap_tab:
        st.markdown("### Four-week learning roadmap")
        st.info(roadmap.get("overall_goal", "Continue practicing your interview skills."))
        for week in roadmap.get("weeks", []):
            with st.expander(f"Week {week['week']}: {week['focus']}", expanded=week["week"] == 1):
                st.markdown("**Topics**")
                for topic in week.get("topics", []):
                    st.markdown(f"- {topic}")
                st.markdown("**Practice**")
                for exercise in week.get("practice", []):
                    st.markdown(f"- {exercise}")
                st.markdown(f"**Expected outcome:** {week.get('expected_outcome', '')}")
        st.markdown("### Recommended resources")
        for resource in roadmap.get("resources", []):
            st.markdown(f"- {resource}")

    with resume_tab:
        st.markdown("### Candidate summary")
        st.write(resume.get("summary", "No summary available."))
        st.markdown("### Skills")
        render_tags(resume.get("skills", []))
        for title, key in [
            ("Projects", "projects"),
            ("Experience", "experience"),
            ("Education", "education"),
        ]:
            st.markdown(f"### {title}")
            values = resume.get(key, [])
            if values:
                for value in values:
                    st.markdown(f"- {value}")
            else:
                st.caption(f"No {title.lower()} items detected.")

    report = {
        "interview": interview,
        "resume_analysis": resume,
        "questions": questions,
        "roadmap": roadmap,
    }
    st.download_button(
        "Download report as JSON",
        data=json.dumps(report, indent=2, default=str),
        file_name=f"interview-report-{interview_id}.json",
        mime="application/json",
    )


def configure_page() -> None:
    st.set_page_config(
        page_title="InterviewAI",
        page_icon="IA",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .stApp { background: #f5f7fb; }
        [data-testid="stSidebar"] { background: #101828; }
        [data-testid="stSidebar"] * { color: #f8fafc; }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e4e7ec;
            border-radius: 16px;
            padding: 16px;
        }
        .question-card {
            background: linear-gradient(135deg, #172554, #1d4ed8);
            color: white;
            padding: 28px;
            border-radius: 18px;
            font-size: 1.35rem;
            font-weight: 650;
            margin: 12px 0 20px;
            box-shadow: 0 14px 30px rgba(29, 78, 216, 0.18);
        }
        .tag {
            display: inline-block;
            background: #eaf2ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
            border-radius: 999px;
            padding: 5px 11px;
            margin: 3px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .workflow {
            background: white;
            border: 1px solid #e4e7ec;
            border-radius: 14px;
            padding: 14px 16px;
            margin: 8px 0;
        }
        .workflow span { color: #667085; }
        h1, h2, h3 { color: #101828; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    configure_page()
    init_database()

    if "requested_page" in st.session_state:
        st.session_state.page = st.session_state.pop("requested_page")
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"

    with st.sidebar:
        st.markdown("# InterviewAI")
        st.caption("Multi-Agent Interview Preparation")
        st.divider()
        st.radio(
            "Navigation",
            ["Dashboard", "New Interview", "Mock Interview", "Final Report"],
            key="page",
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Agent status")
        st.success("Resume Analyzer ready")
        st.success("Question Generator ready")
        st.success("Evaluation Agent ready")
        st.success("Roadmap Agent ready")
        st.caption(
            "Running in local mode. Set GEMINI_API_KEY to enable Gemini-powered responses."
        )

    pages = {
        "Dashboard": render_dashboard,
        "New Interview": render_new_interview,
        "Mock Interview": render_mock_interview,
        "Final Report": render_final_report,
    }
    pages[st.session_state.page]()


if __name__ == "__main__":
    main()
