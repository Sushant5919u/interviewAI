"""Resume analysis and skill classification agent."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from utils.prompts import call_gemini_json, resume_analysis_prompt


SKILL_CATEGORIES = {
    "Programming": [
        "Python",
        "Java",
        "C",
        "C++",
        "C#",
        "JavaScript",
        "TypeScript",
        "Go",
        "Rust",
        "Kotlin",
        "Swift",
    ],
    "Web Development": [
        "HTML",
        "CSS",
        "React",
        "Next.js",
        "Angular",
        "Vue",
        "Node.js",
        "Django",
        "Flask",
        "FastAPI",
        "Streamlit",
    ],
    "Database": [
        "SQL",
        "MySQL",
        "PostgreSQL",
        "SQLite",
        "MongoDB",
        "Redis",
        "Oracle",
    ],
    "Artificial Intelligence": [
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "Natural Language Processing",
        "TensorFlow",
        "PyTorch",
        "Scikit-learn",
        "LLM",
        "Generative AI",
    ],
    "Computer Vision": ["OpenCV", "Computer Vision", "YOLO", "Image Processing"],
    "Cloud and DevOps": [
        "AWS",
        "Azure",
        "GCP",
        "Docker",
        "Kubernetes",
        "Git",
        "GitHub",
        "CI/CD",
        "Linux",
    ],
    "Data and Analytics": [
        "Pandas",
        "NumPy",
        "Power BI",
        "Tableau",
        "Excel",
        "Data Analysis",
        "Data Science",
    ],
}


class ResumeAnalyzerAgent:
    """Extract structured candidate information and calculate an ATS score."""

    def analyze(self, resume_text: str) -> dict[str, Any]:
        ai_result = call_gemini_json(resume_analysis_prompt(resume_text))
        if ai_result and isinstance(ai_result.get("skills"), list):
            result = self._normalize_ai_result(ai_result)
        else:
            result = self._local_analysis(resume_text)

        result["ats_score"] = self.calculate_ats_score(result, resume_text)
        return result

    def _normalize_ai_result(self, data: dict[str, Any]) -> dict[str, Any]:
        skills = sorted({str(skill).strip() for skill in data.get("skills", []) if str(skill).strip()})
        categories = data.get("skill_categories") or self.classify_skills(skills)
        return {
            "skills": skills,
            "skill_categories": categories,
            "education": self._string_list(data.get("education", [])),
            "projects": self._string_list(data.get("projects", [])),
            "experience": self._string_list(data.get("experience", [])),
            "summary": str(data.get("summary", "")).strip()
            or self._build_summary(skills, data.get("projects", [])),
        }

    def _local_analysis(self, text: str) -> dict[str, Any]:
        skills = self.extract_skills(text)
        sections = self._sections(text)
        education = self._extract_section_lines(sections, ["education", "academic"])
        projects = self._extract_section_lines(sections, ["projects", "project"])
        experience = self._extract_section_lines(
            sections, ["experience", "employment", "internship", "work experience"]
        )

        if not education:
            education = self._matching_lines(
                text, ["bachelor", "master", "b.tech", "m.tech", "university", "college"]
            )
        if not projects:
            projects = self._matching_lines(text, ["project", "developed", "built", "created"])
        if not experience:
            experience = self._matching_lines(text, ["intern", "engineer", "developer", "experience"])

        return {
            "skills": skills,
            "skill_categories": self.classify_skills(skills),
            "education": education[:5],
            "projects": projects[:5],
            "experience": experience[:5],
            "summary": self._build_summary(skills, projects),
        }

    def extract_skills(self, text: str) -> list[str]:
        lowered = text.lower()
        found = []
        for skills in SKILL_CATEGORIES.values():
            for skill in skills:
                pattern = rf"(?<!\w){re.escape(skill.lower())}(?!\w)"
                if re.search(pattern, lowered):
                    found.append(skill)
        return sorted(set(found), key=str.lower)

    def classify_skills(self, skills: list[str]) -> dict[str, list[str]]:
        categories: dict[str, list[str]] = defaultdict(list)
        lookup = {
            skill.lower(): category
            for category, category_skills in SKILL_CATEGORIES.items()
            for skill in category_skills
        }
        for skill in skills:
            categories[lookup.get(skill.lower(), "Other")].append(skill)
        return dict(categories)

    def calculate_ats_score(self, result: dict[str, Any], text: str) -> int:
        score = 0
        score += min(35, len(result.get("skills", [])) * 3)
        score += min(20, len(result.get("projects", [])) * 7)
        score += min(20, len(result.get("experience", [])) * 7)
        score += 10 if result.get("education") else 0
        score += 5 if re.search(r"[\w.+-]+@[\w.-]+\.\w+", text) else 0
        score += 5 if re.search(r"\+?\d[\d\s()-]{8,}", text) else 0
        score += 5 if 250 <= len(text.split()) <= 1200 else 0
        return min(100, score)

    def _sections(self, text: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = defaultdict(list)
        current = "profile"
        headings = {
            "education",
            "academic",
            "skills",
            "technical skills",
            "projects",
            "project",
            "experience",
            "work experience",
            "employment",
            "internship",
            "certifications",
        }
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" -|:\t")
            if not line:
                continue
            normalized = line.lower()
            if normalized in headings:
                current = normalized
            else:
                sections[current].append(line)
        return dict(sections)

    def _extract_section_lines(
        self, sections: dict[str, list[str]], names: list[str]
    ) -> list[str]:
        values = []
        for name in names:
            values.extend(sections.get(name, []))
        return self._deduplicate(values)

    def _matching_lines(self, text: str, words: list[str]) -> list[str]:
        lines = []
        for line in text.splitlines():
            clean = re.sub(r"\s+", " ", line).strip(" -|:\t")
            if clean and any(word in clean.lower() for word in words):
                lines.append(clean)
        return self._deduplicate(lines)[:5]

    def _build_summary(self, skills: list[str], projects: list[Any]) -> str:
        skill_text = ", ".join(skills[:6]) or "general technical skills"
        project_count = len(projects)
        return (
            f"Candidate profile highlights {skill_text} with "
            f"{project_count} identified project{'s' if project_count != 1 else ''}."
        )

    def _string_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        result = []
        for value in values:
            if isinstance(value, dict):
                result.append(", ".join(str(item) for item in value.values() if item))
            elif str(value).strip():
                result.append(str(value).strip())
        return self._deduplicate(result)

    def _deduplicate(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))
