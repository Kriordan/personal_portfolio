# Learning Card Quick Reference

Quick reference for learning card formats.

Output a minimal JSON snippet for each card type (qa, incident, cloze, command, code_diff)
so I can copy/paste into an existing note. Keep it short and consistent.

Format examples:
{
  "id": "qa-1",
  "question": "...",
  "answer": "...",
  "tags": ["tag1"]
}

{
  "id": "inc-1",
  "type": "incident",
  "title": "...",
  "symptom": "...",
  "root_cause": "...",
  "fix": "...",
  "prevention": "...",
  "tags": ["tag1", "tag2"]
}

{
  "id": "cloze-1",
  "type": "cloze",
  "text": "Use {{c1::value}} for ...",
  "tags": ["tag1"]
}

{
  "id": "cmd-1",
  "type": "command",
  "prompt": "...",
  "answer": "...",
  "tags": ["tag1"]
}

{
  "id": "diff-1",
  "type": "code_diff",
  "prompt": "...",
  "before": "...",
  "after": "...",
  "tags": ["tag1"]
}
