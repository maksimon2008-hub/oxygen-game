"""Headless runtime smoke test for both OXYGEN builds and Sector 01 routes."""
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
    # main.py imports build-local modules; make the matching build folder
    # importable and clear the previous build's same-named scene module.
    sys.path.insert(0, str(path.parent))
    sys.modules.pop("autumn_hills", None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load OXYGEN module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def draw_at(game, x: float, y: float, camera_x: float, camera_y: float) -> None:
    game.player.x = x
    game.player.y = y
    game.player.vx = 0.0
    game.player.vy = 0.0
    game.player.on_ground = True
    game.camera_x = camera_x
    game.camera_y = camera_y
    game.draw_world()
    game.draw_hud()


def smoke_build(relative_path: str, module_name: str) -> None:
    module = load_module(ROOT / relative_path, module_name)
    game = None
    try:
        game = module.Game()
        game.load_level(0)
        game.mode = "playing"

        # Pump Atrium's upper landing: real physics frames must move the camera up.
        draw_at(game, 2500.0, 92.0, 1900.0, 0.0)
        for _ in range(4):
            game.update(1 / 60)
        assert game.camera_y < -10.0, (
            f"{relative_path}: vertical camera did not follow the Pump stair"
        )
        game.draw_world()
        game.draw_hud()

        # Drainage floor: the camera must also follow the lower service route.
        draw_at(game, 1320.0, 647.0, 900.0, 0.0)
        for _ in range(4):
            game.update(1 / 60)
        assert game.camera_y > 10.0, (
            f"{relative_path}: vertical camera did not follow the lower underpass"
        )
        game.draw_world()
        game.draw_hud()

        # Render both sides of the upper loop and the final beacon mast.
        draw_at(game, 810.0, 372.0, 0.0, -55.0)       # west return ramp
        draw_at(game, 3100.0, 92.0, 2500.0, -75.0)    # Signal Bridge
        draw_at(game, 4580.0, 57.0, 3750.0, -145.0)  # beacon vault

        # Exercise the full-screen TAB map renderer in headless mode.
        game.map_open = True
        game.draw_sector_map()
        game.map_open = False

        # Start again and render a few ordinary gameplay frames.
        game.load_level(0)
        game.mode = "playing"
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
