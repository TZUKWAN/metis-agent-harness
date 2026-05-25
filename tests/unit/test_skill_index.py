from metis.skills.index import SkillIndex
from metis.skills.manager import Skill


def test_skill_index_matches_relevant_skill():
    skills = [
        Skill(id="doc", name="Docs", description="write report", triggers=["报告"]),
        Skill(id="code", name="Code", description="implement code", triggers=["代码"]),
    ]
    matches = SkillIndex(skills).search("请写一份报告", top_k=1)

    assert matches[0].skill.id == "doc"
    assert matches[0].score > 0
