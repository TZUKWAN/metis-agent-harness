from metis.skills.manager import Skill


def test_skill_model_summary():
    skill = Skill(id="doc", name="Docs", description="Write docs", triggers=["文档"], content="Long content")

    assert "Docs" in skill.summary()
    assert "文档" in skill.summary()
