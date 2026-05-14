# Board Dossier v0.2 Design

## Goal

Turn any exported Miro SVG board into a domain-agnostic Board Dossier that gives future agents enough structured context to understand what the board represents, how it is organized, what content is visible, what is inferred, and what remains ambiguous.

## Scope

The v0.2 scope extends the existing SVG extraction helper. It must keep the current markdown/json extraction behavior and add a dossier generation mode that writes reusable local artifacts under a caller-provided directory such as `.miro/svg-specs/`.

This remains domain-agnostic. It must not assume Financial Partner, WhatsApp, status architecture, product funnels, or any specific business vocabulary. Domain-specific meaning is derived from visible labels and organized as evidence, not hardcoded product logic.

## Output Contract

Given `board.svg` and `--dossier-dir .miro/svg-specs`, the helper creates `.miro/svg-specs/board/` with:

- `index.json`: source, generated timestamp, stats, file list, and confidence signals.
- `raw-nodes.json`: machine-readable extracted nodes.
- `raw-edges.json`: connector candidates and inferred edges.
- `board-dossier.md`: complete human-readable dossier with board identity, visual map, evidence, narrative scaffold, domain model, decisions, ambiguities, and agent handoff.
- `visual-map.md`: layout-oriented reading order and spatial groups.
- `narrative.md`: flow-oriented reading in plain language using observed labels and inferred edges.
- `domain-model.md`: visible concepts, entities, status-like labels, actor/system-like labels, and action-like labels.
- `decisions-and-ambiguities.md`: inferred edges, repeated labels, warnings, disconnected nodes, and other items the agent must not over-assume.
- `agent-handoff.md`: concise instructions for a downstream agent using this board.
- `flow.mmd`: Mermaid flowchart from inferred edges.

## Interpretation Rules

- SVG text and coordinates are evidence.
- Connector direction is inferred unless visually confirmed.
- Repeated labels must keep positional context.
- Missing MCP data does not invalidate SVG evidence.
- Raster images inside SVG are a warning because hidden text may not be extractable.
- The dossier can scaffold interpretation, but the consuming agent must still separate observed labels from inferred product meaning.

## Success Criteria

- The existing extraction command remains backward-compatible.
- The new dossier command writes all expected files.
- The generated dossier contains enough structure for another agent to inspect board identity, layout, raw evidence, narrative, domain model, decisions, ambiguities, and handoff without reopening the SVG immediately.
- The Skills CLI packaging continues to install `SKILL.md` and `scripts/extract_miro_svg.py` together.
