#!/usr/bin/env python3
"""Extract readable structure from a Miro SVG export.

This helper is intentionally heuristic: Miro exports visual SVG, not a product
flow schema. It turns machine-readable text, positions, and simple arrow paths
into evidence an agent can inspect before summarizing the board.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TRANSLATE_RE = re.compile(r"translate\(\s*([-+]?\d*\.?\d+)[,\s]+([-+]?\d*\.?\d+)\s*\)")
POINT_RE = re.compile(r"[ML]\s*([-+]?\d*\.?\d+)[,\s]+([-+]?\d*\.?\d+)", re.I)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_number(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    cleaned = value.strip().replace("px", "")
    try:
        return float(cleaned)
    except ValueError:
        return default


def parse_translate(transform: str | None) -> tuple[float, float]:
    if not transform:
        return (0.0, 0.0)
    x_total = 0.0
    y_total = 0.0
    for match in TRANSLATE_RE.finditer(transform):
        x_total += float(match.group(1))
        y_total += float(match.group(2))
    return (x_total, y_total)


def normalize_text(text: str) -> str:
    compact = " ".join(text.replace("\xa0", " ").split())
    compact = re.sub(r"\s+:", ":", compact)
    return re.sub(r":(?=[^\s/])", ": ", compact)


@dataclass
class Ancestor:
    elem: ET.Element
    tx: float
    ty: float
    abs_x: float
    abs_y: float


@dataclass
class TextLine:
    text: str
    x: float
    y: float
    width: float


@dataclass
class NodeDraft:
    elem: ET.Element
    x: float
    y: float
    width: float
    height: float
    lines: list[TextLine] = field(default_factory=list)


def collect_nodes(root: ET.Element) -> list[dict[str, Any]]:
    groups: dict[int, NodeDraft] = {}

    def visit(elem: ET.Element, ancestors: list[Ancestor], abs_x: float, abs_y: float) -> None:
        tx, ty = parse_translate(elem.attrib.get("transform"))
        current_abs_x = abs_x + tx
        current_abs_y = abs_y + ty
        current = Ancestor(elem=elem, tx=tx, ty=ty, abs_x=current_abs_x, abs_y=current_abs_y)
        path = ancestors + [current]

        if local_name(elem.tag) == "text":
            text = normalize_text("".join(elem.itertext()))
            if text:
                owner = next(
                    (
                        item
                        for item in reversed(path)
                        if local_name(item.elem.tag) == "g"
                        and "width" in item.elem.attrib
                        and "height" in item.elem.attrib
                    ),
                    current,
                )
                owner_id = id(owner.elem)
                draft = groups.get(owner_id)
                if draft is None:
                    draft = NodeDraft(
                        elem=owner.elem,
                        x=owner.abs_x,
                        y=owner.abs_y,
                        width=parse_number(owner.elem.attrib.get("width")),
                        height=parse_number(owner.elem.attrib.get("height")),
                    )
                    groups[owner_id] = draft
                draft.lines.append(
                    TextLine(
                        text=text,
                        x=current_abs_x + parse_number(elem.attrib.get("x")),
                        y=current_abs_y + parse_number(elem.attrib.get("y")),
                        width=parse_number(
                            elem.attrib.get("textLength"),
                            default=parse_number(elem.attrib.get("width"), default=len(text) * 6.0),
                        ),
                    )
                )

        for child in list(elem):
            visit(child, path, current_abs_x, current_abs_y)

    visit(root, [], 0.0, 0.0)

    nodes: list[dict[str, Any]] = []
    for index, draft in enumerate(
        sorted(groups.values(), key=lambda item: (item.x, item.y, item.height, item.width)),
        start=1,
    ):
        label = compose_label(draft.lines)
        if not label:
            continue
        width = draft.width or max((len(label) * 6.0), 1.0)
        height = draft.height or 20.0
        nodes.append(
            {
                "id": f"n{index:03d}",
                "label": label,
                "x": round(draft.x, 2),
                "y": round(draft.y, 2),
                "width": round(width, 2),
                "height": round(height, 2),
                "center": [round(draft.x + width / 2, 2), round(draft.y + height / 2, 2)],
            }
        )
    return nodes


def compose_label(lines: list[TextLine]) -> str:
    if not lines:
        return ""

    rows: list[list[TextLine]] = []
    for line in sorted(lines, key=lambda item: (item.y, item.x)):
        if rows and abs(rows[-1][0].y - line.y) <= 2.0:
            rows[-1].append(line)
        else:
            rows.append([line])

    rendered_rows: list[str] = []
    for row in rows:
        parts = sorted(row, key=lambda item: item.x)
        rendered = parts[0].text
        previous = parts[0]
        for part in parts[1:]:
            previous_end = previous.x + (previous.width or len(previous.text) * 6.0)
            gap = part.x - previous_end
            separator = " " if gap > 4.0 else ""
            rendered += separator + part.text
            previous = part
        rendered_rows.append(rendered)
    return normalize_text(" ".join(rendered_rows))


def parse_line_points(d: str) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in POINT_RE.findall(d)]


def collect_connectors(root: ET.Element) -> list[dict[str, Any]]:
    connectors: list[dict[str, Any]] = []

    def visit(elem: ET.Element, ancestors: list[Ancestor], abs_x: float, abs_y: float) -> None:
        tx, ty = parse_translate(elem.attrib.get("transform"))
        current_abs_x = abs_x + tx
        current_abs_y = abs_y + ty
        current = Ancestor(elem=elem, tx=tx, ty=ty, abs_x=current_abs_x, abs_y=current_abs_y)
        path = ancestors + [current]

        if local_name(elem.tag) == "path":
            d = elem.attrib.get("d", "")
            points = parse_line_points(d)
            if len(points) >= 2 and "C" not in d.upper() and "Q" not in d.upper():
                start = points[0]
                end = points[-1]
                connectors.append(
                    {
                        "id": f"c{len(connectors) + 1:03d}",
                        "start": [round(current_abs_x + start[0], 2), round(current_abs_y + start[1], 2)],
                        "end": [round(current_abs_x + end[0], 2), round(current_abs_y + end[1], 2)],
                    }
                )

        for child in list(elem):
            visit(child, path, current_abs_x, current_abs_y)

    visit(root, [], 0.0, 0.0)
    return connectors


def distance_to_node(point: list[float], node: dict[str, Any]) -> float:
    px, py = point
    x1 = node["x"]
    y1 = node["y"]
    x2 = x1 + node["width"]
    y2 = y1 + node["height"]
    dx = max(x1 - px, 0.0, px - x2)
    dy = max(y1 - py, 0.0, py - y2)
    return math.hypot(dx, dy)


def infer_edges(nodes: list[dict[str, Any]], connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not nodes:
        return []

    typical_width = sorted(node["width"] for node in nodes)[len(nodes) // 2]
    threshold = max(120.0, typical_width * 0.8)
    edges: list[dict[str, Any]] = []

    for connector in connectors:
        ranked_start = sorted(
            ((distance_to_node(connector["start"], node), node["id"], node) for node in nodes),
            key=lambda item: (item[0], item[1]),
        )
        ranked_end = sorted(
            ((distance_to_node(connector["end"], node), node["id"], node) for node in nodes),
            key=lambda item: (item[0], item[1]),
        )
        start_distance, _, source = ranked_start[0]
        end_distance, _, target = ranked_end[0]
        if source["id"] == target["id"]:
            continue
        if start_distance > threshold or end_distance > threshold:
            continue
        confidence = "high" if start_distance <= threshold / 2 and end_distance <= threshold / 2 else "medium"
        edges.append(
            {
                "id": connector["id"],
                "from_id": source["id"],
                "to_id": target["id"],
                "from": source["label"],
                "to": target["label"],
                "confidence": confidence,
                "start_distance": round(start_distance, 2),
                "end_distance": round(end_distance, 2),
            }
        )
    return edges


def collect_warnings(root: ET.Element, nodes: list[dict[str, Any]], connectors: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    images = [elem for elem in root.iter() if local_name(elem.tag) == "image"]
    if images:
        warnings.append(
            {
                "code": "embedded-raster",
                "message": "SVG contains raster image elements; inspect the JPG/SVG visually because embedded images may not expose text.",
            }
        )
    if not nodes:
        warnings.append({"code": "no-text-nodes", "message": "No SVG text nodes were found."})
    if nodes and not connectors:
        warnings.append({"code": "no-connectors", "message": "No simple connector paths were inferred."})
    return warnings


def extract(svg_path: Path) -> dict[str, Any]:
    root = ET.parse(svg_path).getroot()
    nodes = collect_nodes(root)
    connectors = collect_connectors(root)
    edges = infer_edges(nodes, connectors)
    warnings = collect_warnings(root, nodes, connectors)
    return {
        "source": str(svg_path),
        "stats": {
            "nodes": len(nodes),
            "connectors": len(connectors),
            "inferred_edges": len(edges),
            "warnings": len(warnings),
        },
        "nodes": nodes,
        "connectors": connectors,
        "edges": edges,
        "warnings": warnings,
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        f"# Miro SVG Extraction: {Path(data['source']).name}",
        "",
        f"- nodes: {data['stats']['nodes']}",
        f"- connectors: {data['stats']['connectors']}",
        f"- inferred_edges: {data['stats']['inferred_edges']}",
    ]
    if data["warnings"]:
        lines.extend(["", "## Warnings"])
        for warning in data["warnings"]:
            lines.append(f"- {warning['code']}: {warning['message']}")

    lines.extend(["", "## Nodes", "| id | x | y | label |", "|---|---:|---:|---|"])
    for node in data["nodes"]:
        label = node["label"].replace("|", "\\|")
        lines.append(f"| {node['id']} | {node['x']} | {node['y']} | {label} |")

    lines.extend(["", "## Inferred Edges", "| id | confidence | from | to |", "|---|---|---|---|"])
    for edge in data["edges"]:
        from_label = edge["from"].replace("|", "\\|")
        to_label = edge["to"].replace("|", "\\|")
        lines.append(f"| {edge['id']} | {edge['confidence']} | {from_label} | {to_label} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract text nodes and likely edges from a Miro SVG export.")
    parser.add_argument("svg", type=Path, help="Path to a Miro-exported SVG file")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args(argv)

    data = extract(args.svg)
    if args.format == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
