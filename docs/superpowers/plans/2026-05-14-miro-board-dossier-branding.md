# Miro Board Dossier Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename and reposition the project as Miro Board Dossier for non-technical agent users.

**Architecture:** Keep the Python helper behavior unchanged. Rename the skill package, update docs/tests/install paths, replace the header SVG, publish through PR, then rename/protect the GitHub repository.

**Tech Stack:** Markdown, SVG, Python standard library tests, GitHub CLI/API, Skills CLI.

---

### Task 1: Rename Skill Package

**Files:**
- Move: `skills/miro-svg-board-reading/` to `skills/miro-board-dossier/`
- Modify: `skills/miro-board-dossier/SKILL.md`
- Modify: `tests/test_extract_miro_svg.py`
- Modify: `tests/test_skill_packaging.py`

- [ ] Change the skill frontmatter name to `miro-board-dossier`.
- [ ] Update tests to use the new path.
- [ ] Run `python3 -m unittest discover -s tests` and verify failures only reflect old names before implementation, then pass after edits.

### Task 2: Rewrite User-Friendly README

**Files:**
- Modify: `README.md`

- [ ] Replace technical-first copy with agent-user-first copy.
- [ ] Keep install and advanced CLI commands.
- [ ] Explain the Board Dossier output in plain language.

### Task 3: Replace Header Image

**Files:**
- Modify: `docs/assets/header.svg`

- [ ] Replace the old "Miro SVG Board Reader" header with a "Miro Board Dossier" header.
- [ ] Validate the SVG parses and can render via macOS preview tooling when available.

### Task 4: Publish, Rename Repo, Protect Main

**Files/Services:**
- GitHub repo currently `pmilanez/miro-svg-board-reader`
- Target repo `pmilanez/miro-board-dossier`

- [ ] Commit branch and push.
- [ ] Open PR, merge after validations.
- [ ] Rename repository to `miro-board-dossier`.
- [ ] Enable issues and PRs.
- [ ] Add branch protection/rules so `main` changes require PR and direct pushes are restricted where supported.
- [ ] Install the published skill locally through `npx skills`.
