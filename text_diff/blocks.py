"""Sentence-sized change blocks with optional LLM comments.

A word-level diff is precise but hard to review: one rephrased sentence can
become several scattered fragments. A block gathers every change inside one
sentence (or clause) into a single unit that is accepted or rejected as a
whole, while keeping the word-level ops for highlighting. See INTERFACE.md."""


__all__ = ['STATUSES', 'ops_to_blocks', 'compute_blocks', 'blocks_to_text', 'set_status', 'edit_block', 'comment_prompt',
           'parse_comments', 'apply_comments', 'add_comments', 'improve_text']

import re
import json
import httpx
from typing import List, Dict, Any, Optional

from .diff import compute_diff
from .clean import clean_newlines

class _Shifted:
    "A regex match with positions shifted back by `n`."
    def __init__(self, m, n): self._m, self._n = m, n
    def start(self): return self._m.start() - self._n
    def end(self): return self._m.end() - self._n
    def group(self): return self._m.group()

_BOUNDARY = {
    "sentence": re.compile(r'(?<=[.!?])[ \t]+|\n+'),
    "clause": re.compile(r'(?<=[.!?,;:])[ \t]+|\n+'),
}

def _split_equal(text: str, granularity: str, prev: str = "") -> List[Dict[str, Any]]:
    """Split unchanged text into pieces, marking the separators that end a unit.

    `prev` is the character just before `text` (it may sit inside a change, as in
    "mat." -> "rug."), so a boundary right at the start of `text` is still found."""
    pattern = _BOUNDARY[granularity]
    pieces, pos = [], 0
    for m in pattern.finditer(prev + text, len(prev)):
        m = _Shifted(m, len(prev))
        if m.start() > pos:
            pieces.append({"text": text[pos:m.start()], "boundary": False})
        pieces.append({"text": m.group(), "boundary": True})
        pos = m.end()
    if pos < len(text):
        pieces.append({"text": text[pos:], "boundary": False})
    return pieces

def _op_old(op): return op.get("text", "") if op["type"] in ("equal", "remove") else op.get("old_text", "")
def _op_new(op): return op.get("text", "") if op["type"] in ("equal", "add") else op.get("new_text", "")

def _merge_ops(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    "Join consecutive equal ops."
    out = []
    for op in ops:
        if out and op["type"] == "equal" and out[-1]["type"] == "equal":
            out[-1] = {"type": "equal", "text": out[-1]["text"] + op["text"]}
        else:
            out.append(dict(op))
    return out

def ops_to_blocks(ops: List[Dict[str, Any]], granularity: str = "sentence") -> List[Dict[str, Any]]:
    """Gather word-level diff ops into reviewable blocks.

    All changes within one sentence (or clause) become a single `change` block;
    text between them is kept inside the block so it reads as a whole sentence."""
    if granularity not in _BOUNDARY:
        raise ValueError(f"granularity must be one of {list(_BOUNDARY)}")

    units, current, prev = [], [], ""
    for op in ops:
        if op["type"] != "equal":
            current.append({k: v for k, v in op.items() if k not in ("accepted", "status")})
            prev = (_op_new(op) or _op_old(op))[-1:] or prev
            continue
        text = op.get("text", "")
        pieces = _split_equal(text, granularity, prev)
        prev = text[-1:] or prev
        for piece in pieces:
            if piece["boundary"]:
                if current: units.append(current)
                units.append([{"type": "equal", "text": piece["text"]}])
                current = []
            else:
                current.append({"type": "equal", "text": piece["text"]})
    if current: units.append(current)

    blocks = []
    for unit in units:
        unit = _merge_ops(unit)
        old = "".join(_op_old(o) for o in unit)
        new = "".join(_op_new(o) for o in unit)
        changed = any(o["type"] != "equal" for o in unit)
        if not changed and blocks and blocks[-1]["type"] == "equal":
            blocks[-1]["old_text"] += old
            blocks[-1]["new_text"] += new
            blocks[-1]["ops"] = _merge_ops(blocks[-1]["ops"] + unit)
            continue
        blocks.append({
            "type": "change" if changed else "equal",
            "old_text": old,
            "new_text": new,
            "ops": unit,
            "comment": "",
            "status": "pending" if changed else "accepted",
        })
    for i, b in enumerate(blocks):
        b["id"] = str(i)
    return blocks

def compute_blocks(original: str, rewritten: str, granularity: str = "sentence") -> List[Dict[str, Any]]:
    "Diff two texts and return reviewable blocks (no LLM calls)."
    return ops_to_blocks(clean_newlines(compute_diff(original, rewritten)), granularity)

def blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    "Original text with accepted change blocks swapped for their new text."
    return "".join(b["new_text"] if b["status"] == "accepted" else b["old_text"] for b in blocks)

STATUSES = ("pending", "accepted", "rejected")

def _find(blocks, block_id):
    for i, b in enumerate(blocks):
        if b["id"] == block_id: return i
    raise KeyError(f"No block with id {block_id!r}")

def set_status(blocks: List[Dict[str, Any]], block_id: str, status: str) -> List[Dict[str, Any]]:
    "Return blocks with one change block set to `status`."
    if status not in STATUSES: raise ValueError(f"status must be one of {STATUSES}")
    i = _find(blocks, block_id)
    if blocks[i]["type"] != "change": raise ValueError("Only change blocks have a status to set")
    return blocks[:i] + [{**blocks[i], "status": status}] + blocks[i+1:]

def edit_block(blocks: List[Dict[str, Any]], block_id: str, new_text: str) -> List[Dict[str, Any]]:
    "Return blocks with one change block's suggestion replaced by `new_text`."
    i = _find(blocks, block_id)
    b = blocks[i]
    if b["type"] != "change": raise ValueError("Only change blocks can be edited")
    ops = clean_newlines(compute_diff(b["old_text"], new_text))
    return blocks[:i] + [{**b, "new_text": new_text, "ops": _merge_ops(ops)}] + blocks[i+1:]

def comment_prompt(blocks: List[Dict[str, Any]], goal: str = "") -> str:
    "Build the user prompt listing each change block."
    items = [{"id": b["id"], "before": b["old_text"], "after": b["new_text"]}
             for b in blocks if b["type"] == "change"]
    return (
        (f"The writer's goal: {goal}\n\n" if goal else "")
        + "Each item below is one edit to the writer's text. For each, write a short reason "
        "the writer can scan: what the edit does and why it helps, in under 10 words. "
        "Start with a verb, use sentence case and no full stop, and don't just repeat the new "
        "wording. Good examples: \"Fixes subject-verb agreement\", \"Cuts filler words\", "
        "\"Splits a long sentence in two\", \"More formal greeting\".\n\n"
        + json.dumps(items, indent=2, ensure_ascii=False)
        + '\n\nReturn ONLY a JSON object mapping each id to its reason, e.g. {"1": "Cuts filler words"}.'
    )

def parse_comments(content: str) -> Dict[str, str]:
    "Pull the JSON object out of an LLM reply, tolerating code fences and stray text."
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
    start, end = content.find("{"), content.rfind("}") + 1
    if start == -1 or end == 0: return {}
    data = json.loads(content[start:end])
    return {str(k): str(v).strip() for k, v in data.items()}

def apply_comments(blocks: List[Dict[str, Any]], comments: Dict[str, str]) -> List[Dict[str, Any]]:
    "Return blocks with `comment` filled in for change blocks that have one."
    return [{**b, "comment": comments.get(b["id"], b["comment"])} if b["type"] == "change" else b
            for b in blocks]

async def add_comments(
    blocks: List[Dict[str, Any]],
    api_key: str,
    goal: str = "",
    model: str = "",
) -> List[Dict[str, Any]]:
    "Ask the LLM for a one-line reason per change block. Returns blocks unchanged on failure."
    if not any(b["type"] == "change" for b in blocks): return blocks
    from text_diff.llm import DEFAULT_MODEL
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": "You explain edits to a writer. Reply with JSON only."},
            {"role": "user", "content": comment_prompt(blocks, goal)},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions",
                                  json=payload, headers=headers, timeout=60.0)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        return apply_comments(blocks, parse_comments(content))
    except Exception as e:
        print(f"Commenting failed: {e}")
        return blocks

async def improve_text(
    text: str,
    goal: str = "",
    api_key: str = "",
    model: str = "",
    comments: bool = True,
    granularity: str = "sentence",
) -> List[Dict[str, Any]]:
    """Rewrite `text` towards `goal` and return reviewable blocks.

    One LLM call for the rewrite, plus one for comments when `comments=True`."""
    import os
    from text_diff.llm import get_llm_rewrite
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key: raise ValueError("No API key: pass api_key or set OPENROUTER_API_KEY.")
    rewritten = await get_llm_rewrite(goal, text, api_key, model)
    blocks = compute_blocks(text, rewritten, granularity)
    if comments: blocks = await add_comments(blocks, api_key, goal, model)
    return blocks
