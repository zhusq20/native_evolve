from utils.parser import recover_list_from_string, recover_dict_from_string


def test_recover_list_basic():
    assert recover_list_from_string("[1, 2, 3]") == [1, 2, 3]
    assert recover_list_from_string("['a', 'b']") == ['a', 'b']


def test_recover_list_nested():
    assert recover_list_from_string("[[1, 2], [3, 4]]") == [[1, 2], [3, 4]]
    assert recover_list_from_string("['[[', ']]']") == ['[[', ']]']


def test_recover_list_empty():
    assert recover_list_from_string("[]") == []


def test_recover_list_invalid_returns_none():
    assert recover_list_from_string("not a list") is None
    assert recover_list_from_string("[unclosed") is None


def test_recover_list_non_list_returns_none():
    assert recover_list_from_string("{'k': 1}") is None
    assert recover_list_from_string("42") is None


def test_recover_dict_basic():
    assert recover_dict_from_string("{'a': 1, 'b': 2}") == {'a': 1, 'b': 2}


def test_recover_dict_nested():
    assert recover_dict_from_string("{'a': {'b': 1}}") == {'a': {'b': 1}}


def test_recover_dict_empty():
    assert recover_dict_from_string("{}") == {}


def test_recover_dict_invalid_returns_none():
    assert recover_dict_from_string("not a dict") is None
    assert recover_dict_from_string("[1, 2, 3]") is None
