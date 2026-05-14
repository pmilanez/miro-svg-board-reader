import json
import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "extract_miro_svg.py"


class ExtractMiroSvgTest(unittest.TestCase):
    def load_module(self):
        spec = importlib.util.spec_from_file_location("extract_miro_svg", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def run_script(self, svg: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "board.svg"
            svg_path.write_text(textwrap.dedent(svg), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(svg_path), "--format", "json"],
                check=True,
                text=True,
                capture_output=True,
            )
            return json.loads(result.stdout)

    def test_groups_multiline_text_into_nodes_and_infers_arrow_edge(self):
        data = self.run_script(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="500" height="160">
              <g width="100px" height="40px" transform="translate(10, 20)">
                <text x="5" y="15">START</text>
                <text x="5" y="30">FLOW</text>
              </g>
              <g width="110px" height="40px" transform="translate(220, 20)">
                <text x="5" y="24">END FLOW</text>
              </g>
              <g width="110px" height="0px" transform="translate(110, 40)">
                <path stroke="#1a1a1a" d="M 0 0 L 110 0" />
              </g>
            </svg>
            """
        )

        labels = [node["label"] for node in data["nodes"]]
        self.assertIn("START FLOW", labels)
        self.assertIn("END FLOW", labels)
        self.assertEqual(data["edges"][0]["from"], "START FLOW")
        self.assertEqual(data["edges"][0]["to"], "END FLOW")

    def test_joins_same_line_text_runs_without_inventing_word_breaks(self):
        data = self.run_script(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="300" height="120">
              <g width="120px" height="40px" transform="translate(10, 20)">
                <text x="5" y="15" textLength="18">TRI</text>
                <text x="23" y="15" textLength="24">AGE</text>
              </g>
            </svg>
            """
        )

        self.assertIn("TRIAGE", [node["label"] for node in data["nodes"]])

    def test_preserves_space_after_colon_for_split_status_labels(self):
        data = self.run_script(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="300" height="120">
              <g width="180px" height="40px" transform="translate(10, 20)">
                <text x="5" y="15" textLength="84">JOURNEY STATUS:</text>
                <text x="89" y="15" textLength="48">TRIAGE</text>
              </g>
            </svg>
            """
        )

        self.assertIn("JOURNEY STATUS: TRIAGE", [node["label"] for node in data["nodes"]])

    def test_marks_embedded_raster_images_as_low_semantic_signal(self):
        data = self.run_script(
            """
            <svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">
              <image href="data:image/png;base64,abc" x="0" y="0" width="300" height="200" />
            </svg>
            """
        )

        self.assertEqual(data["warnings"][0]["code"], "embedded-raster")

    def test_edge_inference_is_deterministic_when_distances_tie(self):
        module = self.load_module()
        nodes = [
            {"id": "n001", "label": "A", "x": 0, "y": 0, "width": 40, "height": 40},
            {"id": "n002", "label": "B", "x": 0, "y": 80, "width": 40, "height": 40},
            {"id": "n003", "label": "C", "x": 160, "y": 40, "width": 40, "height": 40},
        ]
        connectors = [{"id": "c001", "start": [0, 60], "end": [160, 60]}]

        edges = module.infer_edges(nodes, connectors)

        self.assertEqual(edges[0]["to"], "C")


if __name__ == "__main__":
    unittest.main()
