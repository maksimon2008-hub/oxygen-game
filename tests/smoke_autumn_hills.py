"""Headless launch, input, physics and render smoke tests for Autumn Hills."""
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
    # Import autumn_hills.py from the same build directory as the corresponding
    # main.py so the desktop and browser copies are exercised independently.
    build_dir = str(path.parent)
    sys.path.insert(0, build_dir)
    sys.modules.pop("autumn_hills", None)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load OXYGEN module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def key(module, game, code):
    event = module.pygame.event.Event(module.pygame.KEYDOWN, key=code, mod=0, unicode="")
    game.handle_event(event)


def smoke_build(relative_path: str, module_name: str) -> None:
    module = load_module(ROOT / relative_path, module_name)
    game = None
    try:
        game = module.Game()
        assert game.mode == "menu"
        game.open_menu_item(7)
        assert game.mode == "autumn_hills"
        scene = game.autumn_hills_scene
        assert scene is not None
        assert len(scene.rooms) == 15
        assert len(scene.shards) >= 60
        assert len(scene.lanterns) >= 20
        assert len(scene.enemies) >= 20
        assert len(scene.moving) >= 3 and len(scene.swinging) >= 3
        assert len(scene.shops) == 3
        assert scene.boss["max_hp"] == 20

        # A few normal physics frames and a full render at the opening screen.
        for _ in range(5):
            game.update(1 / 60)
        game.draw()

        # The map is a real modal overlay and can be opened/closed independently.
        key(module, game, module.pygame.K_m)
        assert scene.map_open
        game.draw()
        key(module, game, module.pygame.K_m)
        assert not scene.map_open

        # Hitting a lantern produces Time Shards.
        scene.player["x"] = 110.0
        scene.player["y"] = 200.0
        scene.player["ground"] = False
        scene.player["vy"] = 0.0
        before = scene.shards_count
        scene._attack()
        assert not scene.lanterns[0]["lit"]
        assert scene.shards_count == before
        assert scene.player["cloudstep"], "Airborne lantern strike must grant Cloudstep"
        assert scene.banner_name == "CLOUDSTEP READY"

        # The acquired Cloudstep charge must launch a second jump on the next
        # jump press, consuming the charge and restoring upward velocity.
        key(module, scene, module.pygame.K_SPACE)
        scene.update(1 / 60)
        assert not scene.player["cloudstep"], "Cloudstep charge must be consumed by the extra jump"
        assert scene.player["vy"] < -200, "Cloudstep must produce a strong upward impulse"

        # Fonts are larger and use antialiasing so labels remain legible after
        # the scene is enlarged into the host's 1100x620 frame.
        assert scene.font_small.get_height() >= 10
        assert scene.font.get_height() > scene.font_small.get_height()

        # Shop portal grants the first Climbing Claws and becomes a checkpoint.
        scene.player["x"] = 2105.0
        scene.player["y"] = 333.0
        scene.player["vx"] = scene.player["vy"] = 0.0
        scene._interact()
        assert scene.shop_open and scene.climbing_claws
        assert scene.checkpoint_index == 1
        scene.draw(game.screen)
        key(module, game, module.pygame.K_ESCAPE)
        assert not scene.shop_open

        # Pause menu can return to OXYGEN without mixing either game's state.
        key(module, game, module.pygame.K_ESCAPE)
        assert scene.paused
        key(module, game, module.pygame.K_DOWN)
        key(module, game, module.pygame.K_RETURN)
        assert game.mode == "menu"
        assert game.autumn_hills_scene is None
        game.draw()
    finally:
        if game is not None:
            try:
                game.save_progress()
            except Exception:
                pass
        module.pygame.quit()


if __name__ == "__main__":
    smoke_build("neon_ruins_platformer/main.py", "oxygen_desktop_autumn_smoke")
    smoke_build("oxygen_web/main.py", "oxygen_web_autumn_smoke")
    print("OXYGEN Autumn Hills headless smoke test: OK")
