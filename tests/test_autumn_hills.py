"""Regression coverage for the standalone first-visit Autumn Hills mode.

Static checks run before Pygame is installed in CI. Runtime interaction and
render smoke tests live in smoke_autumn_hills.py and run after pygame-ce install.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "oxygen_web"
DESKTOP = ROOT / "neon_ruins_platformer"


class AutumnHillsSourceTests(unittest.TestCase):
    def test_standalone_scene_is_identical_in_both_builds(self):
        web = (WEB / "autumn_hills.py").read_text(encoding="utf-8")
        desktop = (DESKTOP / "autumn_hills.py").read_text(encoding="utf-8")
        self.assertEqual(web, desktop)

    def test_scene_exposes_own_game_loop_map_shop_and_boss(self):
        source = (WEB / "autumn_hills.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        scene = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "AutumnHillsScene"
        )
        methods = {
            node.name for node in scene.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue({"handle_event", "update", "draw", "_draw_map",
                         "_draw_shop", "_shop_action", "_update_boss"} <= methods)
        for token in (
            "Time Shards", "CLIMBING CLAWS", "STRIKE OF THE NINJA",
            "ENERGY SHURIKEN", "KARUTA PLATES", "POWER SEAL",
            "LEAF MONSTER", "AUTUMN HILLS // FIELD MAP",
        ):
            self.assertIn(token, source)

    def test_scene_has_multiple_encounter_types_and_world_mechanics(self):
        source = (WEB / "autumn_hills.py").read_text(encoding="utf-8")
        for token in (
            '"green"', '"orange"', '"blue"', '"slug"', '"runner"',
            "self.moving = [", "self.swinging = [", "self.falling_spikes = [",
            "self.saws = [", "self.water = [", "self.lanterns = [",
            "self.checkpoints = [", "self.shops = [",
        ):
            self.assertIn(token, source)

    def test_both_oxygen_menus_launch_and_route_the_standalone_mode(self):
        for path in (WEB / "main.py", DESKTOP / "main.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            self.assertIn("from autumn_hills import AutumnHillsScene", source)
            self.assertIn('"THE MESSENGER"', source)
            self.assertIn('self.mode = "autumn_hills"', source)
            self.assertIn('if self.mode == "autumn_hills":', source)
            # There must be exactly one Game class that owns this entry point.
            game = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Game")
            methods = {n.name for n in game.body if isinstance(n, ast.FunctionDef)}
            self.assertIn("start_autumn_hills", methods)
            self.assertIn("open_menu_item", methods)

    def test_web_archive_workflow_copies_the_new_module(self):
        workflow = (ROOT / ".github" / "workflows" / "build-web.yml").read_text(encoding="utf-8")
        self.assertIn("oxygen_web/autumn_hills.py", workflow)
        self.assertIn("assets/autumn_hills.py", workflow)
        self.assertIn("tests/smoke_autumn_hills.py", workflow)


if __name__ == "__main__":
    unittest.main()
