"""Interview answer evaluation and feedback agent."""

from __future__ import annotations

import re
from typing import Any

from utils.prompts import call_gemini_json, evaluation_prompt


class EvaluationAgent:
    """Score answers for accuracy, completeness, communication, and confidence."""

    def evaluate(
        self,
        question: str,
        answer: str,
        category: str,
        difficulty: str,
        expected_points: list[str],
    ) -> dict[str, Any]:
        ai_result = call_gemini_json(
            evaluation_prompt(question, answer, category, difficulty, expected_points)
        )
        if ai_result and "score" in ai_result:
            return self._normalize(ai_result)
        return self._local_evaluation(answer, expected_points, difficulty)

    def _local_evaluation(
        self, answer: str, expected_points: list[str], difficulty: str
    ) -> dict[str, Any]:
        words = re.findall(r"\b[\w+-]+\b", answer.lower())
        word_count = len(words)
        lowered = answer.lower()
        covered = [point for point in expected_points if point.lower() in lowered]
        coverage = len(covered) / max(1, len(expected_points))

        technical_accuracy = min(10, round(3 + coverage * 6 + min(word_count, 100) / 100))
        completeness = min(10, round(2 + coverage * 5 + min(word_count, 120) / 35))
        structure_signals = sum(
            signal in lowered
            for signal in ["first", "because", "for example", "result", "however", "therefore"]
        )
        communication = min(10, round(4 + min(word_count, 80) / 25 + structure_signals * 0.5))
        uncertain = sum(
            phrase in lowered for phrase in ["i don't know", "maybe", "i guess", "not sure"]
        )
        confidence = max(2, min(10, round(6 + min(word_count, 80) / 30 - uncertain * 2)))

        if word_count < 12:
            technical_accuracy = min(technical_accuracy, 4)
            completeness = min(completeness, 3)
            communication = min(communication, 4)

        difficulty_penalty = {"Easy": 0, "Medium": 0.3, "Hard": 0.7}.get(difficulty, 0)
        score = round(
            (
                technical_accuracy * 0.4
                + completeness * 0.3
                + communication * 0.2
                + confidence * 0.1
            )
            - difficulty_penalty
        )
        score = max(0, min(10, score))

        strengths = []
        if covered:
            strengths.append("Covered key ideas: " + ", ".join(covered[:3]))
        if word_count >= 40:
            strengths.append("Provided enough detail to demonstrate the thought process")
        if structure_signals:
            strengths.append("Used a clear and structured explanation")
        if not strengths:
            strengths.append("Attempted the question directly")

        missing = [point for point in expected_points if point not in covered]
        weaknesses = []
        if missing:
            weaknesses.append("Did not clearly cover: " + ", ".join(missing[:3]))
        if word_count < 30:
            weaknesses.append("The answer needs more supporting detail and examples")
        if uncertain:
            weaknesses.append("Uncertain phrasing reduced confidence")
        if not weaknesses:
            weaknesses.append("Could discuss trade-offs and edge cases in more depth")

        suggestions = [
            "Use a Situation, Action, Result structure or a definition, example, trade-off structure.",
            "Add one concrete example and explain the result.",
        ]
        if missing:
            suggestions.insert(0, "Review and explicitly explain: " + ", ".join(missing[:3]))

        return {
            "score": score,
            "technical_accuracy": technical_accuracy,
            "completeness": completeness,
            "communication": communication,
            "confidence": confidence,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "feedback": (
                f"This answer scored {score}/10. It shows a useful foundation, "
                "but stronger examples and explicit coverage of the key points "
                "would make it more interview-ready."
            ),
            "improvement_suggestions": suggestions,
        }

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        def score(name: str) -> int:
            return max(0, min(10, round(float(data.get(name, 0)))))

        return {
            "score": score("score"),
            "technical_accuracy": score("technical_accuracy"),
            "completeness": score("completeness"),
            "communication": score("communication"),
            "confidence": score("confidence"),
            "strengths": self._list(data.get("strengths")),
            "weaknesses": self._list(data.get("weaknesses")),
            "feedback": str(data.get("feedback", "")).strip(),
            "improvement_suggestions": self._list(data.get("improvement_suggestions")),
        }

    def _list(self, value: Any) -> list[str]:
        return [str(item).strip() for item in value] if isinstance(value, list) else []
