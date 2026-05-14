# AGENTS.md

## Scope

This repo contains a small Codex/Agent skill plus a Python helper for reading Miro SVG exports.

## Working Style

- Keep the project dependency-light; the helper should use Python standard library unless a strong reason exists.
- Treat SVG extraction as evidence, not a guaranteed source of truth.
- Preserve the skill's SVG-first workflow: SVG primary, JPG/PNG visual check, live Miro/MCP optional.
- Add tests for parser or inference behavior changes.
- Do not add broad framework or packaging machinery unless it is needed for a real release path.

## Verification

Run:

```bash
python3 -m unittest discover -s tests
```

For a real exported Miro file, also smoke-test:

```bash
python3 scripts/extract_miro_svg.py "path/to/board.svg" --format markdown
```
