"""Simple keyword skill index."""

from __future__ import annotations

from dataclasses import dataclass

from metis.skills.manager import Skill


@dataclass(frozen=True)
class SkillMatch:
    skill: Skill
    score: int


class SkillIndex:
    def __init__(self, skills: list[Skill]) -> None:
        self.skills = skills

    def search(self, task_text: str, *, top_k: int = 3) -> list[SkillMatch]:
        task = task_text.lower()
        matches: list[SkillMatch] = []
        for skill in self.skills:
            keywords = set(item.lower() for item in skill.triggers + [skill.name, skill.description])
            score = sum(1 for keyword in keywords if keyword and keyword in task)
            if score:
                matches.append(SkillMatch(skill, score))
        matches.sort(key=lambda item: (-item.score, item.skill.id))
        return matches[:top_k]

    def summarize_matches(self, task_text: str, *, top_k: int = 3, max_chars: int = 800) -> str:
        return "\n\n".join(match.skill.summary(max_chars) for match in self.search(task_text, top_k=top_k))
