from app.prompts import build_softpost_prompt


def test_prompt_contains_topic_and_constraints() -> None:
    text = build_softpost_prompt("看短剧赚钱", "宝妈,大学生", "玩一玩就能赚钱")
    assert "看短剧赚钱" in text
    assert "输出严格 JSON" in text
