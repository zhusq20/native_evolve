from utils.json_util import save_to_json, read_from_json, save_to_jsonl, read_from_jsonl


def test_roundtrip_json_dict(tmp_path):
    data = {"a": 1, "b": [2, 3], "c": {"nested": True}}
    p = tmp_path / "out.json"
    save_to_json(data, str(p))
    assert read_from_json(str(p)) == data


def test_roundtrip_json_list(tmp_path):
    data = [{"x": 1}, {"y": 2}]
    p = tmp_path / "out.json"
    save_to_json(data, str(p))
    assert read_from_json(str(p)) == data


def test_save_json_creates_parent_dirs(tmp_path):
    p = tmp_path / "nested" / "dir" / "out.json"
    save_to_json({"k": "v"}, str(p))
    assert p.exists()
    assert read_from_json(str(p)) == {"k": "v"}


def test_read_json_missing_returns_empty_dict(tmp_path):
    assert read_from_json(str(tmp_path / "missing.json")) == {}


def test_read_json_empty_file_returns_empty_dict(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("")
    assert read_from_json(str(p)) == {}


def test_roundtrip_jsonl(tmp_path):
    rows = [{"i": 1}, {"i": 2}, {"i": 3}]
    p = tmp_path / "rows.jsonl"
    save_to_jsonl(rows, str(p))
    assert read_from_jsonl(str(p)) == rows


def test_read_jsonl_missing_returns_empty_list(tmp_path):
    assert read_from_jsonl(str(tmp_path / "missing.jsonl")) == []
