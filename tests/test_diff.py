"""Tests for text_diff.diff."""

from text_diff.diff import *

def reconstruct(ops):
    """Helper to verify ops can reconstruct both texts."""
    original = ""
    rewritten = ""
    for op in ops:
        if op["type"] == "equal":
            original += op["text"]
            rewritten += op["text"]
        elif op["type"] == "remove":
            original += op["text"]
        elif op["type"] == "add":
            rewritten += op["text"]
        elif op["type"] == "replace":
            original += op["old_text"]
            rewritten += op["new_text"]
    return original, rewritten


def test_tokenize_preserving_whitespace():
    assert tokenize_preserving_whitespace("hello world") == ["hello", " ", "world"]
    assert tokenize_preserving_whitespace("hello  world") == ["hello", "  ", "world"]
    assert tokenize_preserving_whitespace("  leading") == ["  ", "leading"]
    assert tokenize_preserving_whitespace("") == []
    assert "".join(tokenize_preserving_whitespace("hello\nworld  foo")) == "hello\nworld  foo"


def test_identical_text_single_equal_op():
    # Test: identical text -> single equal op
    ops = compute_diff("hello world", "hello world")
    assert len(ops) == 1
    assert ops[0] == {"type": "equal", "text": "hello world"}


def test_empty_inputs():
    # Test: empty inputs
    assert compute_diff("", "") == [{"type": "equal", "text": ""}]
    assert compute_diff("", "hello") == [{"type": "add", "text": "hello"}]
    assert compute_diff("hello", "") == [{"type": "remove", "text": "hello"}]


def test_simple_word_replacement():
    # Test: simple word replacement
    ops = compute_diff("the old cat", "the new cat")
    assert ops[0] == {"type": "equal", "text": "the "}
    assert ops[1] == {"type": "replace", "old_text": "old", "new_text": "new"}
    assert ops[2] == {"type": "equal", "text": " cat"}


def test_insertion():
    # Test: insertion
    ops = compute_diff("I like cats", "I really like cats")
    assert any(op["type"] == "add" and "really" in op["text"] for op in ops)


def test_deletion():
    # Test: deletion
    ops = compute_diff("I really like cats", "I like cats")
    assert any(op["type"] == "remove" and "really" in op["text"] for op in ops)


def test_multiline_and_reconstruction():
    # Test: multiline
    ops = compute_diff("line one\nline two", "line one\nline three")
    assert ops[0]["type"] == "equal"
    assert any(op["type"] == "replace" for op in ops)

    orig, rewr = reconstruct(compute_diff("the old cat sat", "the new cat lay"))
    assert orig == "the old cat sat"
    assert rewr == "the new cat lay"


def test_long_input_stays_word_level_autojunk_regression():
    # Test: long input stays word-level (autojunk regression)
    # On sequences >200 tokens, SequenceMatcher's default autojunk drops common
    # tokens (spaces, the/to/a) from matching, which used to collapse long diffs
    # into paragraph-sized replacements. Here the two texts differ only by a single
    # word, so the diff must stay tiny no matter how long the surrounding text is.
    import re

    _base = ("The system processes the data and returns a result to the user. " * 30).strip()
    _orig = _base + " The final value is correct."
    _rewr = _base + " The final value is wrong."

    ops = compute_diff(_orig, _rewr)
    changes = [op for op in ops if op["type"] in ("add", "remove", "replace")]
    # Exactly one change, and it must be the single swapped word — not a big block.
    assert len(changes) == 1, f"expected 1 change, got {len(changes)}: {changes}"
    ch = changes[0]
    assert ch["type"] == "replace"
    assert len(ch["old_text"].split()) == 1 and len(ch["new_text"].split()) == 1, ch
    assert (ch["old_text"], ch["new_text"]) == ("correct.", "wrong.")

    # And reconstruction still holds on the long input.
    orig2, rewr2 = reconstruct(ops)
    assert orig2 == _orig and rewr2 == _rewr
