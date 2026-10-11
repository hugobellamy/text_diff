"""Tests for text_diff.group."""

from text_diff.group import *

def test_consecutive_replaces_merge():
    # consecutive replaces merge
    ops = [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "replace", "old_text": "b", "new_text": "y"},
    ]
    result = group_replacements(ops)
    assert len(result) == 1
    assert result[0] == {"type": "replace", "old_text": "ab", "new_text": "xy"}


def test_replaces_separated_by_small_equal_connector_merge():
    # replaces separated by small equal connector merge
    ops = [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "equal", "text": " "},
        {"type": "replace", "old_text": "b", "new_text": "y"},
    ]
    result = group_replacements(ops)
    assert len(result) == 1
    assert result[0] == {"type": "replace", "old_text": "a b", "new_text": "x y"}


def test_large_equal_block_prevents_merging():
    # large equal block prevents merging
    ops = [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "equal", "text": "long text here"},
        {"type": "replace", "old_text": "b", "new_text": "y"},
    ]
    result = group_replacements(ops)
    assert len(result) == 3


def test_newlines_block_merging():
    # newlines block merging
    ops = [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "replace", "old_text": "b\nc", "new_text": "y\nz"},
    ]
    result = group_replacements(ops)
    # first replace stays alone, second has newline so doesn't merge
    assert len(result) == 2
    assert result[0] == {"type": "replace", "old_text": "a", "new_text": "x"}


def test_newline_in_equal_connector_blocks_merging():
    # newline in equal connector blocks merging
    ops = [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "equal", "text": "\n"},
        {"type": "replace", "old_text": "b", "new_text": "y"},
    ]
    result = group_replacements(ops)
    assert len(result) == 3


def test_consecutive_same_type_simple_ops_merge():
    # consecutive same-type simple ops merge
    ops = [
        {"type": "equal", "text": "hello "},
        {"type": "equal", "text": "world"},
    ]
    result = group_replacements(ops)
    assert result == [{"type": "equal", "text": "hello world"}]


def test_group_replacements_empty():
    # empty
    assert group_replacements([]) == []


def test_no_groups_pass_through():
    # no groups -> pass through
    ops = [{"type": "equal", "text": "hello"}]
    assert apply_semantic_groups(ops, []) == ops


def test_group_two_replaces():
    # group two replaces
    ops = [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "replace", "old_text": "b", "new_text": "y"},
        {"type": "equal", "text": " end"},
    ]
    result = apply_semantic_groups(ops, [[0, 1]])
    assert len(result) == 2
    assert result[0] == {"type": "replace", "old_text": "ab", "new_text": "xy", "accepted": False}
    assert result[1] == {"type": "equal", "text": " end"}


def test_mixed_types_becomes_replace():
    # mixed types -> becomes replace
    ops = [
        {"type": "remove", "text": "old"},
        {"type": "equal", "text": " "},
        {"type": "add", "text": "new"},
    ]
    result = apply_semantic_groups(ops, [[0, 1, 2]])
    assert len(result) == 1
    assert result[0] == {"type": "replace", "old_text": "old ", "new_text": " new", "accepted": False}


def test_non_consecutive_group_is_skipped_each_index_handle():
    # non-consecutive group is skipped (each index handled individually)
    ops = [
        {"type": "replace", "old_text": "a", "new_text": "x"},
        {"type": "equal", "text": "middle"},
        {"type": "replace", "old_text": "b", "new_text": "y"},
    ]
    result = apply_semantic_groups(ops, [[0, 2]])  # non-consecutive!
    assert len(result) == 3  # nothing merged


def test_multiple_independent_groups():
    # multiple independent groups
    ops = [
        {"type": "add", "text": "a"},
        {"type": "add", "text": "b"},
        {"type": "equal", "text": " mid "},
        {"type": "remove", "text": "c"},
        {"type": "remove", "text": "d"},
    ]
    result = apply_semantic_groups(ops, [[0, 1], [3, 4]])
    assert len(result) == 3
    assert result[0] == {"type": "add", "text": "ab", "accepted": False}
    assert result[1] == {"type": "equal", "text": " mid "}
    assert result[2] == {"type": "remove", "text": "cd", "accepted": False}
