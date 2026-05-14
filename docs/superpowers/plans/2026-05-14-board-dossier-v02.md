# Board Dossier v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned Board Dossier output mode that turns any Miro SVG export into reusable local context for downstream agents.

**Architecture:** Keep the current parser as the source of truth for nodes, connectors, inferred edges, and warnings. Add a dossier writer that derives layout, concept, ambiguity, Mermaid, and handoff artifacts from that extraction data without hardcoding any product domain.

**Tech Stack:** Python standard library, `unittest`, existing Skills CLI-compatible repository layout.

---

### Task 1: Lock Dossier Contract With Tests

**Files:**
- Modify: `tests/test_extract_miro_svg.py`

- [x] **Step 1: Add a failing test for dossier generation**

Add a test that runs:

```bash
python3 skills/miro-svg-board-reading/scripts/extract_miro_svg.py board.svg --format json --dossier-dir specs
```

Expected files:

```text
specs/board/index.json
specs/board/raw-nodes.json
specs/board/raw-edges.json
specs/board/board-dossier.md
specs/board/visual-map.md
specs/board/narrative.md
specs/board/domain-model.md
specs/board/decisions-and-ambiguities.md
specs/board/agent-handoff.md
specs/board/flow.mmd
```

- [x] **Step 2: Run the new test and verify RED**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_extract_miro_svg.py'
```

Expected: fail because `--dossier-dir` is not implemented.

### Task 2: Implement Dossier Writer

**Files:**
- Modify: `skills/miro-svg-board-reading/scripts/extract_miro_svg.py`

- [x] **Step 1: Add helpers**

Add helpers for slug generation, reading order, repeated label detection, keyword-based concept grouping, ambiguity detection, Mermaid rendering, and markdown rendering.

- [x] **Step 2: Add CLI argument**

Add:

```python
parser.add_argument("--dossier-dir", type=Path, help="Write a reusable Board Dossier under this directory")
```

- [x] **Step 3: Write files**

When `--dossier-dir` is set, write the full dossier directory while preserving stdout behavior for `--format markdown/json`.

- [x] **Step 4: Run tests and verify GREEN**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: all tests pass.

### Task 3: Update Skill and README

**Files:**
- Modify: `skills/miro-svg-board-reading/SKILL.md`
- Modify: `README.md`
- Modify: `tests/test_skill_packaging.py`

- [x] **Step 1: Document Board Dossier as default maximum-context workflow**

Show the `--dossier-dir .miro/svg-specs` command and explain the dossier files.

- [x] **Step 2: Keep Skills CLI packaging documented**

Keep `npx skills add pmilanez/miro-svg-board-reader --skill miro-svg-board-reading`.

- [x] **Step 3: Run packaging validation**

Run:

```bash
npx skills add . --list
```

Expected: finds `miro-svg-board-reading`.

### Task 4: Publish and Sync

**Files:**
- GitHub branch: `support-vercel-skills-flow`
- Local Codex global skills directory managed by `npx skills`

- [x] **Step 1: Commit and push**

Run:

```bash
git add -A
git commit -m "Add Board Dossier output"
git push
```

- [x] **Step 2: Sync local Codex skill**

Run:

```bash
npx skills add . --skill miro-svg-board-reading -g -a codex --copy -y
```

Expected: global Codex skill contains `SKILL.md` and `scripts/extract_miro_svg.py`.
