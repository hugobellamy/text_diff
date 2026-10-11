"""Tests for text_diff.blocks."""

from text_diff.blocks import *
from text_diff.blocks import _split_equal

original = "The cat sat on the mat. It was very very happy. The end."
rewritten = "The cat lay on the rug. It was very happy. The end."

def test_split_equal():
    assert _split_equal("One. Two", "sentence") == [
        {"text": "One.", "boundary": False},
        {"text": " ", "boundary": True},
        {"text": "Two", "boundary": False},
    ]
    assert _split_equal("a, b", "sentence") == [{"text": "a, b", "boundary": False}]
    assert [p["text"] for p in _split_equal("a, b", "clause")] == ["a,", " ", "b"]
    assert _split_equal("x\n\ny", "sentence")[1] == {"text": "\n\n", "boundary": True}
    # punctuation inside the preceding change still ends the sentence
    assert _split_equal(" It was", "sentence", prev=".")[0] == {"text": " ", "boundary": True}


def test_compute_blocks():
    blocks = compute_blocks(original, rewritten)
    changes = [b for b in blocks if b["type"] == "change"]
    # two edits in the first sentence -> one block; one edit in the second -> one block
    assert len(changes) == 2
    assert changes[0]["old_text"] == "The cat sat on the mat."
    assert changes[0]["new_text"] == "The cat lay on the rug."
    assert changes[1]["old_text"] == "It was very very happy."
    # blocks rebuild both texts exactly
    assert "".join(b["old_text"] for b in blocks) == original
    assert "".join(b["new_text"] for b in blocks) == rewritten
    assert all(b["status"] == "accepted" for b in blocks if b["type"] == "equal")
    assert all(b["status"] == "pending" for b in changes)
    assert [b["id"] for b in blocks] == [str(i) for i in range(len(blocks))]


def test_unchanged_text_collapses_into_a_single_equal_block():
    # unchanged text collapses into a single equal block
    assert compute_blocks("Same. Text.", "Same. Text.") == [
        {"type": "equal", "old_text": "Same. Text.", "new_text": "Same. Text.",
         "ops": [{"type": "equal", "text": "Same. Text."}], "comment": "", "status": "accepted", "id": "0"}
    ]
    # a change that merges two sentences becomes one block spanning both
    b = compute_blocks("Short one. Short two.", "Short one and short two.")
    assert [x["type"] for x in b] == ["change"]
    # clause granularity gives smaller blocks
    o, r = "First part, second part.", "First bit, second bit."
    assert len([x for x in compute_blocks(o, r) if x["type"] == "change"]) == 1
    assert len([x for x in compute_blocks(o, r, "clause") if x["type"] == "change"]) == 2
    # paragraphs are hard boundaries
    b = compute_blocks("A b\n\nC d", "A x\n\nC y")
    assert len([x for x in b if x["type"] == "change"]) == 2
    # rebuild property on a longer text
    o = "Line one is here.\nLine two, with a clause. And more!\n\nNew para? Yes."
    r = "Line one is there.\nLine two, with clauses. And more!\n\nA new para? Yes indeed."
    for g in ("sentence", "clause"):
        bl = compute_blocks(o, r, g)
        assert "".join(x["old_text"] for x in bl) == o
        assert "".join(x["new_text"] for x in bl) == r


def test_status_and_edit():
    bl = compute_blocks(original, rewritten)
    assert blocks_to_text(bl) == original
    first, second = [b["id"] for b in bl if b["type"] == "change"]
    bl = set_status(bl, first, "accepted")
    assert blocks_to_text(bl).startswith("The cat lay on the rug. It was very very happy.")
    # rejected and pending both keep the original
    bl = set_status(bl, second, "rejected")
    assert blocks_to_text(bl) == "The cat lay on the rug. It was very very happy. The end."
    # helpers don't mutate their input
    fresh = compute_blocks(original, rewritten)
    set_status(fresh, first, "accepted")
    assert fresh[int(first)]["status"] == "pending"
    # edit a suggestion, then accept it
    bl = edit_block(fresh, second, "It was so happy.")
    assert bl[int(second)]["new_text"] == "It was so happy."
    assert {"type": "replace", "old_text": "very very", "new_text": "so"} in bl[int(second)]["ops"]
    bl = set_status(bl, second, "accepted")
    assert blocks_to_text(bl) == "The cat sat on the mat. It was so happy. The end."
    # bad input is rejected loudly
    for call in (lambda: set_status(bl, first, "maybe"), lambda: set_status(bl, "999", "accepted"),
                 lambda: edit_block(bl, str(len(bl) - 1), "x")):
        try: call(); raise AssertionError("should have raised")
        except (ValueError, KeyError): pass


def test_comments():
    assert parse_comments('```json\n{"1": "Tighter wording", "3": " Fixes typo "}\n```') == {"1": "Tighter wording", "3": "Fixes typo"}
    assert parse_comments("no json here") == {}
    bl = compute_blocks(original, rewritten)
    ids = [b["id"] for b in bl if b["type"] == "change"]
    out = apply_comments(bl, {ids[0]: "Clearer verb", "999": "ignored"})
    assert out[int(ids[0])]["comment"] == "Clearer verb"
    assert all(b["comment"] == "" for b in out if b["id"] != ids[0])
    assert '"before": "The cat sat on the mat."' in comment_prompt(bl, "be concise")


def test_parse_comments_ignores_reasoning_block():
    assert parse_comments('<think>maybe {"x": 1}?</think>{"0": "Cuts filler words"}') == {"0": "Cuts filler words"}
