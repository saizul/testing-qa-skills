# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## What counts as a vulnerability

These skills are run by AI agents inside real repositories and CI pipelines, so unsafe
behaviour is treated like a code vulnerability:

- A script that modifies source files, overwrites files without `--force`, or runs a
  command not documented in its `--help` (the only external command is a read-only
  `git diff`)
- A script that prints or copies secrets from its inputs (cookies or tokens in HAR files,
  credentials in reports) beyond what the user asked to see
- Command injection: crafted inputs (JUnit XML, coverage reports, HAR files, OpenAPI
  documents, spec files, git refs) that make a script execute something
- Unsafe parsing: XML or JSON inputs that cause unbounded resource use beyond the
  protections of Python's standard library parsers
- A `SKILL.md` workflow that tells the agent to change CI configuration, push, delete
  data or write to shared environments without asking the user first
- Generated code (test data builders) that embeds input values in a way that executes code

A check that misses a problem (false negative) is a normal bug: please open an issue.

## Reporting

Please **do not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/saizul/testing-qa-skills/security/advisories/new)
with the affected skill, version, impact and steps to reproduce. Redact hostnames,
tokens and any personal data from examples.

You will get an answer within 5 working days. Fixes are released as soon as possible and
credited in the changelog unless you prefer otherwise.
