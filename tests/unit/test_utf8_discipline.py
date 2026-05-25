def test_utf8_chinese_roundtrip(tmp_path):
    path = tmp_path / "中文.md"
    path.write_text("莫提斯架构", encoding="utf-8")

    assert path.read_text(encoding="utf-8") == "莫提斯架构"
