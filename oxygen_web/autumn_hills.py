"""Standalone first-visit Autumn Hills fan reconstruction.

The module intentionally owns its movement, combat, collectibles, shops,
checkpoints, map and boss state. It does not read or write OXYGEN save data.
All art is drawn procedurally; no game assets or audio are bundled.
"""
from __future__ import annotations

import math
import random
import pygame


VIEW_W, VIEW_H = 550, 310
WORLD_W, WORLD_H = 11200, 570
GROUND_Y = 270
SKY = (27, 22, 62)
MOON = (157, 129, 190)
INK = (17, 14, 33)
STONE = (68, 53, 69)
STONE_LIGHT = (119, 86, 91)
MOSS = (93, 118, 73)
LEAF_RED = (128, 43, 61)
LEAF_LIGHT = (179, 67, 69)
BLUE = (74, 194, 224)
SHARD = (91, 214, 237)
GOLD = (250, 207, 112)
WHITE = (244, 235, 220)


def _rect(x, y, w, h):
    return pygame.Rect(int(x), int(y), max(1, int(w)), max(1, int(h)))


class AutumnHillsScene:
    """Independent side-scrolling platform game, embedded into OXYGEN."""

    def __init__(self, output_size=(1100, 620)):
        self.output_size = output_size
        self.frame = pygame.Surface((VIEW_W, VIEW_H))
        self.font_tiny = pygame.font.SysFont("consolas", 6, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 8, bold=True)
        self.font = pygame.font.SysFont("consolas", 10, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 17, bold=True)
        self.random = random.Random(1988)
        self.stars = [
            (self.random.randrange(0, WORLD_W), self.random.randrange(8, 160),
             self.random.choice((1, 1, 1, 2)), self.random.random() * math.tau)
            for _ in range(170)
        ]
        self.paused = False
        self.map_open = False
        self.shop_open = False
        self.shop_index = 0
        self.shop_cursor = 0
        self.dialog_timer = 0.0
        self.dialog_text = ""
        self.banner_timer = 0.0
        self.banner_name = ""
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.elapsed = 0.0
        self.victory = False
        self.game_over = False
        self.completed = False
        self._build_world()
        self._reset_player()
        self._set_banner("AUTUMN HILLS", "A quiet forest. A long road east.")

    # ------------------------------------------------------------------
    # World construction
    # ------------------------------------------------------------------
    def _add_platform(self, x, y, w, h=12, kind="stone"):
        rect = _rect(x, y, w, h)
        self.platforms.append({"rect": rect, "kind": kind})
        self.solids.append(rect)
        return rect

    def _add_ground(self, x, w, y=GROUND_Y):
        return self._add_platform(x, y, w, WORLD_H - y + 60, "ground")

    def _add_enemy(self, kind, x, y, left=None, right=None, hp=None):
        defaults = {"green": 3, "orange": 2, "blue": 1, "slug": 1, "runner": 1}
        self.enemies.append({
            "kind": kind, "x": float(x), "y": float(y),
            "left": float(x - 55 if left is None else left),
            "right": float(x + 55 if right is None else right),
            "hp": defaults[kind] if hp is None else hp,
            "alive": True, "dir": 1, "phase": 0.0,
            "timer": self.random.uniform(0.65, 1.9),
            "flash": 0.0,
        })

    def _build_world(self):
        self.platforms = []
        self.solids = []
        self.spikes = []
        self.lanterns = []
        self.shards = []
        self.enemies = []
        self.projectiles = []
        self.moving = []
        self.swinging = []
        self.falling_spikes = []
        self.saws = []
        self.water = []
        self.currents = []
        self.birds = []
        self.swinging_spikes = []
        self.checkpoints = []
        self.shops = []
        self.potions = []
        self.breakables = []
        self.seal = {"rect": _rect(8955, 370, 18, 23), "found": False}
        self.seal_gate = _rect(9230, 215, 35, 55)
        self.secret_checkpoint = _rect(8330, 404, 24, 16)
        self.rooms = [
            (0, 660, "AUTUMN GATE"),
            (660, 1370, "LANTERN PATH"),
            (1370, 2070, "BROKEN SHRINE"),
            (2070, 2650, "THE SHOP"),
            (2650, 3510, "RED CANOPY"),
            (3510, 4320, "HUNTER'S REACH"),
            (4320, 5200, "OLD ROOTS"),
            (5200, 6100, "FLOODED ROOTS"),
            (6100, 6790, "SECOND PORTAL"),
            (6790, 7560, "CRUMBLING CANOPY"),
            (7560, 8240, "OUN'TARDE RUN"),
            (8240, 9340, "BROKEN SHRINE"),
            (9340, 10100, "FINAL ASCENT"),
            (10100, 10400, "LAST SHOP"),
            (10400, 11200, "LEAF MONSTER"),
        ]

        # The broad route and drops are organized into screen-sized scenes.
        for x, w in [
            (0, 660), (680, 600), (1320, 630), (2050, 45), (2165, 65),
            (2250, 780), (3090, 390), (3530, 710), (4280, 650),
            (5020, 520), (5570, 570), (6170, 590), (6790, 720),
            (7560, 620), (8240, 70), (8390, 470), (8890, 210), (9340, 710),
            (10100, 790), (10980, 220),
        ]:
            self._add_ground(x, w)

        # Short drops and raised ledges in the opening rooms.
        for p in [
            (185, 226, 62, 10), (305, 204, 70, 10), (430, 220, 72, 10),
            (730, 225, 82, 10), (850, 188, 68, 10), (1000, 218, 72, 10),
            (1190, 204, 76, 10), (1390, 215, 80, 10), (1525, 178, 72, 10),
            (1660, 212, 78, 10), (1810, 184, 70, 10),
            (1900, 238, 90, 10),
            (2290, 232, 82, 10), (2400, 191, 68, 10),
            (2540, 153, 78, 10), (2660, 205, 82, 10),
            (2820, 222, 70, 10), (2935, 190, 68, 10),
            (3050, 155, 72, 10), (3200, 210, 86, 10),
            (3375, 180, 70, 10), (3545, 222, 70, 10),
            (3675, 187, 78, 10), (3810, 154, 72, 10),
            (3955, 207, 70, 10), (4100, 178, 70, 10),
            (4385, 220, 75, 10), (4540, 180, 70, 10),
            (4730, 205, 82, 10), (4900, 170, 74, 10),
            (5085, 210, 74, 10),
            (5590, 214, 70, 10), (5740, 179, 75, 10),
            (5895, 211, 76, 10), (6060, 186, 76, 10),
            (6260, 221, 78, 10), (6435, 184, 78, 10),
            (6640, 207, 70, 10),
            (6810, 216, 70, 10), (6960, 180, 70, 10),
            (7120, 211, 74, 10), (7310, 180, 72, 10),
            (7500, 214, 74, 10), (7670, 184, 72, 10),
            (7840, 205, 72, 10), (8050, 175, 74, 10),
            (8300, 216, 80, 10), (8460, 182, 75, 10),
            (8620, 210, 70, 10), (8780, 175, 72, 10),
            (9000, 211, 75, 10), (9160, 181, 74, 10),
            (9370, 220, 76, 10), (9525, 185, 70, 10),
            (9680, 210, 75, 10), (9840, 176, 72, 10),
            (10020, 214, 72, 10),
        ]:
            self._add_platform(*p)

        # The first shop sits at the bottom of the unavoidable-looking drop.
        # A side wall becomes climbable after the free Climbing Claws are granted.
        self._add_platform(1970, 355, 250, 14, "shop_floor")
        self._add_platform(2220, 174, 20, 196, "wall")
        self._add_platform(2240, 174, 62, 10, "stone")

        # A real submerged route, not a blue overlay painted over dry ground.
        self.water = [
            _rect(4380, 224, 1120, 235),
            _rect(5050, 180, 680, 270),
        ]
        self._add_platform(4380, 438, 1120, 35, "underwater")
        self._add_platform(5170, 392, 380, 18, "underwater")
        self.currents = [_rect(4650, 280, 260, 125), _rect(5200, 245, 340, 140)]
        for p in [
            (4415, 350, 74, 10), (4560, 393, 60, 10),
            (4760, 337, 66, 10), (4920, 378, 62, 10),
            (5100, 318, 70, 10), (5270, 350, 68, 10),
            (5420, 302, 64, 10),
        ]:
            self._add_platform(*p, kind="underwater")

        # The optional first-visit Power Seal route is below the main path.
        # The blocks are breakable; the two swinging platforms cross the pit.
        self._add_platform(8230, 392, 110, 12, "secret_floor")
        self._add_platform(8230, 420, 1240, 45, "secret_floor")
        # A stepped return connects the lower seal chamber to the main route.
        self._add_platform(9100, 385, 70, 10, "secret_stair")
        self._add_platform(9190, 350, 70, 10, "secret_stair")
        self._add_platform(9280, 315, 65, 10, "secret_stair")
        self.solids.append(self.seal_gate)
        self.breakables = [
            {"rect": _rect(8310, 248, 20, 22), "alive": True},
            {"rect": _rect(8330, 248, 20, 22), "alive": True},
            {"rect": _rect(8350, 248, 20, 22), "alive": True},
            {"rect": _rect(8370, 248, 20, 22), "alive": True},
        ]
        # Breakables are collision solids until destroyed.
        for block in self.breakables:
            self.solids.append(block["rect"])

        self.spikes = [
            _rect(660, 266, 22, 18), _rect(1280, 266, 42, 18),
            _rect(1950, 263, 40, 22), _rect(2860, 264, 50, 20),
            _rect(3470, 264, 60, 20), _rect(4240, 264, 45, 20),
            _rect(4930, 430, 112, 16), _rect(5310, 430, 94, 16),
            _rect(6070, 264, 95, 20), _rect(6750, 264, 40, 20),
            _rect(7510, 264, 46, 20), _rect(8170, 264, 50, 20),
            _rect(8395, 410, 510, 10), _rect(9250, 264, 72, 20),
            _rect(10080, 264, 28, 20),
        ]
        self.lanterns = [
            {"x": 135, "y": 211, "lit": True},
            {"x": 545, "y": 213, "lit": True},
            {"x": 820, "y": 160, "lit": True},
            {"x": 1110, "y": 190, "lit": True},
            {"x": 1480, "y": 154, "lit": True},
            {"x": 1870, "y": 210, "lit": True},
            {"x": 2530, "y": 126, "lit": True},
            {"x": 2800, "y": 194, "lit": True},
            {"x": 3170, "y": 181, "lit": True},
            {"x": 3715, "y": 158, "lit": True},
            {"x": 4040, "y": 180, "lit": True},
            {"x": 4510, "y": 148, "lit": True},
            {"x": 4820, "y": 174, "lit": True},
            {"x": 5700, "y": 151, "lit": True},
            {"x": 6370, "y": 191, "lit": True},
            {"x": 6950, "y": 152, "lit": True},
            {"x": 7240, "y": 153, "lit": True},
            {"x": 7890, "y": 175, "lit": True},
            {"x": 8560, "y": 160, "lit": True},
            {"x": 8890, "y": 153, "lit": True},
            {"x": 9630, "y": 165, "lit": True},
            {"x": 10070, "y": 186, "lit": True},
        ]
        # Time Shards are placed in readable arcs and reward optional detours.
        for x, y in [
            (205, 205), (240, 180), (275, 205), (390, 174), (430, 151),
            (470, 174), (575, 205), (740, 180), (790, 153), (845, 170),
            (1045, 185), (1090, 164), (1135, 185), (1435, 185), (1480, 126),
            (1530, 185), (1710, 180), (1760, 155), (1820, 180),
            (2320, 201), (2390, 165), (2440, 153), (2605, 128),
            (2730, 196), (2860, 203), (2970, 161), (3030, 144),
            (3140, 166), (3220, 184), (3330, 158),
            (3580, 198), (3660, 159), (3760, 154), (3900, 176),
            (4050, 143), (4130, 166),
            (4470, 180), (4580, 150), (4680, 198), (4830, 146),
            (5000, 200), (5120, 178), (5280, 284), (5400, 240),
            (5630, 185), (5700, 125), (5850, 185), (6000, 160),
            (6240, 194), (6350, 155), (6480, 187), (6600, 184),
            (6870, 187), (7000, 157), (7190, 180), (7340, 154),
            (7590, 201), (7710, 160), (7860, 184), (8010, 150),
            (8320, 194), (8460, 151), (8610, 184), (8780, 152),
            (9010, 186), (9150, 157), (9430, 190), (9570, 160),
            (9730, 187), (9890, 151), (10050, 183), (10230, 183),
        ]:
            self.shards.append({"x": float(x), "y": float(y), "phase": self.random.random() * 6.2, "taken": False})

        for kind, x, y, left, right in [
            ("green", 430, 253, 380, 500), ("orange", 1010, 253, 1000, 1000),
            ("green", 1450, 253, 1400, 1575), ("orange", 1745, 253, 1745, 1745),
            ("green", 2440, 253, 2300, 2560), ("orange", 2825, 253, 2825, 2825),
            ("green", 3190, 193, 3160, 3270), ("blue", 3390, 173, 3390, 3390),
            ("green", 3660, 253, 3580, 3760), ("green", 3990, 253, 3930, 4110),
            ("blue", 4160, 205, 4160, 4160),
            ("blue", 4570, 160, 4570, 4570), ("green", 4750, 253, 4680, 4830),
            ("blue", 5830, 156, 5830, 5830),
            ("green", 6270, 253, 6200, 6380), ("orange", 6500, 253, 6500, 6500),
            ("green", 6900, 253, 6850, 7000), ("blue", 7150, 165, 7150, 7150),
            ("orange", 7350, 253, 7350, 7350), ("runner", 7700, 253, 7700, 7900),
            ("slug", 8040, 253, 8010, 8080),
            ("orange", 8380, 253, 8380, 8380), ("green", 8520, 253, 8440, 8590),
            ("slug", 8700, 253, 8670, 8750), ("green", 9050, 253, 9000, 9180),
            ("blue", 9490, 178, 9490, 9490), ("orange", 9780, 253, 9780, 9780),
            ("green", 10050, 253, 9970, 10100),
        ]:
            self._add_enemy(kind, x, y, left, right)

        # One ordinary horizontal platform, plus two true pendulum platforms.
        self.moving = [
            {"x": 1845.0, "y": 229.0, "w": 42, "h": 8, "axis": "x",
             "range": 55.0, "speed": 1.25, "phase": 0.2, "px": 1845.0, "py": 229.0},
            {"x": 4630.0, "y": 294.0, "w": 40, "h": 8, "axis": "x",
             "range": 60.0, "speed": 1.1, "phase": 1.1, "px": 4630.0, "py": 294.0},
            {"x": 6910.0, "y": 223.0, "w": 42, "h": 8, "axis": "y",
             "range": 34.0, "speed": 1.35, "phase": 2.1, "px": 6910.0, "py": 223.0},
        ]
        for obj in self.moving:
            obj["ox"], obj["oy"] = obj["x"], obj["y"]
        self.swinging = [
            {"ax": 4215.0, "ay": 156.0, "length": 95.0, "w": 42, "h": 8,
             "range": 0.62, "speed": 1.2, "phase": 0.0, "x": 4215.0, "y": 250.0,
             "px": 4215.0, "py": 250.0},
            {"ax": 8310.0, "ay": 330.0, "length": 58.0, "w": 38, "h": 8,
             "range": 0.72, "speed": 1.45, "phase": 2.0, "x": 8310.0, "y": 388.0,
             "px": 8310.0, "py": 388.0},
            {"ax": 8650.0, "ay": 330.0, "length": 58.0, "w": 38, "h": 8,
             "range": 0.72, "speed": 1.45, "phase": 0.6, "x": 8650.0, "y": 388.0,
             "px": 8650.0, "py": 388.0},
        ]
        self.falling_spikes = [
            {"x": 2740.0, "top": 92.0, "y": 92.0, "state": "wait", "timer": 1.0},
            {"x": 2955.0, "top": 88.0, "y": 88.0, "state": "wait", "timer": 1.7},
            {"x": 3160.0, "top": 100.0, "y": 100.0, "state": "wait", "timer": 2.25},
            {"x": 3530.0, "top": 82.0, "y": 82.0, "state": "wait", "timer": 1.2},
            {"x": 3860.0, "top": 80.0, "y": 80.0, "state": "wait", "timer": 2.0},
            {"x": 7080.0, "top": 88.0, "y": 88.0, "state": "wait", "timer": 1.4},
            {"x": 7590.0, "top": 83.0, "y": 83.0, "state": "wait", "timer": 2.0},
            {"x": 9430.0, "top": 80.0, "y": 80.0, "state": "wait", "timer": 1.3},
        ]
        self.saws = [
            {"x": 4470.0, "cy": 327.0, "r": 12.0, "phase": 0.0, "speed": 1.8},
            {"x": 5000.0, "cy": 360.0, "r": 12.0, "phase": 1.7, "speed": 1.45},
        ]
        self.swinging_spikes = [
            {"ax": 7240.0, "ay": 128.0, "length": 84.0, "range": 0.70, "speed": 1.15, "phase": 0.8},
            {"ax": 7830.0, "ay": 118.0, "length": 92.0, "range": 0.72, "speed": 1.3, "phase": 2.1},
            {"ax": 9600.0, "ay": 126.0, "length": 88.0, "range": 0.76, "speed": 1.2, "phase": 0.4},
        ]
        self.birds = [
            {"x": 6920.0, "y": 155.0, "phase": 0.0, "alive": True},
            {"x": 7115.0, "y": 132.0, "phase": 1.7, "alive": True},
            {"x": 7490.0, "y": 165.0, "phase": 2.3, "alive": True},
            {"x": 9720.0, "y": 149.0, "phase": 0.9, "alive": True},
        ]
        self.checkpoints = [
            {"x": 0, "y": 270, "active": True, "name": "AUTUMN GATE"},
            {"x": 2112, "y": 355, "active": False, "name": "FIRST SHOP PORTAL"},
            {"x": 3330, "y": 270, "active": False, "name": "OLD ROOTS"},
            {"x": 6410, "y": 252, "active": False, "name": "SECOND SHOP PORTAL"},
            {"x": 8330, "y": 420, "active": False, "name": "POWER SEAL SHRINE"},
            {"x": 10230, "y": 270, "active": False, "name": "FINAL SHOP"},
        ]
        self.shops = [
            {"x": 2112, "y": 360, "opened": False},
            {"x": 6410, "y": 252, "opened": False},
            {"x": 10230, "y": 252, "opened": False},
        ]
        self.potions = [
            {"rect": _rect(3260, 164, 12, 16), "taken": False},
            {"rect": _rect(4615, 275, 12, 16), "taken": False},
            {"rect": _rect(5815, 142, 12, 16), "taken": False},
            {"rect": _rect(7960, 174, 12, 16), "taken": False},
            {"rect": _rect(9630, 145, 12, 16), "taken": False},
            {"rect": _rect(10170, 180, 12, 16), "taken": False},
        ]
        self.boss = {
            "x": 10700.0, "y": 213.0, "hp": 20, "max_hp": 20,
            "active": False, "defeated": False, "state": "idle",
            "timer": 1.25, "phase": 0.0, "flash": 0.0,
            "vulnerable": 0.0, "leaf_return": False,
        }
        self.boss_shots = []
        self.gate_open = False
        self.discovered = {0}
        self.collected_seals = 0

    def _reset_player(self):
        self.player = {
            "x": 78.0, "y": 247.0, "vx": 0.0, "vy": 0.0,
            "w": 14, "h": 22, "ground": False, "facing": 1,
            "hp": 6, "max_hp": 6, "invuln": 0.0,
            "jump_buffer": 0.0, "coyote": 0.0,
            "jump_held": False, "cloudstep": False,
            "attack": 0.0, "attack_cd": 0.0, "shuriken_cd": 0.0,
            "cling": False, "cling_side": 0, "crouch": False,
            "swim_burst": 0.0,
        }
        self.climbing_claws = False
        self.strike_upgrade = False
        self.energy_shuriken = False
        self.karuta_plates = False
        self.shards_count = 0
        self.power_seals = 0
        self.checkpoint_index = 0
        self.deaths = 0
        self.quarble_timer = 0.0
        self.quarble_x = 0.0
        self.quarble_y = 0.0
        self.shop_open = False
        self.paused = False
        self.map_open = False
        self.victory = False
        self.game_over = False
        self.completed = False

    # ------------------------------------------------------------------
    # Events and progression
    # ------------------------------------------------------------------
    def _set_banner(self, name, subtitle=""):
        self.banner_name = name
        self.banner_subtitle = subtitle
        self.banner_timer = 2.2

    def handle_event(self, event):
        """Return True when the host should leave this mode."""
        if event.type == pygame.KEYUP:
            if event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                self.player["jump_held"] = False
            return False
        if event.type != pygame.KEYDOWN:
            return False

        key = event.key
        if self.victory or self.game_over:
            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return True
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.game_over:
                    self._restart_attempt()
                else:
                    return True
            return False

        if self.shop_open:
            count = 5
            if key in (pygame.K_ESCAPE, pygame.K_UP):
                if key == pygame.K_ESCAPE:
                    self.shop_open = False
                else:
                    self.shop_cursor = (self.shop_cursor - 1) % count
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.shop_cursor = (self.shop_cursor + 1) % count
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self._shop_action()
            return False

        if self.map_open:
            if key in (pygame.K_m, pygame.K_ESCAPE, pygame.K_TAB):
                self.map_open = False
            return False

        if self.paused:
            if key in (pygame.K_ESCAPE, pygame.K_p):
                self.paused = False
            elif key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                self.pause_selection = 1 - self.pause_selection
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.pause_selection == 0:
                    self.paused = False
                else:
                    return True
            return False

        if key in (pygame.K_ESCAPE, pygame.K_p):
            self.paused = True
            self.pause_selection = 0
        elif key in (pygame.K_m, pygame.K_TAB):
            self.map_open = True
        elif key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
            near_portal = any(
                abs((self.player["x"] + self.player["w"] / 2) - shop["x"]) < 48
                and abs((self.player["y"] + self.player["h"] / 2) - shop["y"]) < 70
                for shop in self.shops
            )
            if key in (pygame.K_w, pygame.K_UP) and near_portal:
                self._interact()
            else:
                self.player["jump_buffer"] = 0.14
                self.player["jump_held"] = True
                if self._in_water():
                    self.player["swim_burst"] = 0.32
        elif key in (pygame.K_j, pygame.K_c, pygame.K_z):
            self._attack()
        elif key in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_x):
            self._throw_shuriken()
        elif key in (pygame.K_e, pygame.K_RETURN):
            self._interact()
        return False

    def _restart_attempt(self):
        old_deaths = self.deaths + 1
        old_shards = self.shards_count
        old_seals = self.power_seals
        old_claws = self.climbing_claws
        old_strike = self.strike_upgrade
        old_shuriken = self.energy_shuriken
        old_karuta = self.karuta_plates
        checkpoint_index = self.checkpoint_index
        self._build_world()
        self._reset_player()
        self.deaths = old_deaths
        self.shards_count = old_shards
        self.power_seals = old_seals
        self.climbing_claws = old_claws
        self.strike_upgrade = old_strike
        self.energy_shuriken = old_shuriken
        self.karuta_plates = old_karuta
        self.checkpoint_index = min(checkpoint_index, len(self.checkpoints) - 1)
        self._respawn(initial=True)

    def _interact(self):
        px = self.player["x"] + self.player["w"] / 2
        py = self.player["y"] + self.player["h"] / 2
        for i, shop in enumerate(self.shops):
            if abs(px - shop["x"]) < 48 and abs(py - shop["y"]) < 70:
                self.shop_index = i
                self.shop_cursor = 0
                self.shop_open = True
                cp_i = min(range(len(self.checkpoints)),
                           key=lambda j: abs(self.checkpoints[j]["x"] - shop["x"]))
                self.checkpoints[cp_i]["active"] = True
                self.checkpoint_index = max(self.checkpoint_index, cp_i)
                if i == 0 and not self.climbing_claws:
                    self.climbing_claws = True
                    self.dialog_text = "CLIMBING CLAWS ACQUIRED"
                else:
                    self.dialog_text = "THE SHOPKEEPER HAS NEW SUPPLIES"
                self.dialog_timer = 3.0
                shop["opened"] = True
                return
        if abs(px - 8330) < 65 and self.player["y"] > 340:
            self.checkpoints[4]["active"] = True
            self.checkpoint_index = max(self.checkpoint_index, 4)

    def _shop_items(self):
        return [
            ("CLIMBING CLAWS", 0, "Grip and climb rough walls.", "claws"),
            ("STRIKE OF THE NINJA", 28, "Destroy enemy fireballs and cloudstep from them.", "strike"),
            ("ENERGY SHURIKEN", 32, "Throw a ranged shuriken with SHIFT.", "shuriken"),
            ("KARUTA PLATES", 36, "Increase maximum health by one.", "karuta"),
            ("LEAVE THE SHOP", 0, "Return to Autumn Hills.", "leave"),
        ]

    def _shop_action(self):
        title, cost, desc, item = self._shop_items()[self.shop_cursor]
        if item == "leave":
            self.shop_open = False
            return
        if item == "claws":
            self.climbing_claws = True
            self.dialog_text = "CLIMBING CLAWS READY"
        elif item == "strike":
            if self.strike_upgrade:
                self.dialog_text = "ALREADY PURCHASED"
            elif self.shards_count >= cost:
                self.shards_count -= cost
                self.strike_upgrade = True
                self.dialog_text = "STRIKE OF THE NINJA PURCHASED"
            else:
                self.dialog_text = "NOT ENOUGH TIME SHARDS"
        elif item == "shuriken":
            if self.energy_shuriken:
                self.dialog_text = "ALREADY PURCHASED"
            elif self.shards_count >= cost:
                self.shards_count -= cost
                self.energy_shuriken = True
                self.dialog_text = "ENERGY SHURIKEN PURCHASED"
            else:
                self.dialog_text = "NOT ENOUGH TIME SHARDS"
        elif item == "karuta":
            if self.karuta_plates:
                self.dialog_text = "ALREADY PURCHASED"
            elif self.shards_count >= cost:
                self.shards_count -= cost
                self.karuta_plates = True
                self.player["max_hp"] += 1
                self.player["hp"] = self.player["max_hp"]
                self.dialog_text = "KARUTA PLATES EQUIPPED"
            else:
                self.dialog_text = "NOT ENOUGH TIME SHARDS"
        self.dialog_timer = 2.0

    # ------------------------------------------------------------------
    # Combat and interactions
    # ------------------------------------------------------------------
    def _player_rect(self):
        p = self.player
        h = 13 if p["crouch"] else p["h"]
        y = p["y"] + (p["h"] - h)
        return _rect(p["x"], y, p["w"], h)

    def _attack(self):
        p = self.player
        if p["attack_cd"] > 0 or self.paused or self.shop_open:
            return
        p["attack"] = 0.16
        p["attack_cd"] = 0.31
        px = p["x"] + (p["w"] if p["facing"] > 0 else 0)
        sword = _rect(px - (0 if p["facing"] > 0 else 28), p["y"] + 5, 28, 14)
        hit_any = False
        for enemy in self.enemies:
            if enemy["alive"] and sword.colliderect(self._enemy_rect(enemy)):
                enemy["hp"] -= 1
                enemy["flash"] = 0.12
                hit_any = True
                if enemy["hp"] <= 0:
                    enemy["alive"] = False
        for lantern in self.lanterns:
            if lantern["lit"] and abs(lantern["x"] - px) < 46 and abs(lantern["y"] - (p["y"] + 10)) < 34:
                lantern["lit"] = False
                hit_any = True
                for i in range(5):
                    self.shards.append({
                        "x": lantern["x"] + (i - 2) * 8.0,
                        "y": lantern["y"] - 13 - abs(i - 2) * 4,
                        "phase": i * 0.7, "taken": False,
                    })
        for block in self.breakables:
            if block["alive"] and sword.colliderect(block["rect"]):
                block["alive"] = False
                if block["rect"] in self.solids:
                    self.solids.remove(block["rect"])
                hit_any = True
                for i in range(3):
                    self.shards.append({
                        "x": block["rect"].centerx + (i - 1) * 6,
                        "y": block["rect"].centery - 12,
                        "phase": i * 0.8, "taken": False,
                    })
        for shot in self.projectiles:
            if shot["alive"] and sword.colliderect(_rect(shot["x"] - 4, shot["y"] - 4, 8, 8)):
                if self.strike_upgrade:
                    shot["alive"] = False
                    hit_any = True
                    p["cloudstep"] = True
        for bird in self.birds:
            if bird["alive"] and sword.colliderect(_rect(bird["x"] - 7, bird["y"] - 5, 14, 10)):
                bird["alive"] = False
                p["cloudstep"] = True
                hit_any = True
        if self.boss["active"] and not self.boss["defeated"]:
            if sword.colliderect(self._boss_rect()) and self.boss["vulnerable"] > 0:
                self.boss["hp"] = max(0, self.boss["hp"] - 1)
                self.boss["flash"] = 0.13
                hit_any = True
                self.boss["vulnerable"] = 0.0
                if self.boss["hp"] == 0:
                    self.boss["defeated"] = True
                    self.boss["state"] = "defeated"
                    self.boss_shots.clear()
                    self._set_banner("LEAF MONSTER DEFEATED", "The vines withdraw. The road east is open.")
        if hit_any and not p["ground"]:
            p["cloudstep"] = True

    def _throw_shuriken(self):
        p = self.player
        if not self.energy_shuriken or p["shuriken_cd"] > 0:
            return
        self.projectiles.append({
            "x": p["x"] + p["w"] / 2, "y": p["y"] + 9,
            "vx": p["facing"] * 265.0, "vy": -12.0,
            "life": 1.45, "alive": True, "friendly": True,
        })
        p["shuriken_cd"] = 0.62

    def _enemy_rect(self, enemy):
        if enemy["kind"] == "slug":
            return _rect(enemy["x"] - 8, enemy["y"] + 7, 16, 8)
        if enemy["kind"] == "orange":
            return _rect(enemy["x"] - 9, enemy["y"] - 16, 18, 20)
        if enemy["kind"] == "blue":
            return _rect(enemy["x"] - 8, enemy["y"] - 18, 16, 20)
        return _rect(enemy["x"] - 8, enemy["y"] - 18, 16, 20)

    def _boss_rect(self):
        return _rect(self.boss["x"] - 25, self.boss["y"] - 30, 50, 38)

    def _in_water(self):
        center = (self.player["x"] + 7, self.player["y"] + 11)
        return any(rect.collidepoint(center) for rect in self.water)

    # ------------------------------------------------------------------
    # Physics and frame update
    # ------------------------------------------------------------------
    def update(self, dt):
        dt = max(0.0, min(float(dt), 0.04))
        self.elapsed += dt
        self.banner_timer = max(0.0, self.banner_timer - dt)
        self.dialog_timer = max(0.0, self.dialog_timer - dt)
        if self.paused or self.map_open or self.shop_open or self.victory or self.game_over:
            return

        p = self.player
        p["invuln"] = max(0.0, p["invuln"] - dt)
        p["attack"] = max(0.0, p["attack"] - dt)
        p["attack_cd"] = max(0.0, p["attack_cd"] - dt)
        p["shuriken_cd"] = max(0.0, p["shuriken_cd"] - dt)
        p["jump_buffer"] = max(0.0, p["jump_buffer"] - dt)
        p["coyote"] = max(0.0, p["coyote"] - dt)
        p["swim_burst"] = max(0.0, p["swim_burst"] - dt)
        p["crouch"] = bool(pygame.key.get_pressed()[pygame.K_DOWN] or pygame.key.get_pressed()[pygame.K_s])

        keys = pygame.key.get_pressed()
        move = int(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - int(keys[pygame.K_LEFT] or keys[pygame.K_a])
        if move:
            p["facing"] = 1 if move > 0 else -1
        wet = self._in_water()
        speed = 102.0 if wet else 132.0
        p["vx"] = move * speed
        if wet and any(current.colliderect(self._player_rect()) for current in self.currents):
            p["vx"] += 52.0
        if p["cling"]:
            if not self.climbing_claws:
                p["cling"] = False
            elif p["jump_buffer"] > 0:
                p["vy"] = -286.0
                p["vx"] = -p["cling_side"] * 170.0
                p["cling"] = False
                p["ground"] = False
                p["jump_buffer"] = 0.0
            else:
                p["vx"] = 0.0
                p["vy"] = 0.0
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    p["y"] -= 82 * dt
                elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    p["y"] += 82 * dt
                else:
                    p["vy"] = 0.0
        else:
            if wet:
                p["vy"] += 230 * dt
                p["vy"] = min(92.0, p["vy"])
                if keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE]:
                    p["vy"] = -115.0
                if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    p["vy"] = 125.0
                if p["swim_burst"] > 0:
                    p["vy"] = -172.0
            else:
                p["vy"] = min(420.0, p["vy"] + 620.0 * dt)
                if p["jump_buffer"] > 0 and p["ground"]:
                    p["vy"] = -286.0
                    p["ground"] = False
                    p["coyote"] = 0.0
                    p["jump_buffer"] = 0.0
                    p["cloudstep"] = False
                elif p["jump_buffer"] > 0 and p["coyote"] > 0:
                    p["vy"] = -286.0
                    p["ground"] = False
                    p["coyote"] = 0.0
                    p["jump_buffer"] = 0.0
                elif p["jump_buffer"] > 0 and p["cloudstep"]:
                    p["vy"] = -270.0
                    p["cloudstep"] = False
                    p["jump_buffer"] = 0.0

        # Update moving and pendulum platforms before resolving the player.
        dynamic = []
        for obj in self.moving + self.swinging:
            obj["px"], obj["py"] = obj["x"], obj["y"]
            if "ax" in obj:
                angle = math.sin(self.elapsed * obj["speed"] + obj["phase"]) * obj["range"]
                obj["x"] = obj["ax"] + math.sin(angle) * obj["length"]
                obj["y"] = obj["ay"] + math.cos(angle) * obj["length"]
            else:
                offset = math.sin(self.elapsed * obj["speed"] + obj["phase"]) * obj["range"]
                if obj["axis"] == "x":
                    obj["x"] = obj.get("ox", obj["x"]) + offset
                else:
                    obj["y"] = obj.get("oy", obj["y"]) + offset
            dynamic.append((_rect(obj["x"], obj["y"], obj["w"], obj["h"]),
                            obj["x"] - obj["px"], obj["y"] - obj["py"]))

        solids = self.solids + [r for r, _, _ in dynamic]
        old = self._player_rect()
        # Carry the runner only when their feet were resting on a moving surface.
        for rect, dx, dy in dynamic:
            if abs(old.bottom - rect.top) <= 4 and old.right > rect.left + 2 and old.left < rect.right - 2 and p["ground"]:
                p["x"] += dx
                p["y"] += dy
                old = self._player_rect()
                break

        p["x"] += p["vx"] * dt
        rect = self._player_rect()
        p["cling"] = False
        for solid in solids:
            if rect.colliderect(solid):
                if p["vx"] > 0:
                    rect.right = solid.left
                elif p["vx"] < 0:
                    rect.left = solid.right
                p["x"] = float(rect.x)
                if self.climbing_claws and not wet and move != 0:
                    p["cling"] = True
                    p["cling_side"] = 1 if move > 0 else -1
                    p["vy"] = 0.0

        p["y"] += p["vy"] * dt
        rect = self._player_rect()
        p["ground"] = False
        for solid in solids:
            if rect.colliderect(solid):
                if p["vy"] > 0:
                    rect.bottom = solid.top
                    p["ground"] = True
                    p["coyote"] = 0.10
                    p["cloudstep"] = False
                elif p["vy"] < 0:
                    rect.top = solid.bottom
                p["y"] = float(rect.y - (p["h"] - rect.h))
                p["vy"] = 0.0

        # Keep the runner inside the world and allow the intentional first-shop drop.
        p["x"] = max(0.0, min(WORLD_W - 18.0, p["x"]))
        if p["y"] > WORLD_H - 35:
            self._damage(99)
            return

        # Falling spike balls reset from the canopy after striking the ground.
        for hazard in self.falling_spikes:
            hazard["timer"] -= dt
            if hazard["state"] == "wait" and hazard["timer"] <= 0:
                hazard["state"] = "fall"
            elif hazard["state"] == "fall":
                hazard["y"] += 180 * dt
                if hazard["y"] > GROUND_Y + 4:
                    hazard["state"] = "wait"
                    hazard["y"] = hazard["top"]
                    hazard["timer"] = self.random.uniform(1.4, 2.8)
            if hazard["state"] == "fall" and _rect(hazard["x"] - 7, hazard["y"], 14, 17).colliderect(self._player_rect()):
                self._damage(1)

        for shot in self.projectiles:
            shot["life"] -= dt
            shot["x"] += shot["vx"] * dt
            shot["y"] += shot["vy"] * dt
            shot["vy"] += 95 * dt if shot["friendly"] else 130 * dt
            if shot["life"] <= 0 or shot["x"] < self.camera_x - 60 or shot["x"] > self.camera_x + VIEW_W + 100:
                shot["alive"] = False
            if shot["friendly"]:
                for enemy in self.enemies:
                    if enemy["alive"] and _rect(shot["x"] - 4, shot["y"] - 4, 8, 8).colliderect(self._enemy_rect(enemy)):
                        enemy["hp"] -= 1
                        enemy["flash"] = 0.12
                        shot["alive"] = False
                        if enemy["hp"] <= 0:
                            enemy["alive"] = False
                        break
            elif shot["alive"] and p["invuln"] <= 0 and _rect(shot["x"] - 4, shot["y"] - 4, 8, 8).colliderect(self._player_rect()):
                shot["alive"] = False
                self._damage(1)
        self.projectiles = [s for s in self.projectiles if s["alive"]]

        # Enemy routines: harmless walkers, fixed fire spitters and arcing casters.
        for bird in self.birds:
            bird["phase"] += dt * 5.0

        for enemy in self.enemies:
            if not enemy["alive"]:
                continue
            enemy["phase"] += dt * 4.0
            enemy["flash"] = max(0.0, enemy["flash"] - dt)
            kind = enemy["kind"]
            if kind in ("green", "slug"):
                enemy["x"] += enemy["dir"] * (22 if kind == "green" else 35) * dt
                if enemy["x"] < enemy["left"] or enemy["x"] > enemy["right"]:
                    enemy["dir"] *= -1
                    enemy["x"] = max(enemy["left"], min(enemy["right"], enemy["x"]))
            elif kind == "runner":
                if abs(enemy["x"] - p["x"]) < 185:
                    enemy["x"] += (1 if p["x"] > enemy["x"] else -1) * 86 * dt
                else:
                    enemy["x"] += enemy["dir"] * 22 * dt
            else:
                enemy["timer"] -= dt
                if enemy["timer"] <= 0 and abs(enemy["x"] - p["x"]) < 420:
                    dx = (1 if p["x"] > enemy["x"] else -1)
                    if kind == "orange":
                        self.projectiles.append({
                            "x": enemy["x"], "y": enemy["y"] - 7,
                            "vx": dx * 118, "vy": -7, "life": 2.1,
                            "alive": True, "friendly": False,
                        })
                        enemy["timer"] = 2.0
                    elif kind == "blue":
                        self.projectiles.append({
                            "x": enemy["x"], "y": enemy["y"] - 12,
                            "vx": dx * 100, "vy": -94, "life": 2.4,
                            "alive": True, "friendly": False,
                        })
                        enemy["timer"] = 2.55

            if self._player_rect().colliderect(self._enemy_rect(enemy)) and p["invuln"] <= 0:
                self._damage(1)

        # Pendulum spike balls swing across the late forest routes.
        for hazard in self.swinging_spikes:
            angle = math.sin(self.elapsed * hazard["speed"] + hazard["phase"]) * hazard["range"]
            hx = hazard["ax"] + math.sin(angle) * hazard["length"]
            hy = hazard["ay"] + math.cos(angle) * hazard["length"]
            if _rect(hx - 10, hy - 10, 20, 20).colliderect(self._player_rect()):
                self._damage(2)

        # Spinning saws orbit a fixed point inside the flooded tunnel.
        for saw in self.saws:
            saw["phase"] += dt * saw["speed"]
            sx = saw["x"] + math.sin(saw["phase"]) * 32
            sy = saw["cy"] + math.cos(saw["phase"] * 1.15) * 18
            if _rect(sx - saw["r"], sy - saw["r"], saw["r"] * 2, saw["r"] * 2).colliderect(self._player_rect()):
                self._damage(1)

        # Hazards and collectibles.
        for spike in self.spikes:
            if spike.colliderect(self._player_rect()):
                self._damage(3)
        for shard in self.shards:
            if not shard["taken"]:
                shard["phase"] += dt * 3.0
                if _rect(shard["x"] - 4, shard["y"] - 5, 8, 10).colliderect(self._player_rect()):
                    shard["taken"] = True
                    self.shards_count += 1
        for potion in self.potions:
            if not potion["taken"] and potion["rect"].colliderect(self._player_rect()):
                potion["taken"] = True
                p["hp"] = min(p["max_hp"], p["hp"] + 3)
                self._set_banner("HEALTH RESTORED", "+3")
        if not self.seal["found"] and self.seal["rect"].colliderect(self._player_rect()):
            self.seal["found"] = True
            self.power_seals += 1
            self.gate_open = True
            if self.seal_gate in self.solids:
                self.solids.remove(self.seal_gate)
            self._set_banner("POWER SEAL", "A secret challenge completed.")

        # The lower seal chamber has a hidden checkpoint below the breakable floor.
        if 8240 <= p["x"] <= 9000 and p["y"] > 330 and not self.checkpoints[4]["active"]:
            self.checkpoints[4]["active"] = True
            self.checkpoint_index = max(self.checkpoint_index, 4)
            self._set_banner("CHECKPOINT", "BROKEN SHRINE")

        # Checkpoints remember a safe return point; a shop is also a checkpoint.
        for i, cp in enumerate(self.checkpoints):
            if abs(p["x"] - cp["x"]) < 22 and abs(p["y"] - cp["y"]) < 48:
                if not cp["active"]:
                    cp["active"] = True
                    self._set_banner("CHECKPOINT", cp["name"])
                self.checkpoint_index = max(self.checkpoint_index, i)

        # The Quarble-like shard thief appears only after a death.
        if self.quarble_timer > 0:
            self.quarble_timer -= dt
            self.quarble_x += (p["x"] - self.quarble_x) * min(1.0, dt * 1.8)
            self.quarble_y += (p["y"] - 28 - self.quarble_y) * min(1.0, dt * 1.5)
            if abs(self.quarble_x - p["x"]) < 24 and self.shards_count > 0 and self.random.random() < dt * 1.4:
                self.shards_count = max(0, self.shards_count - 1)
            if self.quarble_timer <= 0:
                self.quarble_timer = 0.0

        self._update_boss(dt)
        self._update_room_discovery()
        self.camera_x = max(0.0, min(WORLD_W - VIEW_W, p["x"] - VIEW_W * 0.43))
        target_y = max(0.0, min(WORLD_H - VIEW_H, p["y"] - VIEW_H * 0.56))
        self.camera_y += (target_y - self.camera_y) * min(1.0, dt * 5.0)
        if self.banner_timer > 0:
            self.banner_timer = max(0.0, self.banner_timer - dt)

    def _update_room_discovery(self):
        x = self.player["x"]
        for i, (left, right, name) in enumerate(self.rooms):
            if left <= x < right and i not in self.discovered:
                self.discovered.add(i)
                self._set_banner(name, "Keep moving. Watch the lanterns.")
                break

    def _damage(self, amount):
        p = self.player
        if p["invuln"] > 0 or self.game_over or self.victory:
            return
        p["hp"] -= amount
        p["invuln"] = 1.0
        if amount >= 3:
            self._set_banner("SPIKES", "The sharpest hazards hit hard.")
        if p["hp"] <= 0:
            self.deaths += 1
            self.shards_count = max(0, self.shards_count - min(8, self.shards_count // 3))
            self.quarble_timer = 28.0
            self.quarble_x = p["x"] - 42
            self.quarble_y = p["y"] - 25
            self._respawn()
        else:
            p["hp"] = max(0, p["hp"])

    def _respawn(self, initial=False):
        cp = self.checkpoints[self.checkpoint_index]
        self.player.update({
            "x": float(cp["x"] + 4), "y": float(cp["y"] - 22),
            "vx": 0.0, "vy": 0.0, "ground": False,
            "hp": self.player["max_hp"], "invuln": 1.7,
            "cling": False, "cloudstep": False,
            "jump_buffer": 0.0, "coyote": 0.0,
        })
        self.camera_x = max(0.0, min(WORLD_W - VIEW_W, self.player["x"] - VIEW_W * 0.4))
        self.camera_y = 0.0
        self._set_banner("CHECKPOINT RESTORED", cp["name"])

    # ------------------------------------------------------------------
    # Leaf Monster encounter
    # ------------------------------------------------------------------
    def _update_boss(self, dt):
        b = self.boss
        if not b["active"] and self.player["x"] > 10420:
            b["active"] = True
            self.player["x"] = max(self.player["x"], 10420)
            self._set_banner("LEAF MONSTER", "Watch its leaves. Strike when its guard opens.")
        if not b["active"] or b["defeated"]:
            if b["defeated"] and self.player["x"] > 11100:
                self.victory = True
                self.completed = True
            return
        b["phase"] += dt
        b["flash"] = max(0.0, b["flash"] - dt)
        b["vulnerable"] = max(0.0, b["vulnerable"] - dt)
        b["timer"] -= dt

        if b["state"] == "idle" and b["timer"] <= 0:
            if self.random.random() < 0.55:
                b["state"] = "ground_windup"
                b["timer"] = 0.55
            else:
                b["state"] = "high_windup"
                b["timer"] = 0.7
        elif b["state"] == "ground_windup" and b["timer"] <= 0:
            dx = 1 if self.player["x"] >= b["x"] else -1
            self.boss_shots.append({
                "x": b["x"], "y": b["y"] - 12, "vx": dx * 122,
                "vy": -14, "life": 2.4, "turn": False, "split": False,
            })
            b["state"] = "recover"
            b["timer"] = 1.15
            b["vulnerable"] = 0.48
        elif b["state"] == "high_windup" and b["timer"] <= 0:
            b["state"] = "high_attack"
            b["timer"] = 1.1
            b["y"] = 166
            for direction in (-1, 1):
                self.boss_shots.append({
                    "x": b["x"], "y": b["y"] + 22,
                    "vx": direction * 105, "vy": 28,
                    "life": 2.4, "turn": False, "split": True,
                })
            b["vulnerable"] = 0.28
        elif b["state"] in ("recover", "high_attack") and b["timer"] <= 0:
            b["state"] = "idle"
            b["y"] = 213.0
            b["timer"] = 0.8 if b["hp"] > 10 else 0.52

        for shot in self.boss_shots:
            shot["life"] -= dt
            shot["x"] += shot["vx"] * dt
            shot["y"] += shot["vy"] * dt
            if shot["split"]:
                shot["vy"] += 110 * dt
            else:
                shot["vy"] += 42 * dt
            if shot["life"] < 1.0 and not shot["turn"]:
                shot["vx"] *= -1
                shot["turn"] = True
                shot["split"] = False
            if shot["life"] <= 0:
                shot["life"] = 0
            if shot["life"] > 0 and _rect(shot["x"] - 5, shot["y"] - 5, 10, 10).colliderect(self._player_rect()):
                if self.player["invuln"] <= 0:
                    shot["life"] = 0
                    self._damage(1)
        self.boss_shots = [s for s in self.boss_shots if s["life"] > 0]

        if self._boss_rect().colliderect(self._player_rect()) and self.player["invuln"] <= 0:
            self._damage(1)

    # ------------------------------------------------------------------
    # Drawing: bespoke pixel art, HUD and world map
    # ------------------------------------------------------------------
    def _text(self, text, pos, color=WHITE, font=None, center=False):
        surf = (font or self.font).render(str(text), False, color)
        rect = surf.get_rect()
        if center:
            rect.center = (int(pos[0]), int(pos[1]))
        else:
            rect.topleft = (int(pos[0]), int(pos[1]))
        self.frame.blit(surf, rect)

    def _draw_background(self):
        f = self.frame
        f.fill(SKY)
        # Layered dusk gradient and distant ridgelines.
        for y in range(VIEW_H):
            mix = y / VIEW_H
            col = (int(28 + 10 * mix), int(22 + 7 * mix), int(66 + 12 * mix))
            pygame.draw.line(f, col, (0, y), (VIEW_W, y))
        for x, y, size, phase in self.stars:
            sx = int(x - self.camera_x * 0.12) % VIEW_W
            sy = int(y - self.camera_y * 0.06)
            if (int(self.elapsed * 2 + phase) % 5) == 0:
                pygame.draw.rect(f, (106, 109, 163), (sx, sy, size, size))
        moon_x = int(422 - self.camera_x * 0.055)
        moon_y = int(62 - self.camera_y * 0.04)
        pygame.draw.circle(f, (99, 84, 142), (moon_x + 2, moon_y + 2), 43)
        pygame.draw.circle(f, MOON, (moon_x, moon_y), 39)
        pygame.draw.circle(f, (176, 152, 198), (moon_x - 12, moon_y - 8), 6)
        pygame.draw.circle(f, (133, 110, 165), (moon_x + 13, moon_y + 12), 8)
        pygame.draw.circle(f, (133, 110, 165), (moon_x - 19, moon_y + 15), 4)
        for layer, color, offset, peak in [
            (0, (63, 57, 104), 0.10, 126),
            (1, (43, 43, 79), 0.18, 160),
            (2, (31, 33, 60), 0.28, 195),
        ]:
            shift = int(self.camera_x * offset) % 260
            pts = [(-260 - shift, 260)]
            for x in range(-260 - shift, VIEW_W + 300, 55):
                pts.append((x, peak - ((x // 55 + layer) % 3) * 18))
            pts.extend([(VIEW_W + 20, VIEW_H), (-260 - shift, VIEW_H)])
            pygame.draw.polygon(f, color, pts)
        # The red forest scrolls at different speeds; trunks and crowns use
        # chunky blocks to keep the original hand-built pixel silhouette feel.
        for tree_x in range(-180, WORLD_W + 250, 235):
            sx = int(tree_x - self.camera_x * 0.48)
            if -95 <= sx <= VIEW_W + 95:
                base = 224 - int(self.camera_y * 0.12)
                pygame.draw.rect(f, (43, 33, 43), (sx + 20, base - 65, 11, 90))
                pygame.draw.rect(f, (65, 43, 52), (sx + 15, base - 40, 7, 8))
                for ox, oy, radius in [(-9, -61, 22), (12, -77, 25), (34, -59, 22), (8, -48, 21)]:
                    pygame.draw.circle(f, LEAF_RED, (sx + 24 + ox, base + oy), radius)
                    pygame.draw.rect(f, LEAF_LIGHT, (sx + 18 + ox, base + oy - 10, 8, 6))
        # Subtle foreground branches frame but never obscure the play route.
        for x in range(-20, VIEW_W + 80, 145):
            sx = x - int((self.camera_x * 0.75) % 145)
            pygame.draw.rect(f, (37, 31, 43), (sx, 0, 5, 44))
            pygame.draw.circle(f, (91, 39, 56), (sx + 6, 17), 16)

    def _world_rect(self, rect):
        return _rect(rect.x - self.camera_x, rect.y - self.camera_y, rect.w, rect.h)

    def _draw_terrain(self):
        f = self.frame
        for platform in self.platforms:
            r = self._world_rect(platform["rect"])
            if r.right < -20 or r.left > VIEW_W + 20 or r.bottom < -20 or r.top > VIEW_H + 25:
                continue
            kind = platform["kind"]
            base = (58, 46, 55) if kind != "underwater" else (48, 63, 76)
            pygame.draw.rect(f, base, r)
            pygame.draw.rect(f, MOSS if kind not in ("underwater", "secret_floor") else (76, 104, 87),
                             (r.x, r.y, r.w, 3))
            for tx in range(r.left + 3, r.right - 2, 8):
                pygame.draw.rect(f, (94, 68, 69), (tx, r.y + 5, 3, 2))
            for tx in range(r.left + 7, r.right - 3, 16):
                pygame.draw.rect(f, (37, 31, 42), (tx, r.bottom - 5, 4, 3))
        for block in self.breakables:
            if block["alive"]:
                r = self._world_rect(block["rect"])
                pygame.draw.rect(f, (115, 78, 57), r)
                pygame.draw.rect(f, (174, 115, 75), (r.x + 2, r.y + 2, r.w - 4, 3))
                pygame.draw.line(f, (55, 42, 46), r.topleft, r.bottomright, 1)
        for spike in self.spikes:
            r = self._world_rect(spike)
            if r.right < 0 or r.left > VIEW_W:
                continue
            pygame.draw.rect(f, (39, 34, 51), (r.x, r.bottom - 3, r.w, 4))
            for x in range(r.left, r.right, 8):
                pygame.draw.polygon(f, (179, 188, 196),
                                    [(x, r.bottom - 2), (x + 4, r.top), (x + 8, r.bottom - 2)])
                pygame.draw.line(f, WHITE, (x + 4, r.top + 2), (x + 4, r.bottom - 3), 1)
        if not self.gate_open:
            gate = self._world_rect(self.seal_gate)
            pygame.draw.rect(f, (74, 57, 74), gate)
            pygame.draw.rect(f, (176, 126, 110), (gate.x, gate.y, gate.w, 4))
            pygame.draw.line(f, (39, 31, 49), gate.topleft, gate.bottomright, 2)
        for rect in self.water:
            r = self._world_rect(rect)
            if r.right < 0 or r.left > VIEW_W:
                continue
            overlay = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            overlay.fill((45, 105, 139, 145))
            f.blit(overlay, r.topleft)
            for yy in range(r.y + 5, r.bottom, 13):
                wave_x = int(6 * math.sin(self.elapsed * 2 + yy))
                pygame.draw.line(f, (105, 189, 202), (r.x + 2 + wave_x, yy),
                                 (min(r.right - 2, r.x + 30 + wave_x), yy), 1)
        # Currents are visible as small streams of bubbles and arrows.
        for rect in self.currents:
            r = self._world_rect(rect)
            if r.right > 0 and r.left < VIEW_W:
                for i in range(5):
                    bx = r.x + 8 + ((i * 19 + int(self.elapsed * 18)) % max(12, r.w - 12))
                    by = r.y + 5 + (i * 9) % max(10, r.h - 8)
                    pygame.draw.circle(f, (156, 215, 214), (bx, by), 1)

    def _draw_lanterns(self):
        for lantern in self.lanterns:
            sx = int(lantern["x"] - self.camera_x)
            sy = int(lantern["y"] - self.camera_y)
            if not -20 <= sx <= VIEW_W + 20:
                continue
            pygame.draw.rect(self.frame, (76, 69, 69), (sx - 2, sy + 6, 4, 17))
            pygame.draw.rect(self.frame, (148, 112, 75), (sx - 5, sy + 3, 10, 3))
            col = (244, 190, 99) if lantern["lit"] else (87, 74, 81)
            pygame.draw.rect(self.frame, (48, 44, 57), (sx - 5, sy - 6, 10, 10))
            pygame.draw.rect(self.frame, col, (sx - 3, sy - 4, 6, 6))
            pygame.draw.rect(self.frame, WHITE if lantern["lit"] else (111, 105, 115),
                             (sx - 1, sy - 7, 2, 2))

    def _draw_collectibles(self):
        for shard in self.shards:
            if shard["taken"]:
                continue
            sx = int(shard["x"] - self.camera_x)
            sy = int(shard["y"] + math.sin(shard["phase"]) * 2 - self.camera_y)
            if -10 <= sx <= VIEW_W + 10:
                pygame.draw.polygon(self.frame, SHARD,
                                    [(sx, sy - 5), (sx + 4, sy), (sx, sy + 5), (sx - 4, sy)])
                pygame.draw.line(self.frame, (199, 250, 250), (sx, sy - 3), (sx, sy + 1), 1)
        if not self.seal["found"]:
            r = self._world_rect(self.seal["rect"])
            if r.right >= 0 and r.left <= VIEW_W:
                pygame.draw.circle(self.frame, (40, 114, 95), r.center, 13, 2)
                pygame.draw.circle(self.frame, (115, 211, 143), r.center, 9)
                pygame.draw.polygon(self.frame, (31, 78, 67),
                                    [(r.centerx, r.y + 3), (r.x + 4, r.bottom - 5), (r.right - 4, r.bottom - 5)])
        for potion in self.potions:
            if not potion["taken"]:
                r = self._world_rect(potion["rect"])
                if r.right > 0 and r.left < VIEW_W:
                    pygame.draw.rect(self.frame, (74, 151, 91), r)
                    pygame.draw.rect(self.frame, (185, 226, 155), (r.x + 3, r.y + 3, 6, 4))
                    pygame.draw.rect(self.frame, (206, 220, 164), (r.x + 4, r.y - 3, 4, 3))

    def _draw_platforms(self):
        for obj in self.moving:
            r = _rect(obj["x"] - self.camera_x, obj["y"] - self.camera_y, obj["w"], obj["h"])
            pygame.draw.rect(self.frame, (48, 47, 63), r)
            pygame.draw.rect(self.frame, (167, 148, 116), (r.x, r.y, r.w, 2))
        for hazard in self.swinging_spikes:
            angle = math.sin(self.elapsed * hazard["speed"] + hazard["phase"]) * hazard["range"]
            hx = hazard["ax"] + math.sin(angle) * hazard["length"]
            hy = hazard["ay"] + math.cos(angle) * hazard["length"]
            sx, sy = int(hx - self.camera_x), int(hy - self.camera_y)
            ax, ay = int(hazard["ax"] - self.camera_x), int(hazard["ay"] - self.camera_y)
            pygame.draw.line(self.frame, (125, 105, 94), (ax, ay), (sx, sy), 2)
            pygame.draw.circle(self.frame, (102, 94, 96), (sx, sy), 9)
            for angle_deg in range(0, 360, 90):
                ex = sx + int(math.cos(math.radians(angle_deg)) * 14)
                ey = sy + int(math.sin(math.radians(angle_deg)) * 14)
                pygame.draw.line(self.frame, (193, 189, 182), (sx, sy), (ex, ey), 3)
        for obj in self.swinging:
            sx = int(obj["x"] - self.camera_x)
            sy = int(obj["y"] - self.camera_y)
            ax = int(obj["ax"] - self.camera_x)
            ay = int(obj["ay"] - self.camera_y)
            pygame.draw.line(self.frame, (123, 104, 100), (ax, ay), (sx + obj["w"] // 2, sy), 2)
            pygame.draw.rect(self.frame, (53, 47, 60), (sx, sy, obj["w"], obj["h"]))
            pygame.draw.rect(self.frame, (177, 158, 122), (sx, sy, obj["w"], 2))
        for hazard in self.falling_spikes:
            if hazard["state"] != "fall":
                continue
            sx = int(hazard["x"] - self.camera_x)
            sy = int(hazard["y"] - self.camera_y)
            pygame.draw.circle(self.frame, (105, 94, 97), (sx, sy), 7)
            for angle in range(0, 360, 60):
                ex = sx + int(math.cos(math.radians(angle)) * 12)
                ey = sy + int(math.sin(math.radians(angle)) * 12)
                pygame.draw.line(self.frame, (190, 185, 179), (sx, sy), (ex, ey), 3)
        for saw in self.saws:
            sx = int(saw["x"] + math.sin(saw["phase"]) * 32 - self.camera_x)
            sy = int(saw["cy"] + math.cos(saw["phase"] * 1.15) * 18 - self.camera_y)
            pygame.draw.circle(self.frame, (66, 61, 70), (sx, sy), 12)
            for angle in range(0, 360, 45):
                ex = sx + int(math.cos(math.radians(angle)) * 16)
                ey = sy + int(math.sin(math.radians(angle)) * 16)
                pygame.draw.line(self.frame, (190, 193, 188), (sx, sy), (ex, ey), 3)
            pygame.draw.circle(self.frame, (92, 80, 91), (sx, sy), 4)

    def _draw_enemies(self):
        for enemy in self.enemies:
            if not enemy["alive"]:
                continue
            sx = int(enemy["x"] - self.camera_x)
            sy = int(enemy["y"] - self.camera_y)
            if sx < -25 or sx > VIEW_W + 25:
                continue
            col = {
                "green": (105, 166, 104), "orange": (208, 127, 72),
                "blue": (83, 147, 204), "slug": (91, 180, 103),
                "runner": (188, 79, 71),
            }[enemy["kind"]]
            r = self._enemy_rect(enemy)
            r.x -= int(self.camera_x)
            r.y -= int(self.camera_y)
            pygame.draw.ellipse(self.frame, (30, 27, 42), (r.x - 1, r.y + r.h - 3, r.w + 2, 5))
            pygame.draw.rect(self.frame, col, r)
            pygame.draw.rect(self.frame, (31, 34, 45), (r.x + 3, r.y + 5, r.w - 6, 4))
            pygame.draw.rect(self.frame, (245, 220, 162), (r.x + 4, r.y + 6, 2, 2))
            pygame.draw.rect(self.frame, (245, 220, 162), (r.x + r.w - 6, r.y + 6, 2, 2))
            if enemy["kind"] in ("orange", "blue"):
                pygame.draw.rect(self.frame, (230, 193, 112), (r.x + 4, r.y - 3, r.w - 8, 3))

    def _draw_player(self):
        p = self.player
        sx = int(p["x"] - self.camera_x)
        sy = int(p["y"] - self.camera_y)
        if p["invuln"] > 0 and int(self.elapsed * 18) % 2:
            return
        if sx < -25 or sx > VIEW_W + 25:
            return
        # Original, simple ninja silhouette; deliberately not a ripped sprite.
        pygame.draw.ellipse(self.frame, (20, 19, 31), (sx + 1, sy + 18, 14, 5))
        body = (46, 81, 119)
        pygame.draw.rect(self.frame, body, (sx + 3, sy + 7, 9, 10))
        pygame.draw.rect(self.frame, (29, 48, 76), (sx + 2, sy + 16, 5, 6))
        pygame.draw.rect(self.frame, (29, 48, 76), (sx + 8, sy + 16, 5, 6))
        pygame.draw.rect(self.frame, (42, 54, 77), (sx + 2, sy + 1, 11, 8))
        pygame.draw.rect(self.frame, (217, 213, 193), (sx + 3, sy + 4, 9, 3))
        pygame.draw.rect(self.frame, (188, 64, 67), (sx - 3 if p["facing"] < 0 else sx + 9, sy + 9, 7, 3))
        pygame.draw.rect(self.frame, (225, 207, 160), (sx + (11 if p["facing"] > 0 else 0), sy + 10, 3, 2))
        if p["attack"] > 0:
            sword_x = sx + 15 if p["facing"] > 0 else sx - 11
            pygame.draw.rect(self.frame, (226, 225, 214), (sword_x, sy + 7, 10, 2))

    def _draw_birds(self):
        for bird in self.birds:
            if not bird["alive"]:
                continue
            sx = int(bird["x"] - self.camera_x)
            sy = int(bird["y"] + math.sin(bird["phase"]) * 3 - self.camera_y)
            if sx < -20 or sx > VIEW_W + 20:
                continue
            wing = 1 if int(bird["phase"] * 4) % 2 else -1
            pygame.draw.rect(self.frame, (83, 172, 210), (sx - 3, sy - 2, 7, 5))
            pygame.draw.line(self.frame, (152, 220, 229), (sx - 1, sy), (sx - 7, sy + wing * 4), 2)
            pygame.draw.line(self.frame, (152, 220, 229), (sx + 2, sy), (sx + 8, sy + wing * 4), 2)
            pygame.draw.rect(self.frame, WHITE, (sx + 2, sy - 1, 1, 1))

    def _draw_projectiles(self):
        for shot in self.projectiles:
            sx, sy = int(shot["x"] - self.camera_x), int(shot["y"] - self.camera_y)
            if -10 <= sx <= VIEW_W + 10:
                col = (232, 157, 85) if not shot["friendly"] else (132, 225, 243)
                pygame.draw.rect(self.frame, col, (sx - 3, sy - 2, 7, 4))
                pygame.draw.rect(self.frame, WHITE, (sx - 1, sy - 1, 3, 2))
        for shot in self.boss_shots:
            sx, sy = int(shot["x"] - self.camera_x), int(shot["y"] - self.camera_y)
            if -12 <= sx <= VIEW_W + 12:
                pygame.draw.polygon(self.frame, (189, 81, 91),
                                    [(sx - 6, sy), (sx, sy - 4), (sx + 7, sy), (sx, sy + 5)])

    def _draw_checkpoints_and_shops(self):
        for cp in self.checkpoints:
            sx, sy = int(cp["x"] - self.camera_x), int(cp["y"] - self.camera_y)
            if -15 <= sx <= VIEW_W + 15:
                pygame.draw.rect(self.frame, (76, 63, 67), (sx - 2, sy - 31, 4, 31))
                pygame.draw.polygon(self.frame, GOLD if cp["active"] else (121, 96, 86),
                                    [(sx, sy - 32), (sx + 9, sy - 27), (sx, sy - 22), (sx - 7, sy - 27)])
                if cp["active"]:
                    pygame.draw.rect(self.frame, (244, 199, 116), (sx - 1, sy - 29, 2, 4))
        for shop in self.shops:
            sx, sy = int(shop["x"] - self.camera_x), int(shop["y"] - self.camera_y)
            if -22 <= sx <= VIEW_W + 22:
                pulse = 1 if int(self.elapsed * 4) % 2 else 0
                pygame.draw.ellipse(self.frame, (43, 39, 67), (sx - 13, sy - 18, 26, 32), 2)
                pygame.draw.ellipse(self.frame, (91, 70, 131), (sx - 9, sy - 14, 18, 24), 2)
                pygame.draw.rect(self.frame, (190, 170, 218), (sx - 2, sy - 5, 4, 9))
                if pulse:
                    pygame.draw.circle(self.frame, (161, 135, 204), (sx, sy - 14), 2)

    def _draw_boss(self):
        b = self.boss
        if not b["active"] and self.player["x"] < 10420:
            return
        sx = int(b["x"] - self.camera_x)
        sy = int(b["y"] - self.camera_y)
        if sx < -50 or sx > VIEW_W + 50:
            return
        leaf = (198, 92, 75) if b["flash"] <= 0 else (255, 227, 180)
        pygame.draw.ellipse(self.frame, (54, 38, 52), (sx - 28, sy + 20, 57, 9))
        pygame.draw.ellipse(self.frame, leaf, (sx - 24, sy - 20, 48, 48))
        for i in range(7):
            a = i * math.tau / 7 + b["phase"] * 0.25
            lx = sx + int(math.cos(a) * 25)
            ly = sy + int(math.sin(a) * 22)
            pygame.draw.ellipse(self.frame, (133, 62, 76), (lx - 8, ly - 4, 15, 8))
        pygame.draw.rect(self.frame, (42, 42, 48), (sx - 10, sy - 2, 20, 5))
        pygame.draw.rect(self.frame, (244, 222, 176), (sx - 7, sy - 1, 4, 2))
        pygame.draw.rect(self.frame, (244, 222, 176), (sx + 3, sy - 1, 4, 2))
        if b["active"] and not b["defeated"]:
            pygame.draw.rect(self.frame, (53, 33, 47), (VIEW_W // 2 - 92, 25, 184, 7))
            pygame.draw.rect(self.frame, (191, 77, 87),
                             (VIEW_W // 2 - 90, 27, int(180 * b["hp"] / b["max_hp"]), 3))

    def _draw_hud(self):
        pygame.draw.rect(self.frame, (17, 16, 32), (0, 0, VIEW_W, 28))
        pygame.draw.line(self.frame, (103, 83, 108), (0, 28), (VIEW_W, 28))
        self._text("NINJA", (10, 5), WHITE, self.font)
        for i in range(self.player["max_hp"]):
            x = 44 + i * 9
            col = (109, 206, 122) if i < self.player["hp"] else (56, 67, 69)
            pygame.draw.rect(self.frame, col, (x, 7, 6, 8))
            pygame.draw.rect(self.frame, (185, 233, 158) if i < self.player["hp"] else (83, 87, 87),
                             (x, 7, 6, 2))
        # Shard count and Power Seal indicator occupy the same visual lane as
        # the original HUD without using any OXYGEN coin/power terminology.
        pygame.draw.polygon(self.frame, SHARD, [(169, 7), (174, 12), (169, 17), (164, 12)])
        self._text(f"{self.shards_count:03d}", (179, 7), (178, 223, 224), self.font_small)
        self._text(f"SEALS {self.power_seals}/1", (225, 7), (165, 210, 157), self.font_small)
        self._text("M  MAP", (VIEW_W - 60, 7), (187, 174, 206), self.font_small)

    def _draw_quarble(self):
        if self.quarble_timer <= 0:
            return
        sx = int(self.quarble_x - self.camera_x)
        sy = int(self.quarble_y - self.camera_y)
        if -20 <= sx <= VIEW_W + 20:
            pygame.draw.circle(self.frame, (109, 65, 118), (sx, sy), 8)
            pygame.draw.circle(self.frame, (205, 123, 164), (sx - 3, sy - 2), 2)
            pygame.draw.circle(self.frame, (205, 123, 164), (sx + 3, sy - 2), 2)

    def _draw_map(self):
        veil = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        veil.fill((9, 9, 25, 232))
        self.frame.blit(veil, (0, 0))
        self._text("AUTUMN HILLS // FIELD MAP", (VIEW_W // 2, 25), WHITE, self.font_big, center=True)
        self._text("M / ESC TO CLOSE", (VIEW_W // 2, 44), (158, 148, 181), self.font_small, center=True)
        left, top, width = 34, 94, VIEW_W - 68
        pygame.draw.line(self.frame, (95, 79, 108), (left, top + 35), (left + width, top + 35), 3)
        for i, (x0, x1, name) in enumerate(self.rooms):
            cx = left + int((x0 / WORLD_W) * width)
            w = max(8, int(((x1 - x0) / WORLD_W) * width))
            col = (130, 79, 92) if i in self.discovered else (52, 48, 70)
            pygame.draw.rect(self.frame, col, (cx, top + 26, w, 18))
            if i in self.discovered:
                pygame.draw.rect(self.frame, (203, 140, 117), (cx, top + 26, w, 3))
            if i in self.discovered or i % 2 == 0:
                label = name[:10]
                self._text(label, (cx + 1, top + (0 if i % 2 == 0 else 52)),
                           (208, 191, 190) if i in self.discovered else (91, 86, 111), self.font_tiny)
        px = left + int((self.player["x"] / WORLD_W) * width)
        pygame.draw.polygon(self.frame, GOLD, [(px, top + 14), (px - 5, top + 5), (px + 5, top + 5)])
        cp_x = left + int((self.checkpoints[self.checkpoint_index]["x"] / WORLD_W) * width)
        pygame.draw.circle(self.frame, (134, 216, 153), (cp_x, top + 35), 4)
        self._text("YOU", (px, top - 1), GOLD, self.font_tiny, center=True)

        # Compact legend and actual inventory.
        self._text("LEGEND", (42, 177), (164, 155, 181), self.font_small)
        pygame.draw.circle(self.frame, (134, 216, 153), (49, 197), 3)
        self._text("CHECKPOINT", (60, 194), WHITE, self.font_small)
        pygame.draw.ellipse(self.frame, (129, 103, 177), (43, 210, 12, 10), 1)
        self._text("SHOP PORTAL", (60, 211), WHITE, self.font_small)
        pygame.draw.polygon(self.frame, SHARD, [(49, 229), (53, 233), (49, 237), (45, 233)])
        self._text("TIME SHARDS", (60, 229), WHITE, self.font_small)
        pygame.draw.circle(self.frame, (128, 205, 148), (49, 250), 5, 1)
        self._text("POWER SEAL // 1 AVAILABLE NOW", (60, 247), WHITE, self.font_small)
        self._text(f"SHARDS {self.shards_count:03d}     SEALS {self.power_seals}/1",
                   (VIEW_W // 2, 285), GOLD, self.font, center=True)

    def _draw_shop(self):
        veil = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        veil.fill((10, 8, 24, 218))
        self.frame.blit(veil, (0, 0))
        panel = _rect(75, 40, 400, 231)
        pygame.draw.rect(self.frame, (45, 35, 64), panel)
        pygame.draw.rect(self.frame, (158, 125, 178), panel, 2)
        self._text("THE SHOP", (VIEW_W // 2, 55), GOLD, self.font_big, center=True)
        # A small hooded shopkeeper silhouette anchors the portal room.
        pygame.draw.ellipse(self.frame, (27, 25, 42), (VIEW_W // 2 - 9, 72, 18, 28))
        pygame.draw.rect(self.frame, (109, 87, 121), (VIEW_W // 2 - 8, 79, 16, 17))
        pygame.draw.rect(self.frame, (214, 198, 178), (VIEW_W // 2 - 5, 75, 10, 7))
        self._text("TIME SHARDS", (94, 78), (169, 202, 211), self.font_small)
        self._text(f"{self.shards_count:03d}", (VIEW_W - 99, 77), SHARD, self.font)
        for i, (title, cost, desc, item) in enumerate(self._shop_items()):
            y = 103 + i * 29
            selected = i == self.shop_cursor
            color = GOLD if selected else WHITE
            if selected:
                pygame.draw.rect(self.frame, (79, 59, 91), (89, y - 2, 372, 26))
                pygame.draw.rect(self.frame, (182, 143, 183), (89, y - 2, 372, 26), 1)
            owned = ((item == "claws" and self.climbing_claws)
                     or (item == "strike" and self.strike_upgrade)
                     or (item == "shuriken" and self.energy_shuriken)
                     or (item == "karuta" and self.karuta_plates))
            status = "OWNED" if owned else ("FREE" if cost == 0 else f"{cost}")
            self._text(title, (99, y + 2), color, self.font_small)
            self._text(status, (VIEW_W - 100, y + 2), (143, 217, 157) if owned else GOLD, self.font_small)
        self._text("UP/DOWN SELECT   ENTER BUY   ESC LEAVE", (VIEW_W // 2, 258),
                   (174, 164, 194), self.font_tiny, center=True)
        if self.dialog_timer > 0:
            self._text(self.dialog_text, (VIEW_W // 2, 288), GOLD, self.font_small, center=True)

    def _draw_overlay(self):
        if self.banner_timer > 0 and not self.shop_open:
            alpha = min(1.0, self.banner_timer / 0.35)
            bg = pygame.Surface((VIEW_W, 34), pygame.SRCALPHA)
            bg.fill((13, 12, 30, int(185 * alpha)))
            self.frame.blit(bg, (0, 36))
            self._text(self.banner_name, (VIEW_W // 2, 42), WHITE, self.font, center=True)
            self._text(getattr(self, "banner_subtitle", ""), (VIEW_W // 2, 55),
                       (181, 170, 195), self.font_tiny, center=True)
        if self.paused:
            veil = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
            veil.fill((5, 5, 18, 212))
            self.frame.blit(veil, (0, 0))
            self._text("PAUSED", (VIEW_W // 2, 92), WHITE, self.font_big, center=True)
            for i, label in enumerate(("RESUME", "RETURN TO OXYGEN MENU")):
                color = GOLD if i == self.pause_selection else (179, 171, 194)
                self._text(("> " if i == self.pause_selection else "  ") + label,
                           (VIEW_W // 2, 143 + i * 25), color, self.font, center=True)
            self._text("ESC RESUME   ENTER SELECT", (VIEW_W // 2, 249),
                       (156, 147, 174), self.font_small, center=True)
        if self.game_over or self.victory:
            veil = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
            veil.fill((8, 7, 23, 232))
            self.frame.blit(veil, (0, 0))
            title = "AUTUMN HILLS CLEARED" if self.victory else "THE PATH ENDS HERE"
            self._text(title, (VIEW_W // 2, 104), GOLD if self.victory else (206, 132, 137),
                       self.font_big, center=True)
            self._text("LEAF MONSTER DEFEATED" if self.victory else "CHECKPOINTS RESTORED",
                       (VIEW_W // 2, 135), WHITE, self.font, center=True)
            self._text("ENTER / ESC TO RETURN", (VIEW_W // 2, 196),
                       (173, 161, 190), self.font, center=True)
        if self.shop_open:
            self._draw_shop()
        if self.map_open:
            self._draw_map()

    def draw(self, target):
        self._draw_background()
        self._draw_terrain()
        self._draw_platforms()
        self._draw_lanterns()
        self._draw_collectibles()
        self._draw_checkpoints_and_shops()
        self._draw_birds()
        self._draw_enemies()
        self._draw_projectiles()
        self._draw_boss()
        self._draw_quarble()
        self._draw_player()
        self._draw_hud()
        self._draw_overlay()
        scaled = pygame.transform.scale(self.frame, self.output_size)
        target.blit(scaled, (0, 0))
