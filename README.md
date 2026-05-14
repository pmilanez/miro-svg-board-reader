<p align="center">
  <img src="docs/assets/header.svg" alt="Miro SVG Board Reader" width="100%">
</p>

# Miro SVG Board Reader

Turn exported Miro SVG boards into structured evidence that AI agents can actually reason about.

Miro boards are great for product flows, journey maps, and decision diagrams, but a live board API or a JPG export often loses the structure that matters: labels, coordinates, arrows, branches, repeated states, and visual grouping. This project uses the SVG export as the primary source because SVG can preserve machine-readable text and vector paths.

## What it does

- extracts text nodes from a Miro-exported SVG
- groups multi-line labels into board nodes
- detects simple connector paths
- infers likely edges between nearby nodes
- warns when embedded raster images may hide unreadable text
- includes a Codex/Agent skill that teaches the workflow: SVG first, JPG second, live Miro/MCP optional

The output is evidence, not magic. Miro exports a visual drawing, not a guaranteed process graph, so final interpretation should still cross-check arrowheads, lanes, colors, and dense areas visually.

## Quick start

```bash
git clone https://github.com/pmilanez/miro-svg-board-reader.git
cd miro-svg-board-reader

python3 skills/miro-svg-board-reading/scripts/extract_miro_svg.py "path/to/board.svg" --format markdown
python3 skills/miro-svg-board-reading/scripts/extract_miro_svg.py "path/to/board.svg" --format json
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

No third-party Python packages are required.

## Install with the Skills CLI

```bash
npx skills add pmilanez/miro-svg-board-reader --list
npx skills add pmilanez/miro-svg-board-reader --skill miro-svg-board-reading
```

For a global Codex install:

```bash
npx skills add pmilanez/miro-svg-board-reader --skill miro-svg-board-reading -g -a codex -y
```

The skill is packaged in `skills/miro-svg-board-reading/`, so `npx skills` installs the instructions and the helper script together. Start a new Codex session so the skill inventory can reload.

Update later:

```bash
npx skills update miro-svg-board-reading -g
```

## Recommended Miro export flow

1. Export the relevant board area as **SVG / Vector quality**.
2. Export the same area as JPG or PNG for visual cross-checking.
3. Ask the agent to use the SVG as the primary source.
4. Use live Miro/MCP only to confirm item existence, not as the main flow source.

If you control the Miro board, make important frame titles visible as text widgets before export.

## Example output

```text
# Miro SVG Extraction: board.svg

- nodes: 48
- connectors: 40
- inferred_edges: 39

## Nodes
| id | x | y | label |
|---|---:|---:|---|
| n001 | 110.99 | 188.82 | API de referral |

## Inferred Edges
| id | confidence | from | to |
|---|---|---|---|
| c006 | high | API de referral | Criação customer no FP |
```

## Limitations

- Curved or complex connector paths may not infer perfectly.
- Arrow direction should be visually checked.
- Repeated labels need position/lane context.
- Raster images inside SVG can hide text from extraction.
- Frame titles, comments, and some Miro metadata may not be present in the SVG export.

## Why SVG

SVG is XML for vector graphics. When Miro exports real `<text>` and `<path>` elements, agents can inspect labels and geometry directly instead of relying on OCR or incomplete board summaries.

## License

MIT
