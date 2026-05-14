---
name: miro-board-dossier
description: Use when asked to understand, summarize, audit, document, or hand off a Miro board from SVG/JPG/PDF/MCP context, especially product flows, architecture maps, journey maps, status diagrams, decision trees, funnels, or backlog boards.
---

# Miro Board Dossier

## Overview

Use this skill to turn a Miro board into a durable context dossier before product, architecture, implementation, review, or planning work. Prefer exported SVG when available because it can expose real text, coordinates, and connector paths.

Source priority: SVG first, JPG/PNG second for visual checking, live Miro/MCP as optional confirmation.

## Best Input Contract

Ask for:

- SVG export of the relevant Miro area
- PNG/JPG of the same area when available
- Miro URL when MCP confirmation is useful
- any human notes that explain the purpose of the board

If the user controls the board, ask them to make important frame titles visible as text widgets before export.

## Workflow

1. Inspect the SVG before summarizing:

```bash
file "board.svg"
rg -n "<text|<path|<image|STATUS|API|CTA|HANDOFF|Decision|Journey" "board.svg"
```

2. Generate a Board Dossier:

```bash
python3 scripts/extract_miro_svg.py "board.svg" --dossier-dir .miro/svg-specs
```

When installed with the Skills CLI, resolve `scripts/extract_miro_svg.py` relative to this `SKILL.md` directory.

3. Read the generated files in this order:

- `board-dossier.md`
- `agent-handoff.md`
- `visual-map.md`
- `narrative.md`
- `domain-model.md`
- `decisions-and-ambiguities.md`
- `raw-nodes.json` and `raw-edges.json` when exact evidence matters

4. Cross-check visually with JPG/PNG/SVG:

- arrow direction
- dense areas and tiny status pills
- colors, lanes, grouping, repeated labels
- raster image areas that may hide text

5. Use Miro MCP only as confirmation unless it clearly returns richer structure:

- confirm item/frame existence
- retrieve comments, documents, tables, or frame summaries not present in SVG
- never override SVG evidence with a vague MCP overview without explaining why

6. Answer with this contract:

- what the board represents
- how the board is visually organized
- main flow in order
- decision branches and outcomes
- actors, systems, entities, statuses, screens, APIs, or events visible on the board
- what is observed vs inferred
- visible inconsistencies or likely copy/paste errors
- confidence level and open ambiguities
- handoff notes for the next agent/task

## Board Dossier Files

| File | Purpose |
|---|---|
| `index.json` | Source, stats, confidence signals, generated files |
| `raw-nodes.json` | Extracted text nodes and coordinates |
| `raw-edges.json` | Connector candidates and inferred edges |
| `board-dossier.md` | Complete human-readable board overview |
| `visual-map.md` | Spatial organization and reading order |
| `narrative.md` | Inferred flow scaffold |
| `domain-model.md` | Generic status/entity/action/decision signals |
| `decisions-and-ambiguities.md` | Warnings, repeated labels, uncertain edges, disconnected nodes |
| `agent-handoff.md` | Instructions for downstream agents |
| `flow.mmd` | Mermaid graph from inferred edges |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Treating a screenshot as enough | Use SVG when possible, JPG/PNG only for visual checking |
| Trusting every inferred arrow | Mark connector direction as inferred until visually checked |
| Collapsing repeated statuses | Keep each repeated label tied to position/lane/provider/context |
| Ignoring raster warnings | Tell the user when text may be hidden inside images |
| Letting MCP replace SVG evidence | Use MCP for confirmation or missing metadata, not vague overrides |
| Giving final architecture too early | First separate observed labels from interpretation and assumptions |

## Core Principle

The dossier is evidence, not magic. A good answer uses it to explain the board clearly while preserving uncertainty where the board itself is ambiguous.
