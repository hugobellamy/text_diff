# Text Iterator: library interface (v1)

The `text_diff` library is the engine and the website is just one client. This doc pins down
what any UI can rely on, so the later UI overhaul only has to change how things look.

## The core idea: a block
A **block** is the unit a person reviews. Every change inside one sentence (or clause) is
gathered into one block, which is accepted or rejected as a whole. The word-level edits are
still inside it, so a UI can highlight them.

```json
{
  "id": "0",
  "type": "change",                 // "equal" (unchanged) or "change"
  "old_text": "Our team have been working really hard on the new release.",
  "new_text": "Our team has worked hard on the new release.",
  "ops": [                          // word-level detail, for inline highlighting only
    {"type": "equal", "text": "Our team "},
    {"type": "replace", "old_text": "have been working really", "new_text": "has worked"},
    {"type": "equal", "text": " hard on the new release."}
  ],
  "comment": "Tighter, correct verb agreement",   // "" when comments are off
  "status": "pending"               // "pending" | "accepted" | "rejected"; equal blocks are always "accepted"
}
```

Guarantees:
- Joining every block's `old_text` gives back the original text exactly, and joining every
  `new_text` gives the full rewrite. Whitespace and newlines are preserved.
- Paragraph breaks are always block boundaries.
- Changes that are only whitespace are accepted automatically and never shown as blocks.
- A block is always JSON-serialisable, so it can go over HTTP unchanged.

## Calls

| Call | LLM calls | What it does |
|---|---|---|
| `compute_blocks(original, rewritten, granularity="sentence")` | 0 | Diffs two texts into blocks. `granularity` is `"sentence"` or `"clause"`. |
| `await improve_text(text, goal="", comments=True, granularity="sentence", model="", api_key="")` | 1 or 2 | Rewrites towards `goal`, then returns blocks, with comments if asked. |
| `await add_comments(blocks, api_key, goal="", model="")` | 1 | Fills in `comment` on change blocks. If it fails, you get the blocks back unchanged. |
| `set_status(blocks, id, status)` | 0 | Marks a change block `"pending"`, `"accepted"` or `"rejected"`. |
| `edit_block(blocks, id, new_text)` | 0 | Lets the user tweak a suggestion before accepting it. The word-level `ops` are recomputed so highlighting still matches. |
| `blocks_to_text(blocks)` | 0 | Returns the text with accepted blocks applied and pending or rejected ones left as the original. This is the input for the next round. |

The helpers return a new list and never change the one passed in. Blocks are plain dicts,
so a UI in another language can do the same thing just by setting the fields.

A round looks like this: `improve_text`, then the user accepts, rejects or edits blocks, then
`blocks_to_text`, then the next `improve_text`. Comments are on by default.

This replaces the old pipeline, which made a word diff, cleaned it, grouped it with an extra
LLM call and returned per-op `accepted` flags. The old functions stay in place for now, so the
current website keeps working until it switches over.

## Proposed website backend (stateless)
- `POST /suggest {text, goal, comments, granularity}` returns `{blocks}`
- `POST /comment {blocks, goal}` returns `{blocks}`, for comments added after the fact

The browser holds the blocks and the user's decisions, and works out the final text itself
(or calls `blocks_to_text`). Nothing is stored on the server between requests, so the old
`DocumentState`/undo history can move to the client.

## Decisions (Hugo, 11 Oct)
1. Blocks have three states: `pending`, `accepted` and `rejected`.
2. Users can edit a suggestion before accepting it (`edit_block`).
3. Comments are on by default.
4. The old pipeline (`process_diff`, `llm_semantic_grouping`, `request_text_improvement`,
   `group.py`, `DocumentState`) gets removed once the website has switched to blocks.
