# Create Learning Note

Create a learning note from this chat session.

Analyze the key concepts and output JSON to `notes/<topic-slug>.json`.

Card type guidelines:

- **qa**: For conceptual knowledge ("What is X?", "Why does Y happen?")
- **cloze**: For specific facts, syntax, or values ("Use {{c1::timestamptz}} for...")
- **command**: For CLI commands or code snippets to memorize
- **code_diff**: For before/after code changes

Include:

- 5-10 flashcards mixing types for variety
- Relevant tags at note level
- Per-card tags for specific subtopics

Format:
{
  "id": "topic-slug",
  "title": "Topic Title",
  "created_at": "YYYY-MM-DD",
  "tags": ["tag1", "tag2"],
  "summary": "<2-3 sentence summary>",
  "flashcards": [
    {"id": "topic-qa-1", "question": "...", "answer": "...", "tags": ["tag1"]},
    {"id": "topic-cloze-1", "type": "cloze", "text": "Use {{c1::value}} for...", "tags": ["tag2"]},
    {"id": "topic-cmd-1", "type": "command", "prompt": "...", "answer": "...", "tags": ["tag1"]},
    {"id": "topic-diff-1", "type": "code_diff", "prompt": "...", "before": "...", "after": "...", "tags": ["tag2"]}
  ]
}
