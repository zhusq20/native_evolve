#!/usr/bin/env python3
"""Offline validation of the MATH env answer matcher + score + verify (NO claude). Run:
   python3 eval/test_math_env.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import envs.math as M  # the env SUBMODULE (envs/math.py) — how get_env loads it; no stdlib collision


def test_extract():
    assert M._last_boxed("so the result is \\boxed{42}.") == "42"
    assert M._last_boxed("\\boxed{\\frac{1}{2}}") == "\\frac{1}{2}"
    assert M._last_boxed("nested \\boxed{\\frac{a}{b+\\frac{1}{2}}} end").startswith("\\frac{a}")
    assert M._last_boxed("The answer is 17.") == "17"
    assert M._last_boxed("first 3 then finally 5") == "5"
    assert M._last_boxed("two boxes \\boxed{1} ... \\boxed{9}") == "9"     # LAST one
    print("ok  extract (boxed / nested / 'answer is' / last-number / last-box)")


def test_equiv():
    yes = [("\\frac{1}{2}", "1/2"), ("\\frac12", "1/2"), ("4.0", "4"), ("1,000", "1000"),
           ("17", "17"), ("$3$", "3"), (" 5 ", "5"), ("\\dfrac{3}{4}", "3/4"),
           ("\\frac{1}{2}", "\\frac{1}{2}"), ("3.0", "3")]
    no = [("3", "4"), ("1/2", "1/3"), ("12", "21"), ("", "5")]
    for a, b in yes:
        assert M._equiv(a, b), "should be equal: %r vs %r" % (a, b)
    for a, b in no:
        assert not M._equiv(a, b), "should differ: %r vs %r" % (a, b)
    print("ok  equiv (frac / decimal / commas / $ / whitespace / negatives)")


def test_score():
    task = {"answer": "4", "topic": "algebra", "level": 3, "question": "deg?"}
    assert M.score(task, "reasoning ... \\boxed{4}")["em"] == 1.0
    assert M.score(task, "... \\boxed{5}")["em"] == 0.0
    assert M.score(task, "no answer here")["em"] == 0.0
    assert M.score({"answer": "1/2"}, "\\boxed{\\frac{1}{2}}")["em"] == 1.0
    print("ok  score (right/wrong/missing/fraction-gold)")


def test_verify():
    assert M.verify({}, "I think it is 5")["signature"] == "no-final-answer"
    assert M.verify({}, "final \\boxed{}")["signature"] == "empty-answer"
    assert M.verify({}, "\\boxed{3}")["ok"] is True
    assert M.verify({}, "the answer is 7")["ok"] is True          # accepts 'answer is' form
    print("ok  verify (missing / empty / present / answer-is)")


if __name__ == "__main__":
    test_extract()
    test_equiv()
    test_score()
    test_verify()
    print("\nALL MATH-ENV OFFLINE TESTS PASSED")
