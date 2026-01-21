Create a learning note from this chat session.

Output a JSON file to `notes/<topic-slug>.json` with:
- A concise summary (2-3 sentences)
- 5-10 Q/A flashcards testing key concepts
- Relevant tags

Format:
{
  "id": "<topic-slug>",
  "title": "<Topic Title>",
  "created_at": "<YYYY-MM-DD>",
  "tags": ["tag1", "tag2"],
  "summary": "<summary>",
  "flashcards": [
    {"id": "<slug>-1", "question": "...", "answer": "..."}
  ]
}
