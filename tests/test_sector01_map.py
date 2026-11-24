"""Structural regression tests for OXYGEN's vertically connected opening sector.

These tests intentionally use only the Python standard library so the same
checks can run in GitHub Actions without installing Pygame or launching a
window. They validate the authored level data and a conservative jump-envelope
reachability graph against the movement values used by Player.update().
"""
from __future__ import annotations

import ast
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "neon_ruins_platformer" / "main.py",
    ROOT / "oxygen_web" / "main.py",
)

OLD_COINS = [
    (365, 352), (575, 292), (850, 350), (1085, 297),
    (1480, 345), (1720, 287), (2095, 345), (2345, 287),
    (2705, 345), (2945, 290), (120, 425), (740, 420),
    (1370, 420), (1980, 420), (2570, 420), (3180, 420),
]
OLD_SECRETS = [
    (1030, 175, 100, 65, "UPPER WATCHTOWER"),
    (1850, 120, 105, 65, "ARCHIVE LOFT"),
    (3100, 120, 105, 65, "BELL CHAMBER"),
    (4520, 55, 110, 65, "SKY SHRINE"),
]


def read_first_level(path: Path) -> tuple[str, dict]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "LEVELS"
                for target in node.targets)
    )
    levels = ast.literal_eval(assignment.value)
    return source, levels[0]


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
    """Conservative 2D jump envelope using OXYGEN's default jump/gravity."""
    _ax, ay, _aw, _ah = a
    _bx, by, _bw, _bh = b
    vertical_change = by - ay
    jump_speed = 650.0
    gravity = 1750.0

    if vertical_change < 0:
        rise = -vertical_change
        if rise > (jump_speed * jump_speed) / (2 * gravity):
            return False
        discriminant = jump_speed * jump_speed - 2 * gravity * rise
        flight_time = (jump_speed + math.sqrt(max(0.0, discriminant))) / gravity
    else:
        drop = vertical_change
        if drop > 560:
            return False
        discriminant = jump_speed * jump_speed + 2 * gravity * drop
        flight_time = (jump_speed + math.sqrt(discriminant)) / gravity

    horizontal_reach = 320.0 * flight_time + 30.0
    return horizontal_gap(a, b) <= horizontal_reach


def reachable_nodes(platforms: list[tuple], start_index: int) -> set[int]:
    reached = {start_index}
    frontier = [start_index]
    while frontier:
        current = frontier.pop()
        for candidate, platform in enumerate(platforms):
            if candidate in reached:
                continue
            if jump_reachable(platforms[current], platform):
                reached.add(candidate)
                frontier.append(candidate)
    return reached


class SectorOneMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desktop_source, cls.level = read_first_level(SOURCES[0])
        cls.web_source, cls.web_level = read_first_level(SOURCES[1])
        cls.platforms = as_platforms(cls.level)

    def test_desktop_and_web_maps_are_identical(self):
        self.assertEqual(self.level, self.web_level)

    def test_existing_save_indices_are_preserved(self):
        self.assertEqual(self.level["coins"][:16], OLD_COINS)
        self.assertEqual(self.level["secrets"][:4], OLD_SECRETS)

    def test_world_bounds_and_room_structure(self):
        self.assertEqual(self.level["width"], 7350)
        self.assertLess(self.level["top_bound"], -1500)
        self.assertLessEqual(self.level["camera_top"], self.level["top_bound"])
        self.assertGreater(self.level["camera_bottom"], 0)
        self.assertGreaterEqual(len(self.level["rooms"]), 6)
        self.assertGreaterEqual(len(self.level["secrets"]), 7)
        self.assertTrue(self.level.get("wall_jump", False))

        for x, y, width, height in self.level["platforms"]:
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + width, self.level["width"])
            self.assertGreaterEqual(y, self.level["top_bound"] - 10)

    def test_start_to_exit_has_a_platform_route(self):
        spawn_x, spawn_y = self.level["spawn"]
        start_candidates = [
            i for i, p in enumerate(self.platforms)
            if p[0] <= spawn_x + 15 <= p[0] + p[2]
            and 0 <= p[1] - (spawn_y + 43) <= 60
        ]
        self.assertTrue(start_candidates, "Spawn must have a safe first landing.")

        exit_x, exit_y = self.level["exit"]
        goal_candidates = [
            i for i, p in enumerate(self.platforms)
            if p[0] <= exit_x + 27 <= p[0] + p[2]
            and abs(p[1] - (exit_y + 82)) <= 2
        ]
        self.assertTrue(goal_candidates, "Exit portal must sit on a landing deck.")

        reached = reachable_nodes(self.platforms, start_candidates[0])
        self.assertTrue(
            any(i in reached for i in goal_candidates),
            "The mandatory route from spawn to the exit is disconnected.",
        )

    def test_high_bridge_is_reachable_and_returns_to_the_final_district(self):
        reached = reachable_nodes(
            self.platforms,
            next(i for i, p in enumerate(self.platforms)
                 if p[0] <= 80 <= p[0] + p[2] and p[1] == 475),
        )
        high_bridge = [
            i for i, p in enumerate(self.platforms)
            if p[0] <= 4300 <= p[0] + p[2] and p[1] == -1500
        ]
        final_floor = [
            i for i, p in enumerate(self.platforms)
            if p[0] <= 7210 <= p[0] + p[2] and p[1] == 475
        ]
        self.assertTrue(high_bridge, "The top bridge needs a real landing platform.")
        self.assertTrue(any(i in reached for i in high_bridge),
                        "The route to the high signal bridge is unreachable.")
        self.assertTrue(any(i in reached for i in final_floor),
                        "The descending bridge must reconnect to the final district.")

    def test_secrets_overlap_a_real_player_standing_position(self):
        player_height = 43
        for x, y, width, height, name in self.level["secrets"]:
            secret = (x, y, width, height)
            accessible = False
            for px, py, pw, _ph in self.platforms:
                player_left = px
                player_right = px + pw
                player_top = py - player_height
                player_bottom = py
                overlaps_x = player_right > x and player_left < x + width
                overlaps_y = player_bottom > y and player_top < y + height
                if overlaps_x and overlaps_y:
                    accessible = True
                    break
            self.assertTrue(accessible, f"Secret room {name!r} has no reachable standing ledge.")

    def test_launch_pads_are_attached_to_their_takeoff_decks(self):
        for x, y, width in self.level.get("launch_pads", []):
            attached = any(
                py == y and px < x + width - 20 and px + pw > x + 20
                for px, py, pw, _ph in self.level["platforms"]
            )
            self.assertTrue(attached, f"Launch pad at ({x}, {y}) is not over a platform.")

    def test_checkpoints_and_exit_have_safe_floor_support(self):
        floors = [p for p in self.platforms if p[3] >= 60 and p[1] >= 450]
        self.assertGreaterEqual(len(self.level["checkpoints"]), 6)
        for x, _y in self.level["checkpoints"]:
            distance = min(
                0 if px <= x <= px + width else min(abs(x - px), abs(x - (px + width)))
                for px, _py, width, _height in floors
            )
            self.assertLessEqual(distance, 120, f"Checkpoint at x={x} is too far from a safe floor.")
        exit_x, exit_y = self.level["exit"]
        self.assertTrue(any(
            px <= exit_x + 27 <= px + width and py == exit_y + 82
            for px, py, width, height in floors
        ))

    def test_vertical_camera_offsets_are_wired_to_world_objects(self):
        for source, label in ((self.desktop_source, "desktop"), (self.web_source, "web")):
            for fragment in (
                "self.player.draw(self.screen, self.camera_x, self.camera_y)",
                "draw_checkpoint(self.screen, cp, self.camera_x, accent, self.time, self.camera_y)",
                "draw_spikes(self.screen, spike, self.camera_x, accent2, self.camera_y)",
            ):
                self.assertIn(fragment, source, f"{label} build is missing camera offset: {fragment}")
            self.assertIn("target_y = self.player.y - 190", source)
            self.assertIn('self.top_bound = float(data.get("top_bound", 0.0))', source)


if __name__ == "__main__":
    unittest.main()
