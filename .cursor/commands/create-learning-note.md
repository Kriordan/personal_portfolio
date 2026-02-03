# Create or Extend Learning Note

Create a learning note from this chat session.

Analyze the key concepts and output JSON to `notes/<topic-slug>.json`.

Before writing the note:

1. Check if `notes/<topic-slug>.json` already exists.
2. If it exists, read it and keep:
   - `id`, `title`, `created_at`, `tags`, `summary` (unless you are improving it)
   - All existing flashcards exactly as-is (do not edit or rename card IDs)
3. Generate new cards that **extend** the note without duplicating existing ones.
   - Avoid duplicates by comparing the question/answer or prompt/response text.
   - Use new unique IDs that continue the existing sequence
     (e.g., if `topic-qa-7` exists, start at `topic-qa-8`).
4. Output the **merged** JSON with both old and new cards.

Card type guidelines:

- **qa**: For conceptual knowledge ("What is X?", "Why does Y happen?")
- **cloze**: For specific facts, syntax, or values ("Use {{c1::timestamptz}} for...")
- **command**: For CLI commands or code snippets to memorize
- **code_diff**: For before/after code changes

Include:

- If creating a new note: 5-10 flashcards mixing types for variety
- If extending an existing note: 3-6 additional flashcards
- Relevant tags at note level
- Per-card tags for specific subtopics
- A **comprehensive summary** using basic markdown (headings, lists, inline code)
  - 2-4 short paragraphs
  - Cover key concepts, pitfalls, and practical usage

Format:
{
"id": "topic-slug",
"title": "Topic Title",
"created_at": "YYYY-MM-DD",
"tags": ["tag1", "tag2"],
"summary": "## Overview\nShort overview...\n\n## Key Concepts\n- `timestamptz` stores...\n\n## Common Pitfalls\n- Don't use `timestamp without time zone`...",
"flashcards": [
{"id": "topic-qa-1", "question": "...", "answer": "...", "tags": ["tag1"]},
{"id": "topic-cloze-1", "type": "cloze", "text": "Use {{c1::value}} for...", "tags": ["tag2"]},
{"id": "topic-cmd-1", "type": "command", "prompt": "...", "answer": "...", "tags": ["tag1"]},
{"id": "topic-diff-1", "type": "code_diff", "prompt": "...", "before": "...", "after": "...", "tags": ["tag2"]}
]
}
