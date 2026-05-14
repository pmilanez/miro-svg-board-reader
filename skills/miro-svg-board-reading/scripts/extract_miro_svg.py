#!/usr/bin/env python3
"""Extract readable structure from a Miro SVG export.

This helper is intentionally heuristic: Miro exports visual SVG, not a product
flow schema. It turns machine-readable text, positions, and simple arrow paths
into evidence an agent can inspect before summarizing the board.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRANSLATE_RE = re.compile(r"translate\(\s*([-+]?\d*\.?\d+)[,\s]+([-+]?\d*\.?\d+)\s*\)")
POINT_RE = re.compile(r"[ML]\s*([-+]?\d*\.?\d+)[,\s]+([-+]?\d*\.?\d+)", re.I)
SLUG_RE = re.compile(r"[^a-z0-9]+")
ACTION_RE = re.compile(
    r"\b(api|create|creates|created|cria|criacao|consulta|consult|send|sent|redirect|transition|transicao|"
    r"handoff|process|processing|analysis|analyze|submit|register|registered|approve|approved|reject|"
    r"rejected|offer|found|execute|executed)\b",
    re.I,
)
ACTOR_SYSTEM_RE = re.compile(
    r"\b(api|app|web|whatsapp|service|foundation|customer|client|user|provider|partner|orchestrator|"
    r"agent|system|modelo|model)\b",
    re.I,
)
STATUS_RE = re.compile(r"\b(status|state|journey|approved|rejected|registered|terminated|abandoned|processing|handoff)\b", re.I)


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


def slugify(value: str) -> str:
    slug = SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "board"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def markdown_table_value(value: str) -> str:
    return value.replace("|", "\\|")


def mermaid_label(value: str) -> str:
    return value.replace('"', "'").replace("[", "(").replace("]", ")")


def reading_order(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(nodes, key=lambda node: (node["x"], node["y"], node["id"]))


def board_bounds(nodes: list[dict[str, Any]]) -> dict[str, float]:
    if not nodes:
        return {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0, "width": 0.0, "height": 0.0}
    min_x = min(node["x"] for node in nodes)
    min_y = min(node["y"] for node in nodes)
    max_x = max(node["x"] + node["width"] for node in nodes)
    max_y = max(node["y"] + node["height"] for node in nodes)
    return {
        "min_x": round(min_x, 2),
        "min_y": round(min_y, 2),
        "max_x": round(max_x, 2),
        "max_y": round(max_y, 2),
        "width": round(max_x - min_x, 2),
        "height": round(max_y - min_y, 2),
    }


def layout_summary(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    bounds = board_bounds(nodes)
    orientation = "left-to-right" if bounds["width"] >= bounds["height"] else "top-to-bottom"
    return {
        "bounds": bounds,
        "primary_orientation": orientation,
        "reading_order_ids": [node["id"] for node in reading_order(nodes)],
    }


def label_counts(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node["label"]] = counts.get(node["label"], 0) + 1
    return counts


def repeated_labels(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = label_counts(nodes)
    repeated: list[dict[str, Any]] = []
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if count <= 1:
            continue
        repeated.append(
            {
                "label": label,
                "count": count,
                "node_ids": [node["id"] for node in nodes if node["label"] == label],
            }
        )
    return repeated


def concept_tokens(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for node in nodes:
        for token in re.findall(r"\w{3,}", node["label"]):
            key = token.lower()
            counts[key] = counts.get(key, 0) + 1
    return [
        {"token": token, "count": count}
        for token, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:30]
    ]


def select_labels(nodes: list[dict[str, Any]], pattern: re.Pattern[str]) -> list[dict[str, str]]:
    return [
        {"id": node["id"], "label": node["label"]}
        for node in nodes
        if pattern.search(node["label"])
    ]


def domain_model(data: dict[str, Any]) -> dict[str, Any]:
    nodes = data["nodes"]
    return {
        "status_like_labels": select_labels(nodes, STATUS_RE),
        "actor_or_system_like_labels": select_labels(nodes, ACTOR_SYSTEM_RE),
        "action_or_event_like_labels": select_labels(nodes, ACTION_RE),
        "decision_like_labels": [
            {"id": node["id"], "label": node["label"]}
            for node in nodes
            if "?" in node["label"] or re.search(r"\b(decision|if|whether|found|approved|rejected)\b", node["label"], re.I)
        ],
        "repeated_labels": repeated_labels(nodes),
        "common_terms": concept_tokens(nodes),
    }


def disconnected_nodes(data: dict[str, Any]) -> list[dict[str, str]]:
    connected_ids = {edge["from_id"] for edge in data["edges"]} | {edge["to_id"] for edge in data["edges"]}
    return [
        {"id": node["id"], "label": node["label"]}
        for node in data["nodes"]
        if node["id"] not in connected_ids
    ]


def ambiguity_report(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "warnings": data["warnings"],
        "medium_confidence_edges": [edge for edge in data["edges"] if edge["confidence"] != "high"],
        "repeated_labels": repeated_labels(data["nodes"]),
        "disconnected_nodes": disconnected_nodes(data),
        "notes": [
            "Connector direction is inferred from SVG path start/end points; visually confirm arrowheads before implementation.",
            "Colors and spatial groups are semantic signals, not proof of behavior by themselves.",
            "Treat generated narrative as a scaffold until checked against the rendered board.",
        ],
    }


def render_flow_mermaid(data: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    for node in data["nodes"]:
        lines.append(f'  {node["id"]}["{mermaid_label(node["label"])}"]')
    for edge in data["edges"]:
        lines.append(f'  {edge["from_id"]} --> {edge["to_id"]}')
    return "\n".join(lines) + "\n"


def render_visual_map(data: dict[str, Any]) -> str:
    layout = layout_summary(data["nodes"])
    bounds = layout["bounds"]
    lines = [
        "# Visual Map",
        "",
        f"- primary_orientation: {layout['primary_orientation']}",
        f"- bounds: x={bounds['min_x']}..{bounds['max_x']}, y={bounds['min_y']}..{bounds['max_y']}",
        "",
        "## Reading Order",
        "| id | x | y | label |",
        "|---|---:|---:|---|",
    ]
    for node in reading_order(data["nodes"]):
        lines.append(f"| {node['id']} | {node['x']} | {node['y']} | {markdown_table_value(node['label'])} |")
    return "\n".join(lines) + "\n"


def render_narrative(data: dict[str, Any]) -> str:
    lines = [
        "# Narrative Understanding",
        "",
        "This is an evidence-based reading scaffold. It lists observed labels and inferred connections so an agent can write the final domain interpretation without losing source context.",
        "",
        "## Inferred Flow",
    ]
    if data["edges"]:
        for edge in data["edges"]:
            lines.append(f"- {edge['from']} -> {edge['to']} ({edge['confidence']} confidence)")
    else:
        lines.append("- No connector-based flow was inferred. Use the visual map and rendered board to infer sequence.")
    lines.extend(["", "## Reading-Order Story"])
    for index, node in enumerate(reading_order(data["nodes"]), start=1):
        lines.append(f"{index}. {node['label']}")
    return "\n".join(lines) + "\n"


def render_domain_model(data: dict[str, Any]) -> str:
    model = domain_model(data)
    lines = ["# Domain Model", ""]
    sections = [
        ("Status-Like Labels", "status_like_labels"),
        ("Actor/System-Like Labels", "actor_or_system_like_labels"),
        ("Action/Event-Like Labels", "action_or_event_like_labels"),
        ("Decision-Like Labels", "decision_like_labels"),
    ]
    for title, key in sections:
        lines.extend([f"## {title}", ""])
        items = model[key]
        if items:
            for item in items:
                lines.append(f"- {item['id']}: {item['label']}")
        else:
            lines.append("- None detected by generic label heuristics.")
        lines.append("")
    lines.extend(["## Repeated Labels", ""])
    if model["repeated_labels"]:
        for item in model["repeated_labels"]:
            lines.append(f"- {item['label']}: {item['count']} occurrences ({', '.join(item['node_ids'])})")
    else:
        lines.append("- None.")
    lines.extend(["", "## Common Terms", ""])
    lines.extend(f"- {item['token']}: {item['count']}" for item in model["common_terms"])
    return "\n".join(lines) + "\n"


def render_decisions_and_ambiguities(data: dict[str, Any]) -> str:
    report = ambiguity_report(data)
    lines = [
        "# Decisions and Ambiguities",
        "",
        "## What Appears Decided",
        "",
        "- Treat labels connected by high-confidence inferred edges as candidate decided flow, pending visual arrowhead confirmation.",
        "- Treat repeated status or terminal labels as separate states unless position and lane prove they are duplicates.",
        "",
        "## Ambiguities and Risks",
        "",
    ]
    for warning in report["warnings"]:
        lines.append(f"- {warning['code']}: {warning['message']}")
    for edge in report["medium_confidence_edges"]:
        lines.append(f"- medium edge: {edge['from']} -> {edge['to']}")
    for item in report["repeated_labels"]:
        lines.append(f"- repeated label: {item['label']} appears {item['count']} times")
    if report["disconnected_nodes"]:
        lines.append(f"- disconnected nodes: {len(report['disconnected_nodes'])} labels have no inferred connector.")
    if not lines[-1].startswith("-"):
        lines.append("- No automatic ambiguities beyond the standard SVG interpretation cautions.")
    lines.extend(["", "## Standard Cautions", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    return "\n".join(lines) + "\n"


def render_agent_handoff(data: dict[str, Any]) -> str:
    lines = [
        "# Agent Handoff",
        "",
        "Use this dossier as board context before planning, coding, reviewing, or writing product/architecture analysis.",
        "",
        "## Start Here",
        "",
        "1. Read `board-dossier.md` for the complete summary.",
        "2. Use `raw-nodes.json` and `raw-edges.json` as source evidence.",
        "3. Use `decisions-and-ambiguities.md` to avoid over-assuming unclear arrows, repeated labels, or raster-hidden content.",
        "4. If a live Miro MCP source is available, use it only to confirm item existence, frame titles, comments, or metadata not present in SVG.",
        "",
        "## Response Contract",
        "",
        "- Separate observed board labels from inferred meaning.",
        "- State the main flow, branches, statuses/entities, and terminal outcomes.",
        "- Call out inconsistencies, copy/paste-looking errors, and missing context.",
        "- Before implementation, turn unresolved ambiguities into explicit questions or assumptions.",
    ]
    return "\n".join(lines) + "\n"


def render_board_dossier(data: dict[str, Any]) -> str:
    source_name = Path(data["source"]).name
    layout = layout_summary(data["nodes"])
    model = domain_model(data)
    report = ambiguity_report(data)
    lines = [
        f"# Board Dossier: {source_name}",
        "",
        "## Board Identity",
        "",
        f"- source: {data['source']}",
        f"- probable_type: visual flow / board map inferred from SVG labels and connectors",
        f"- primary_orientation: {layout['primary_orientation']}",
        f"- nodes: {data['stats']['nodes']}",
        f"- connectors: {data['stats']['connectors']}",
        f"- inferred_edges: {data['stats']['inferred_edges']}",
        f"- warnings: {data['stats']['warnings']}",
        "",
        "## Visual Map",
        "",
        f"- reading_order: {', '.join(layout['reading_order_ids'])}",
        "- See `visual-map.md` for coordinates and full reading order.",
        "",
        "## Raw Evidence",
        "",
        "- See `raw-nodes.json` for all extracted text nodes.",
        "- See `raw-edges.json` for connector candidates and inferred edges.",
        "",
        "## Narrative Understanding",
        "",
    ]
    if data["edges"]:
        lines.append("The SVG contains inferred connector flow. Review `narrative.md` and `flow.mmd` before turning it into product meaning.")
        for edge in data["edges"][:10]:
            lines.append(f"- {edge['from']} -> {edge['to']} ({edge['confidence']})")
        if len(data["edges"]) > 10:
            lines.append(f"- ... {len(data['edges']) - 10} more inferred edges in `narrative.md`.")
    else:
        lines.append("No connector-based flow was inferred. Use spatial reading order and visual inspection.")
    lines.extend(
        [
            "",
            "## Domain Model",
            "",
            f"- status_like_labels: {len(model['status_like_labels'])}",
            f"- actor_or_system_like_labels: {len(model['actor_or_system_like_labels'])}",
            f"- action_or_event_like_labels: {len(model['action_or_event_like_labels'])}",
            f"- decision_like_labels: {len(model['decision_like_labels'])}",
            "- See `domain-model.md` for the detailed generic model.",
            "",
            "## Decisions and Ambiguities",
            "",
            f"- warnings: {len(report['warnings'])}",
            f"- medium_confidence_edges: {len(report['medium_confidence_edges'])}",
            f"- repeated_labels: {len(report['repeated_labels'])}",
            f"- disconnected_nodes: {len(report['disconnected_nodes'])}",
            "- See `decisions-and-ambiguities.md` before making implementation assumptions.",
            "",
            "## Agent Handoff",
            "",
            "Use this dossier to brief another agent. The agent should cite observed labels, mark inferred connections, and convert ambiguities into questions before coding.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_dossier(data: dict[str, Any], dossier_root: Path) -> Path:
    source = Path(data["source"])
    slug = slugify(source.stem)
    dossier_dir = dossier_root / slug
    dossier_dir.mkdir(parents=True, exist_ok=True)

    raw_edges = {"connectors": data["connectors"], "inferred_edges": data["edges"]}
    files = [
        "index.json",
        "raw-nodes.json",
        "raw-edges.json",
        "board-dossier.md",
        "visual-map.md",
        "narrative.md",
        "domain-model.md",
        "decisions-and-ambiguities.md",
        "agent-handoff.md",
        "flow.mmd",
    ]
    index = {
        "board": {
            "source": str(source),
            "name": source.name,
            "slug": slug,
            "sha256": file_sha256(source),
        },
        "generated_at": utc_now(),
        "stats": data["stats"],
        "confidence_signals": {
            "has_text_nodes": bool(data["nodes"]),
            "has_connectors": bool(data["connectors"]),
            "has_inferred_edges": bool(data["edges"]),
            "has_warnings": bool(data["warnings"]),
        },
        "files": files,
    }

    write_json(dossier_dir / "index.json", index)
    write_json(dossier_dir / "raw-nodes.json", data["nodes"])
    write_json(dossier_dir / "raw-edges.json", raw_edges)
    (dossier_dir / "board-dossier.md").write_text(render_board_dossier(data), encoding="utf-8")
    (dossier_dir / "visual-map.md").write_text(render_visual_map(data), encoding="utf-8")
    (dossier_dir / "narrative.md").write_text(render_narrative(data), encoding="utf-8")
    (dossier_dir / "domain-model.md").write_text(render_domain_model(data), encoding="utf-8")
    (dossier_dir / "decisions-and-ambiguities.md").write_text(render_decisions_and_ambiguities(data), encoding="utf-8")
    (dossier_dir / "agent-handoff.md").write_text(render_agent_handoff(data), encoding="utf-8")
    (dossier_dir / "flow.mmd").write_text(render_flow_mermaid(data), encoding="utf-8")
    return dossier_dir


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract text nodes and likely edges from a Miro SVG export.")
    parser.add_argument("svg", type=Path, help="Path to a Miro-exported SVG file")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--dossier-dir", type=Path, help="Write a reusable Board Dossier under this directory")
    args = parser.parse_args(argv)

    data = extract(args.svg)
    if args.dossier_dir:
        data["dossier"] = str(write_dossier(data, args.dossier_dir))
    if args.format == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
