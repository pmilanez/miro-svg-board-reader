import json
import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "miro-svg-board-reading" / "scripts" / "extract_miro_svg.py"


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

    def test_writes_complete_board_dossier_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            svg_path = tmp_path / "Customer Status Flow.svg"
            dossier_root = tmp_path / "specs"
            svg_path.write_text(
                textwrap.dedent(
                    """
                    <svg xmlns="http://www.w3.org/2000/svg" width="700" height="240">
                      <g width="120px" height="40px" transform="translate(10, 30)">
                        <text x="5" y="24">API creates customer</text>
                      </g>
                      <g width="140px" height="40px" transform="translate(220, 30)">
                        <text x="5" y="24">STATUS: REGISTERED</text>
                      </g>
                      <g width="150px" height="40px" transform="translate(450, 30)">
                        <text x="5" y="24">Decision: offer found?</text>
                      </g>
                      <g width="110px" height="0px" transform="translate(130, 50)">
                        <path stroke="#1a1a1a" d="M 0 0 L 90 0" />
                      </g>
                      <g width="110px" height="0px" transform="translate(360, 50)">
                        <path stroke="#1a1a1a" d="M 0 0 L 90 0" />
                      </g>
                    </svg>
                    """
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(svg_path),
                    "--format",
                    "json",
                    "--dossier-dir",
                    str(dossier_root),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            data = json.loads(result.stdout)
            dossier_dir = dossier_root / "customer-status-flow"
            expected_files = {
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
            }

            self.assertEqual(data["dossier"], str(dossier_dir))
            self.assertEqual(expected_files, {path.name for path in dossier_dir.iterdir()})
            index = json.loads((dossier_dir / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["board"]["slug"], "customer-status-flow")
            self.assertEqual(index["stats"]["nodes"], 3)
            dossier = (dossier_dir / "board-dossier.md").read_text(encoding="utf-8")
            self.assertIn("## Board Identity", dossier)
            self.assertIn("## Narrative Understanding", dossier)
            self.assertIn("## Agent Handoff", dossier)
            self.assertIn("STATUS: REGISTERED", (dossier_dir / "domain-model.md").read_text(encoding="utf-8"))
            self.assertIn("flowchart LR", (dossier_dir / "flow.mmd").read_text(encoding="utf-8"))

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
