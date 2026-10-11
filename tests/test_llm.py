"""Tests for text_diff.llm."""
import asyncio
import os

from text_diff.llm import *

def test_process_diff_without_llm_grouping():
    async def run():
        # process_diff without LLM grouping
        result = await process_diff("the old cat", "the new cat", semantic_grouping=False)

        # Should have equal + replace + equal, all with accepted flags
        types = [op["type"] for op in result]
        assert "replace" in types
        assert all("accepted" in op for op in result)

        # equal parts should be accepted, replace should not
        for op in result:
            if op["type"] == "equal":
                assert op["accepted"] == True
            elif op["type"] == "replace":
                assert op["accepted"] == False
    asyncio.run(run())


def test_identical_text_all_equal():
    async def run():
        # identical text -> all equal
        result = await process_diff("same text", "same text", semantic_grouping=False)
        assert all(op["type"] == "equal" for op in result)
        assert all(op["accepted"] == True for op in result)
    asyncio.run(run())


def test_missing_api_key_returns_error_ops():
    async def run():
        # missing API key returns error ops (temporarily clear env var)
        _saved_key = os.environ.pop("OPENROUTER_API_KEY", None)
        result = await request_text_improvement("fix grammar", "hello world", api_key="")
        if _saved_key: os.environ["OPENROUTER_API_KEY"] = _saved_key
        assert any("API Key missing" in op.get("text", "") for op in result)
    asyncio.run(run())


def test_process_diff_with_multiline_text():
    async def run():
        # process_diff with multiline text
        result = await process_diff("line one\nline two", "line one\nline three", semantic_grouping=False)
        # Should contain a newline equal block
        assert any(op.get("text") == "\n" and op["type"] == "equal" for op in result)
    asyncio.run(run())


def test_rewrite_prompt_wraps_text_and_defaults_goal():
    p = build_rewrite_prompt("", "Hello there.")
    assert p.startswith("Goal: Improve clarity")
    assert "<text>\nHello there.\n</text>" in p
    assert build_rewrite_prompt("be formal", "x").startswith("Goal: be formal\n")


def test_clean_rewrite_strips_wrappers_and_keeps_outer_whitespace():
    original = "\n  Some text.\n\n"
    assert clean_rewrite("Better text.", original) == "\n  Better text.\n\n"
    assert clean_rewrite("```\nBetter text.\n```", "Some text.") == "Better text."
    assert clean_rewrite("```markdown\nA\n\nB\n```", "a\n\nb") == "A\n\nB"
    assert clean_rewrite("<think>hmm</think>\n<text>\nBetter.\n</text>", "x") == "Better."
    assert clean_rewrite("Edited text: Better.", "x") == "Better."
    # inner structure is untouched
    assert clean_rewrite("Line one.\n\nLine two.", "a\n\nb") == "Line one.\n\nLine two."
