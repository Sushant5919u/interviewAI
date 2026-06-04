"""Prompt builders and an optional Gemini JSON client."""

from __future__ import annotations

import json
import os
from typing import Any

import requests


def resume_analysis_prompt(resume_text: str) -> str:
    return f"""
You are the Resume Analyzer Agent for an interview preparation platform.
Extract factual information from the resume text below.

Return only valid JSON with this structure:
{{
  "skills": ["skill"],
  "skill_categories": {{"category": ["skill"]}},
  "education": ["education item"],
  "projects": ["project item"],
  "experience": ["experience item"],
  "summary": "short candidate summary"
}}

Do not invent information that is not present in the resume.

RESUME:
{resume_text[:18000]}
""".strip()


def question_generation_prompt(
    resume_data: dict[str, Any],
    company: str,
    difficulty: str,
    focus_areas: str,
    question_count: int,
) -> str:
    return f"""
You are the Question Generation Agent for a {company} interview.
Create {question_count} personalized {difficulty.lower()} interview questions.
Use the candidate data and requested focus areas. Include technical,
project-specific, and behavioral questions.

Return only valid JSON:
{{
  "questions": [
    {{
      "question": "question text",
      "category": "topic",
      "difficulty": "{difficulty}",
      "expected_points": ["important point"]
    }}
  ]
}}

CANDIDATE DATA:
{json.dumps(resume_data, ensure_ascii=True)}

FOCUS AREAS:
{focus_areas or "No additional focus areas"}
""".strip()


def evaluation_prompt(
    question: str,
    answer: str,
    category: str,
    difficulty: str,
    expected_points: list[str],
) -> str:
    return f"""
You are the Evaluation Agent. Evaluate the candidate answer fairly.
Score each metric from 0 to 10 and provide concise, actionable feedback.

Return only valid JSON:
{{
  "score": 0,
  "technical_accuracy": 0,
  "completeness": 0,
  "communication": 0,
  "confidence": 0,
  "strengths": ["strength"],
  "weaknesses": ["weakness"],
  "feedback": "short feedback",
  "improvement_suggestions": ["suggestion"]
}}

CATEGORY: {category}
DIFFICULTY: {difficulty}
EXPECTED POINTS: {json.dumps(expected_points, ensure_ascii=True)}
QUESTION: {question}
CANDIDATE ANSWER: {answer}
""".strip()


def roadmap_prompt(performance: dict[str, Any]) -> str:
    return f"""
You are the Roadmap Agent. Create a practical four-week learning roadmap from
the candidate's interview performance.

Return only valid JSON:
{{
  "overall_goal": "goal",
  "weak_topics": [{{"topic": "name", "score": 0}}],
  "strong_topics": [{{"topic": "name", "score": 0}}],
  "weeks": [
    {{
      "week": 1,
      "focus": "focus area",
      "topics": ["topic"],
      "practice": ["exercise"],
      "expected_outcome": "outcome"
    }}
  ],
  "resources": ["resource type"]
}}

PERFORMANCE:
{json.dumps(performance, ensure_ascii=True)}
""".strip()


def call_gemini_json(prompt: str) -> dict[str, Any] | None:
    """Call Gemini when configured, otherwise return None for local fallback."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.25,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError):
        return None
