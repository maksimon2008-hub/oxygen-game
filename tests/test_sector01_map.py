"""Structural regression tests for the OXYGEN port of the Autumn Hills level."""
from __future__ import annotations
import ast
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (ROOT / "neon_ruins_platformer" / "main.py", ROOT / "oxygen_web" / "main.py")


def read_first_level(path: Path) -> tuple[str, dict]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    assignment = next(node for node in tree.body
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "LEVELS" for target in node.targets))
    return source, ast.literal_eval(assignment.value)[0]


def as_platforms(level: dict) -> list[tuple[float, float, float, float]]:
    items = [tuple(map(float, p[:4])) for p in level["platforms"]]
    items.extend(tuple(map(float, p[:4])) for p in level.get("moving_platforms", []))
    return items


def horizontal_gap(a: tuple, b: tuple) -> float:
    ax, _ay, aw, _ah = a
    bx, _by, bw, _bh = b
    if ax + aw < bx:
        return bx - (ax + aw)
    if bx + bw < ax:
        return ax - (bx + bw)
    return 0.0


def jump_reachable(a: tuple, b: tuple) -> bool:
    _ax, ay, _aw, _ah = a
    _bx, by, _bw, _bh = b
    dy = by - ay
    jump_speed, gravity, run_speed = 650.0, 1750.0, 320.0
    if dy < 0:
        rise = -dy
        if rise > jump_speed * jump_speed / (2 * gravity):
            return False
        t = (jump_speed + math.sqrt(max(0.0, jump_speed * jump_speed - 2 * gravity * rise))) / gravity
    else:
        if dy > 560:
            return False
        t = (jump_speed + math.sqrt(jump_speed * jump_speed + 2 * gravity * dy)) / gravity
    return horizontal_gap(a, b) <= run_speed * t + 30.0


def reachable_nodes(platforms: list[tuple], start: int) -> set[int]:
    reached, frontier = {start}, [start]
    while frontier:
        current = frontier.pop()
        for i, candidate in enumerate(platforms):
            if i not in reached and jump_reachable(platforms[current], candidate):
                reached.add(i)
                frontier.append(i)
    return reached


class SectorOneMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desktop_source, cls.level = read_first_level(SOURCES[0])
        cls.web_source, cls.web_level = read_first_level(SOURCES[1])
        cls.platforms = as_platforms(cls.level)
        sx, sy = cls.level["spawn"]
        cls.start = next(i for i, p in enumerate(cls.platforms)
            if p[0] <= sx + 15 <= p[0] + p[2] and 0 <= p[1] - (sy + 43) <= 60)
        cls.reached = reachable_nodes(cls.platforms, cls.start)

    def test_desktop_and_web_maps_are_identical(self):
        self.assertEqual(self.level, self.web_level)

    def test_full_autumn_hills_route_is_ported(self):
        self.assertEqual(self.level["width"], 22400)
        self.assertEqual(len(self.level["rooms"]), 15)
        self.assertEqual(self.level["rooms"][0][4], "AUTUMN GATE")
        self.assertEqual(self.level["rooms"][-1][4], "LEAF MONSTER")
        self.assertGreaterEqual(len(self.level["platforms"]), 90)
        self.assertGreaterEqual(len(self.level["coins"]), 65)
        self.assertGreaterEqual(len(self.level["checkpoints"]), 5)
        self.assertGreaterEqual(len(self.level["drones"]), 15)
        self.assertGreaterEqual(len(self.level["seekers"]), 4)
        self.assertEqual(len(self.level["moving_platforms"]), 3)

    def test_platforms_stay_inside_world_and_camera_bounds(self):
        self.assertLessEqual(self.level["camera_top"], self.level["top_bound"])
        self.assertGreater(self.level["camera_bottom"], 0)
        for x, y, width, height in self.level["platforms"]:
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + width, self.level["width"])
            self.assertGreaterEqual(y, self.level["top_bound"] - 10)
            self.assertLess(y, self.level["fall_limit"])

    def test_spawn_to_exit_route_is_reachable(self):
        ex, ey = self.level["exit"]
        goals = [i for i, p in enumerate(self.platforms)
            if p[0] <= ex + 27 <= p[0] + p[2] and abs(p[1] - (ey + 82)) <= 2]
        self.assertTrue(goals, "Exit must sit on the final ground platform.")
        self.assertTrue(any(i in self.reached for i in goals),
                        "The main Autumn Hills route must connect spawn to exit.")

    def test_lower_corridor_and_secret_chamber_are_supported(self):
        for key in ("flooded_roots", "beacon_vault"):
            x, floor_y = self.level["region_landmarks"][key]
            self.assertTrue(any(i in self.reached and p[0] <= x <= p[0] + p[2]
                and abs(p[1] - floor_y) <= 2 for i, p in enumerate(self.platforms)),
                f"Landmark {key} must have reachable floor support.")
        for x, y, width, height, name in self.level["secrets"]:
            self.assertTrue(any(i in self.reached and p[0] + p[2] > x and p[0] < x + width
                and p[1] > y and p[1] - 43 < y + height
                for i, p in enumerate(self.platforms)),
                f"Secret {name} must overlap a reachable ledge.")

    def test_map_overlay_and_tab_control_exist_in_both_builds(self):
        for source, label in ((self.desktop_source, "desktop"), (self.web_source, "web")):
            self.assertIn("self.map_open = False", source, label)
            self.assertIn("event.key == pygame.K_TAB", source, label)
            self.assertIn("def draw_sector_map(self)", source, label)
            self.assertIn("self.level.rooms", source, label)
            self.assertIn("self.draw_sector_map()", source, label)

    def test_oxygen_camera_offsets_remain_wired(self):
        for source, label in ((self.desktop_source, "desktop"), (self.web_source, "web")):
            for fragment in (
                "self.player.draw(self.screen, self.camera_x, self.camera_y)",
                "draw_checkpoint(self.screen, cp, self.camera_x, accent, self.time, self.camera_y)",
                "draw_spikes(self.screen, spike, self.camera_x, accent2, self.camera_y)",
            ):
                self.assertIn(fragment, source, f"{label}: missing {fragment}")


if __name__ == "__main__":
    unittest.main()
