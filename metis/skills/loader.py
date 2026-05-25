"""Load SKILL.md files."""

from __future__ import annotations

from pathlib import Path

from metis.skills.manager import Skill


class SkillLoader:
    def load_dir(self, root: str | Path) -> list[Skill]:
        root = Path(root)
        return [self.load_file(path) for path in sorted(root.glob("*/SKILL.md"))]

    def load_file(self, path: str | Path) -> Skill:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        metadata, content = self._parse_frontmatter(text)
        skill_id = str(metadata.get("id") or path.parent.name)
        return Skill(
            id=skill_id,
            name=str(metadata.get("name") or skill_id),
            description=str(metadata.get("description") or ""),
            triggers=self._as_list(metadata.get("triggers")),
            content=content.strip(),
            allowed_tools=self._as_list(metadata.get("allowed_tools")),
            quality_gates=self._as_list(metadata.get("quality_gates")),
        )

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
        if not text.startswith("---\n"):
            return {}, text
        _, raw_meta, content = text.split("---", 2)
        metadata: dict[str, object] = {}
        for line in raw_meta.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                metadata[key.strip()] = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
            else:
                metadata[key.strip()] = value.strip("'\"")
        return metadata, content

    @staticmethod
    def _as_list(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]
