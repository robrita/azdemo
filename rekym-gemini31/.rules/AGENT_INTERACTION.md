# Agent Interaction

Rules for how agents capture human input and ask clarifying questions.

## Core Rule

**Never use checkbox, radio button, picker, or any non-text UI element to capture human input.** All agent-to-human interaction must be plain text.

## Why

- Options UI (quick-pick dialogs, checkbox lists, radio selectors) is unreliable — it can disappear when switching sessions or editor tabs.
- Text-based interaction is universally compatible across all editors, terminals, and chat interfaces.
- Plain text responses are auditable and persist in conversation history.

## How to Ask Clarifying Questions

When you need the user to choose between options, present them as a **numbered list in plain text** and ask the user to reply with a number or free-form text.

```markdown
# ✅ CORRECT: Plain text with numbered options

I need to know which approach you'd prefer:

1. Create a new service layer with dedicated endpoints
2. Extend the existing ticket service with additional methods
3. Use a background worker for async processing

Reply with a number or describe your preference.
```

```markdown
# ❌ WRONG: Using UI-based selection tools

Do not use ask_questions, quick-pick dialogs, checkbox groups,
radio buttons, or any tool that renders a non-text selection UI.
These are unreliable and may not persist in conversation history.
```

## Rules

1. **Always use plain text** — present options as numbered items in the chat message
2. **Never use UI selection tools** — no checkboxes, radio buttons, dropdowns, or picker dialogs
3. **Keep questions concise** — batch related questions; limit to 1–3 questions per message
4. **Always provide a recommended option** — every list of options must include a clearly marked recommendation (e.g., "**(recommended)**") with a one-line rationale citing project conventions, security best practices, or software-engineering best practices. Never present bare options without guidance.
5. **Accept flexible replies** — allow the user to respond with a number, a keyword, or a free-form description
