Create an incident learning note from this debugging session.

Extract:
1. Symptom (what you observed)
2. Root cause (why it happened)
3. Fix (what you changed)
4. Prevention (tests/checks to add)

Output JSON to `notes/<incident-slug>.json` with:
- 1 incident card capturing the core lesson
- 2-4 supporting qa/cloze cards for key details
- Relevant tags

Format:
{
  "id": "<incident-slug>",
  "title": "<Incident Title>",
  "created_at": "<YYYY-MM-DD>",
  "tags": ["tag1", "tag2"],
  "summary": "<summary>",
  "flashcards": [
    {
      "id": "<incident-slug>-inc-1",
      "type": "incident",
      "title": "<Incident Title>",
      "symptom": "...",
      "root_cause": "...",
      "fix": "...",
      "prevention": "...",
      "tags": ["tag1", "tag2"]
    },
    {
      "id": "<incident-slug>-qa-1",
      "type": "qa",
      "question": "...",
      "answer": "...",
      "tags": ["tag1"]
    }
  ]
}
