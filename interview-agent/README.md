# InterviewAI - Multi-Agent AI Interview Preparation Platform

InterviewAI is a Python and Streamlit project that analyzes a resume, generates
personalized interview questions, evaluates answers, identifies weak topics,
and creates a four-week learning roadmap.

## Project Structure

```text
interview-agent/
|-- app.py
|-- agents/
|   |-- resume_agent.py
|   |-- question_agent.py
|   |-- evaluation_agent.py
|   `-- roadmap_agent.py
|-- utils/
|   |-- pdf_reader.py
|   `-- prompts.py
|-- database/
|   `-- sqlite.db
|-- requirements.txt
`-- README.md
```

## Features

- PDF resume analysis and skill classification
- ATS resume score
- Easy, medium, and hard interview modes
- General and company-specific interviews
- Personalized technical, project, and behavioral questions
- Per-answer evaluation for accuracy, completeness, communication, and confidence
- Final performance report and category analysis
- Four-week personalized learning roadmap
- SQLite interview history and performance dashboard
- Optional Gemini integration with a complete local fallback

## Run

```bash
cd interview-agent
python -m pip install -r requirements.txt
streamlit run app.py
```

The project runs locally without an API key. To enable Gemini-powered agent
responses, set these optional environment variables before starting:

```bash
set GEMINI_API_KEY=your_key
set GEMINI_MODEL=gemini-2.0-flash
```

## Workflow

1. Open **New Interview**.
2. Enter candidate details and upload a PDF resume.
3. Choose a company, difficulty, focus areas, and question count.
4. Complete the generated mock interview.
5. Review answer-level feedback.
6. Complete the interview to generate the final report and roadmap.

## Database

`database/sqlite.db` stores:

- users
- interviews
- resume analyses
- questions and evaluations
- personalized roadmaps

The app creates or updates the required tables automatically on startup.
