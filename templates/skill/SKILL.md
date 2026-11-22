---
name: your-skill-name
description: One or two sentences on WHAT the skill does (name the concrete checks, tools and outputs) followed by WHEN to use it. Use when the user asks to ... or mentions ..., ... (list the phrases and file names that should trigger it). Max 1024 characters.
license: MIT
compatibility: Python 3.8+. Mention required tools and versions (pytest 8, Vitest 3, PHPUnit 10) here, or delete this line.
metadata:
  author: Your Name
  version: "0.1.0"
---

# Your skill title

One or two sentences on the goal and the main rule (for example: work from the reports the
tools already produce; ask before editing CI or running long jobs).

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- Concrete user requests that should trigger this skill
- Files, reports or error messages that indicate it

## When not to use

- Neighbouring problems and which skill or tool fits them better

## Workflow

1. **Detect the stack.** Which config files to read (pyproject.toml, package.json,
   phpunit.xml) and what to ask before running anything.
2. **Run the helper (read-only).**
   ```bash
   python3 scripts/your_script.py INPUT
   python3 scripts/your_script.py INPUT --json
   ```
3. **Interpret.** Decision points; link details in [references/details.md](references/details.md).
4. **Propose changes** (tests, config); ask before editing CI or running long jobs.
5. **Verify** with an exact command (rerun the tests, rerun the script).

## Output

A short example of the report the agent should return.
