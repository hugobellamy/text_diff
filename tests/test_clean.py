"""Tests for text_diff.clean."""

from text_diff.clean import *

def test_whitespace_only_add_becomes_equal():
    # whitespace-only add -> becomes equal
    ops = [{"type": "equal", "text": "hello"}, {"type": "add", "text": "  "}]
    result = clean_newlines(ops)
    assert len(result) == 1  # merged into single equal
    assert result[0] == {"type": "equal", "text": "hello  "}


def test_whitespace_only_remove_dropped():
    # whitespace-only remove -> dropped
    ops = [{"type": "equal", "text": "hello"}, {"type": "remove", "text": "\n"}, {"type": "equal", "text": "world"}]
    result = clean_newlines(ops)
    assert len(result) == 1
    assert result[0] == {"type": "equal", "text": "helloworld"}


def test_whitespace_replace_indent_change_equal_with_new_wh():
    # whitespace replace (indent change) -> equal with new whitespace
    ops = [{"type": "replace", "old_text": "  ", "new_text": "    "}]
    result = clean_newlines(ops)
    assert result == [{"type": "equal", "text": "    "}]


def test_real_changes_pass_through_untouched():
    # real changes pass through untouched
    ops = [
        {"type": "equal", "text": "the "},
        {"type": "replace", "old_text": "old", "new_text": "new"},
        {"type": "equal", "text": " cat"},
    ]
    result = clean_newlines(ops)
    assert len(result) == 3
    assert result[1] == {"type": "replace", "old_text": "old", "new_text": "new"}


def test_clean_newlines_empty():
    # empty input
    assert clean_newlines([]) == []


def test_equal_with_newline_splits_into_text_newline_text():
    # equal with newline splits into text + newline + text
    ops = [{"type": "equal", "text": "hello\nworld"}]
    result = extract_newlines_to_blocks(ops)
    assert result == [
        {"type": "equal", "text": "hello"},
        {"type": "equal", "text": "\n"},
        {"type": "equal", "text": "world"},
    ]


def test_add_with_newline_splits_similarly():
    # add with newline splits similarly
    ops = [{"type": "add", "text": "line1\nline2"}]
    result = extract_newlines_to_blocks(ops)
    assert result == [
        {"type": "add", "text": "line1"},
        {"type": "equal", "text": "\n"},
        {"type": "add", "text": "line2"},
    ]


def test_remove_with_newline_drops_the_newlines():
    # remove with newline drops the newlines
    ops = [{"type": "remove", "text": "old1\nold2"}]
    result = extract_newlines_to_blocks(ops)
    assert result == [
        {"type": "remove", "text": "old1"},
        {"type": "remove", "text": "old2"},
    ]


def test_symmetric_replace_with_newlines():
    # symmetric replace with newlines
    ops = [{"type": "replace", "old_text": "a\nb", "new_text": "x\ny"}]
    result = extract_newlines_to_blocks(ops)
    assert result == [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "equal", "text": "\n"},
        {"type": "replace", "old_text": "b", "new_text": "y"},
    ]


def test_asymmetric_replace_kept_as_is():
    # asymmetric replace kept as-is
    ops = [{"type": "replace", "old_text": "a", "new_text": "x\ny"}]
    result = extract_newlines_to_blocks(ops)
    assert len(result) == 1
    assert result[0]["type"] == "replace"


def test_extract_newlines_empty():
    # empty input
    assert extract_newlines_to_blocks([]) == []


def test_equal_accepted():
    # equal -> accepted
    result = add_accepted_flags([{"type": "equal", "text": "hello"}])
    assert result == [{"type": "equal", "text": "hello", "accepted": True}]


def test_add_remove_not_accepted():
    # add/remove -> not accepted
    result = add_accepted_flags([
        {"type": "add", "text": "new"},
        {"type": "remove", "text": "old"},
    ])
    assert result[0]["accepted"] == False
    assert result[1]["accepted"] == False


def test_replace_deleting_1_3_spaces_auto_accepted_as_equal():
    # replace deleting 1-3 spaces -> auto-accepted as equal
    result = add_accepted_flags([{"type": "replace", "old_text": "  ", "new_text": ""}])
    assert result == [{"type": "equal", "text": "", "accepted": True}]


def test_real_replace_not_accepted():
    # real replace -> not accepted
    result = add_accepted_flags([{"type": "replace", "old_text": "old", "new_text": "new"}])
    assert result == [{"type": "replace", "old_text": "old", "new_text": "new", "accepted": False}]


def test_add_accepted_flags_empty():
    # empty
    assert add_accepted_flags([]) == []
