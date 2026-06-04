"""Personalized learning roadmap agent."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from utils.prompts import call_gemini_json, roadmap_prompt


class RoadmapAgent:
    """Identify weak topics and create a four-week improvement plan."""

    def create(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        category_scores: dict[str, list[int]] = defaultdict(list)
        for item in evaluations:
            category_scores[item.get("category", "General")].append(int(item.get("score", 0)))

        performance = {
            category: round(sum(scores) / len(scores), 1)
            for category, scores in category_scores.items()
        }
        ai_result = call_gemini_json(roadmap_prompt(performance))
        if ai_result and isinstance(ai_result.get("weeks"), list):
            return ai_result
        return self._local_roadmap(performance)

    def _local_roadmap(self, performance: dict[str, float]) -> dict[str, Any]:
        ordered = sorted(performance.items(), key=lambda item: item[1])
        weak = [{"topic": topic, "score": score} for topic, score in ordered if score < 7]
        strong = [
            {"topic": topic, "score": score}
            for topic, score in sorted(performance.items(), key=lambda item: item[1], reverse=True)
            if score >= 7
        ]
        priorities = [item["topic"] for item in weak] or [item["topic"] for item in strong[:2]]
        priorities = priorities or ["Technical Fundamentals", "Communication"]

        weeks = []
        for index in range(4):
            topic = priorities[index % len(priorities)]
            weeks.append(
                {
                    "week": index + 1,
                    "focus": topic,
                    "topics": [
                        f"Core concepts in {topic}",
                        f"Common interview patterns for {topic}",
                        f"Trade-offs and practical examples in {topic}",
                    ],
                    "practice": [
                        f"Study {topic} for 30 minutes on five days",
                        f"Answer three {topic} interview questions aloud",
                        "Review answers and rewrite the weakest response",
                    ],
                    "expected_outcome": (
                        f"Explain {topic} clearly, answer follow-up questions, "
                        "and support decisions with examples."
                    ),
                }
            )

        return {
            "overall_goal": (
                "Build confident, structured answers and raise weak-topic scores "
                "to at least 7/10."
            ),
            "weak_topics": weak,
            "strong_topics": strong,
            "weeks": weeks,
            "resources": [
                "Official documentation for each technical topic",
                "Timed mock interviews with answer review",
                "A personal STAR-story bank for behavioral questions",
            ],
        }
