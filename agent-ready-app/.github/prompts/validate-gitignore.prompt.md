---
name: Validate Gitignore
description: Scans the codebase to identify missing or incorrect entries in the .gitignore file.
---
Scan the codebase and analyze the current project stack (e.g., frontend frameworks, backend languages, IDEs, testing tools). 

Then, review the `.gitignore` file and determine if there are any necessary updates. Specifically, look for:
1. **Missing entries** that are standard for the detected stack (e.g., `node_modules`, `__pycache__`, coverage reports, IDE folders like `.vscode` or `.idea`).
2. **Incorrect entries** that should not be ignored (e.g., lock files that are intentionally committed, unless project rules specify otherwise).

Please take the following steps:
1. Use terminal commands like `git status --short --ignored` and `git status --short` to see what is currently untracked or ignored.
2. Read the current `.gitignore` file.
3. If updates are needed, use the appropriate edit tools to update the `.gitignore` file directly.
4. Provide a concise summary of the changes made and why they were necessary.