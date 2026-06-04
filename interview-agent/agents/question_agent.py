"""Personalized interview question generation agent."""

from __future__ import annotations

from itertools import cycle
from typing import Any

from utils.prompts import call_gemini_json, question_generation_prompt


QUESTION_BANK = {
    "Programming": [
        ("Explain the difference between mutable and immutable data.", ["mutability", "examples", "impact"]),
        ("How would you analyze the time and space complexity of a solution?", ["time complexity", "space complexity", "trade-offs"]),
        ("Explain object-oriented programming using a practical example.", ["encapsulation", "inheritance", "polymorphism"]),
    ],
    "Web Development": [
        ("How do you design a secure and maintainable web API?", ["validation", "authentication", "error handling"]),
        ("Explain client-side rendering and server-side rendering.", ["rendering", "performance", "SEO"]),
        ("How would you improve the performance of a slow web application?", ["profiling", "caching", "optimization"]),
    ],
    "Database": [
        ("Explain database indexing and when an index can hurt performance.", ["index", "read performance", "write cost"]),
        ("How do SQL joins work? Give a practical example.", ["inner join", "outer join", "relationship"]),
        ("How would you diagnose and optimize a slow SQL query?", ["execution plan", "index", "query design"]),
    ],
    "Artificial Intelligence": [
        ("How do you evaluate a machine learning model beyond accuracy?", ["precision", "recall", "cross-validation"]),
        ("Explain overfitting and the techniques you use to reduce it.", ["generalization", "regularization", "validation"]),
        ("How would you take an ML model from experiment to production?", ["pipeline", "monitoring", "deployment"]),
    ],
    "Computer Vision": [
        ("Describe a computer vision pipeline from raw image to prediction.", ["preprocessing", "features", "evaluation"]),
        ("How do lighting and image quality affect a vision model?", ["augmentation", "normalization", "robustness"]),
        ("How would you evaluate an object detection system?", ["IoU", "precision", "recall"]),
    ],
    "Cloud and DevOps": [
        ("How would you containerize and deploy an application?", ["Docker", "configuration", "deployment"]),
        ("Explain a reliable CI/CD pipeline.", ["testing", "automation", "rollback"]),
        ("How would you monitor and troubleshoot a production service?", ["logs", "metrics", "alerts"]),
    ],
    "Data and Analytics": [
        ("How do you clean and validate a new dataset?", ["missing values", "outliers", "validation"]),
        ("How would you communicate a data insight to a non-technical stakeholder?", ["context", "visualization", "recommendation"]),
        ("Explain how you would prevent data leakage.", ["training data", "validation", "pipeline"]),
    ],
    "Behavioral": [
        ("Tell me about a difficult problem you solved.", ["situation", "action", "result"]),
        ("Describe a time you received critical feedback.", ["feedback", "response", "learning"]),
        ("Tell me about a time you worked through ambiguity.", ["context", "decision", "outcome"]),
    ],
}


class QuestionGenerationAgent:
    """Generate personalized questions from resume data and interview settings."""

    def generate(
        self,
        resume_data: dict[str, Any],
        company: str,
        difficulty: str,
        focus_areas: str = "",
        question_count: int = 7,
    ) -> list[dict[str, Any]]:
        ai_result = call_gemini_json(
            question_generation_prompt(
                resume_data, company, difficulty, focus_areas, question_count
            )
        )
        if ai_result and isinstance(ai_result.get("questions"), list):
            questions = [self._normalize(question, difficulty) for question in ai_result["questions"]]
            if questions:
                return questions[:question_count]

        return self._local_questions(
            resume_data, company, difficulty, focus_areas, question_count
        )

    def _local_questions(
        self,
        resume_data: dict[str, Any],
        company: str,
        difficulty: str,
        focus_areas: str,
        question_count: int,
    ) -> list[dict[str, Any]]:
        questions = [
            {
                "question": (
                    f"Give me a concise introduction and explain why your background "
                    f"is a good fit for {company}."
                ),
                "category": "Behavioral",
                "difficulty": difficulty,
                "expected_points": ["background", "skills", "motivation"],
            }
        ]

        projects = resume_data.get("projects", [])
        if projects:
            questions.append(
                {
                    "question": (
                        f"Walk me through this resume project: {projects[0]}. "
                        "What was your contribution and what would you improve?"
                    ),
                    "category": "Projects",
                    "difficulty": difficulty,
                    "expected_points": ["problem", "contribution", "technology", "improvement"],
                }
            )

        categories = list((resume_data.get("skill_categories") or {}).keys())
        if focus_areas:
            categories = [item.strip() for item in focus_areas.split(",") if item.strip()] + categories
        categories = categories or ["Programming", "Behavioral"]

        category_cycle = cycle(categories)
        bank_positions: dict[str, int] = {}
        while len(questions) < question_count:
            requested_category = next(category_cycle)
            category = requested_category if requested_category in QUESTION_BANK else self._closest_category(requested_category)
            bank = QUESTION_BANK.get(category, QUESTION_BANK["Behavioral"])
            position = bank_positions.get(category, 0) % len(bank)
            bank_positions[category] = position + 1
            question, expected_points = bank[position]

            prefix = ""
            if difficulty == "Hard":
                prefix = "Discuss the trade-offs and failure modes: "
            elif difficulty == "Easy":
                prefix = "Explain in simple terms: "

            questions.append(
                {
                    "question": prefix + question,
                    "category": category,
                    "difficulty": difficulty,
                    "expected_points": expected_points,
                }
            )

        return questions[:question_count]

    def _closest_category(self, requested: str) -> str:
        lowered = requested.lower()
        for category in QUESTION_BANK:
            if category.lower() in lowered or lowered in category.lower():
                return category
        if "sql" in lowered or "database" in lowered:
            return "Database"
        if "system" in lowered or "design" in lowered:
            return "Cloud and DevOps"
        if "machine" in lowered or "ai" in lowered:
            return "Artificial Intelligence"
        return "Programming"

    def _normalize(self, question: dict[str, Any], difficulty: str) -> dict[str, Any]:
        return {
            "question": str(question.get("question", "")).strip(),
            "category": str(question.get("category", "General")).strip(),
            "difficulty": str(question.get("difficulty", difficulty)).strip(),
            "expected_points": [
                str(point).strip()
                for point in question.get("expected_points", [])
                if str(point).strip()
            ],
        }
