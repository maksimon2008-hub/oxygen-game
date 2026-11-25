"""Headless runtime smoke test for the OXYGEN Autumn Hills sector port."""
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
    game.player.x, game.player.y = x, y
    game.player.vx = game.player.vy = 0.0
    game.player.on_ground = True
    game.camera_x, game.camera_y = camera_x, camera_y
    game.draw_world()
    game.draw_hud()


def smoke_build(relative_path: str, module_name: str) -> None:
    module = load_module(ROOT / relative_path, module_name)
    game = None
    try:
        game = module.Game()
        game.load_level(0)
        game.mode = "playing"
        draw_at(game, 1500.0, 432.0, 900.0, 0.0)
        draw_at(game, 5100.0, 262.0, 4500.0, 0.0)
        draw_at(game, 10000.0, 497.0, 9400.0, 0.0)
        for _ in range(4):
            game.update(1 / 60)
        assert game.camera_y > 10.0, (
            f"{relative_path}: vertical camera did not follow the lower passage")
        draw_at(game, 17600.0, 649.0, 17000.0, 100.0)
        draw_at(game, 21400.0, 432.0, 20800.0, 0.0)
        game.map_open = True
        game.draw_sector_map()
        game.map_open = False
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
    print("OXYGEN Autumn Hills headless runtime smoke test: OK")
