from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "miro-svg-board-reading"


class SkillPackagingTests(unittest.TestCase):
    def test_vercel_skills_layout_packages_helper_with_skill(self) -> None:
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file())
        self.assertTrue((SKILL_DIR / "scripts" / "extract_miro_svg.py").is_file())

    def test_readme_documents_npx_skills_install_flow(self) -> None:
        readme = (ROOT / "README.md").read_text()

        self.assertIn("npx skills add pmilanez/miro-svg-board-reader", readme)
        self.assertIn("--skill miro-svg-board-reading", readme)


if __name__ == "__main__":
    unittest.main()
