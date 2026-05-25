from metis.skills.loader import SkillLoader


def test_skill_loader_loads_chinese_skill_with_frontmatter(tmp_path):
    skill_dir = tmp_path / "skills" / "writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "id: writer\n"
        "name: 写作技能\n"
        "description: 生成中文文档\n"
        "triggers: [文档, 报告]\n"
        "allowed_tools: [read_file]\n"
        "---\n"
        "请生成结构化内容。",
        encoding="utf-8",
    )

    skills = SkillLoader().load_dir(tmp_path / "skills")

    assert skills[0].name == "写作技能"
    assert skills[0].triggers == ["文档", "报告"]
    assert "结构化" in skills[0].content
