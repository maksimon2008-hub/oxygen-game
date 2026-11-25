"""Headless runtime smoke test for sector 01 in both Pygame builds."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load OXYGEN module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def smoke_build(relative_path: str, module_name: str) -> None:
    module = load_module(ROOT / relative_path, module_name)
    game = None
    try:
        game = module.Game()
        game.load_level(0)
        game.mode = "playing"

        # First tall shaft: execute physics and verify the camera tracks upward.
        game.player.x = 1030.0
        game.player.y = -403.0  # standing on the authored ledge at y=-360
        game.player.vx = 0.0
        game.player.vy = 0.0
        game.player.on_ground = True
        game.camera_y = 0.0
        for _ in range(4):
            game.update(1 / 60)
        assert game.camera_y < -10.0, (
            f"{relative_path}: vertical camera did not follow the upper shaft"
        )
        game.draw_world()
        game.draw_hud()

        # Lower drainage route: verify the camera can scroll down as well.
        game.player.x = 2030.0
        game.player.y = 667.0  # standing on the lower tunnel deck at y=710
        game.player.vx = 0.0
        game.player.vy = 0.0
        game.player.on_ground = True
        game.camera_y = 0.0
        for _ in range(4):
            game.update(1 / 60)
        assert game.camera_y > 10.0, (
            f"{relative_path}: vertical camera did not follow the lower tunnel"
        )
        game.draw_world()
        game.draw_hud()

        # Render the highest bridge and its surrounding room at real world coordinates.
        game.player.x = 4300.0
        game.player.y = -1543.0
        game.camera_x = 3850.0
        game.camera_y = -1743.0
        game.draw_world()
        game.draw_hud()

        # Exercise a few ordinary frames after returning to the start.
        game.load_level(0)
        for _ in range(8):
            game.update(1 / 60)
            game.draw_world()
            game.draw_hud()
    finally:
        if game is not None:
            try:
                game.save_progress()
            except Exception:
                pass
        module.pygame.quit()


if __name__ == "__main__":
    smoke_build("neon_ruins_platformer/main.py", "oxygen_desktop_smoke")
    smoke_build("oxygen_web/main.py", "oxygen_web_smoke")
    print("OXYGEN sector 01 headless runtime smoke test: OK")
