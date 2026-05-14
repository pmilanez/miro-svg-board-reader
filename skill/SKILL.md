---
name: miro-svg-board-reading
description: Use when asked to understand, summarize, audit, or document a Miro board from exported SVG/JPG/PDF files, including product flows, journey maps, status diagrams, handoffs, decision trees, or funnels.
---

# Miro SVG Board Reading

## Overview

Use exported SVG as the primary source when it contains real `<text>` and vector `<path>` elements. Reconstruct product meaning from labels, coordinates, arrows, branches, states, colors, lanes, and grouping.

Source priority: SVG first, JPG second, live Miro/MCP optional.

## Best Input Contract

Ask for the Miro SVG export in Vector quality, a JPG/PNG of the same area for visual cross-checking, and any known board purpose. If the user controls the board, ask them to make frame titles visible as text widgets before export.

## Workflow

1. Inspect the SVG structure before summarizing:

```bash
file "board.svg"
rg -n "<text|<path|<image|JOURNEY|STATUS|API|CTA|HANDOFF" "board.svg"
```

2. Run the extraction helper:

```bash
python3 ~/.codex/skills/miro-svg-board-reading/scripts/extract_miro_svg.py "board.svg" --format markdown
```

3. Cross-check visually with the JPG/SVG image:

- arrows and branch direction
- dense areas and tiny status pills
- colors, lanes, grouping, repeated labels
- text embedded as raster images

4. Reconstruct the flow:

- read left-to-right and top-to-bottom unless arrows prove otherwise
- identify entry points, actions, decisions, outcomes, terminal states
- separate system steps from user-facing screens
- group statuses by lane/provider/channel
- mark inferred edges as inferred when connector confidence is not obvious

5. Answer with this contract:

- what the board represents
- main flow in order
- decision branches and outcomes
- statuses/entities/tables involved
- visible inconsistencies or likely copy-paste errors
- confidence level and what remains ambiguous

## Quick Reference

| Signal | Meaning |
|---|---|
| `<text>` nodes | Machine-readable labels; trust before OCR |
| `<path>` lines | Possible connectors/arrows; verify visually |
| `<image>` nodes | Raster content; may hide unreadable text |
| colors/lane placement | Semantic grouping, not proof by itself |
| duplicate labels | Need IDs/positions to avoid collapsing states |
| missing connectors | Do not invent flow; say where inference starts |

## Helper Output

`scripts/extract_miro_svg.py` emits nodes, connector candidates, inferred edges, and warnings for embedded raster images or missing text/connectors. Use helper output as evidence, not final truth. Miro exports visual drawings, not a guaranteed graph schema.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Using MCP overview as truth when SVG is available | Treat MCP as optional context only |
| Summarizing from JPG alone | Use JPG only after extracting SVG text |
| Collapsing repeated statuses like TERMINATED/ABANDONED | Keep provider/lane/position context |
| Trusting every inferred edge | Cross-check arrowheads and line endpoints visually |
| Ignoring export limitations | State when frame titles, comments, or raster text may be missing |
| Giving a polished answer without uncertainty | Separate observed labels from inferred product meaning |

## References

Miro export docs: vector SVG/PDF preserves quality; CSV loses relationships. W3C SVG docs: SVG is XML with vector shapes, images, and searchable/selectable text.
