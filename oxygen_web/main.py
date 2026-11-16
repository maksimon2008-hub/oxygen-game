"""OXYGEN — a neon platformer made with Pygame.

Controls:
    A / D or Left / Right : move
    Space / W / Up        : jump (hold for a higher jump)
    Left Shift / X        : air dash (VANTA)
    Space in air           : second jump (ECHO)
    J / C / left mouse     : pulse shot (CIPHER)
    Escape                : pause menu / return to main menu
    R                     : restart current level
    Enter                 : start / continue
"""

from __future__ import annotations

import asyncio
import json
import math
from array import array
import random
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
WIDTH, HEIGHT = 1100, 620
TARGET_FPS = 60 if sys.platform == "emscripten" else 180  # browser-friendly cap
TITLE = "OXYGEN"

CURRENT_LANGUAGE = "en"
_LOCALIZATION_CACHE: dict[str, str] = {}

def set_language(language: str) -> None:
    """Load the selected UI language. English remains the source/fallback language."""
    global CURRENT_LANGUAGE, _LOCALIZATION_CACHE
    CURRENT_LANGUAGE = "ru" if str(language).lower() == "ru" else "en"
    _LOCALIZATION_CACHE = {}
    if CURRENT_LANGUAGE == "ru":
        path = Path(__file__).with_name("locales") / "ru.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                _LOCALIZATION_CACHE = {str(k): str(v) for k, v in loaded.items()}
        except (OSError, json.JSONDecodeError):
            _LOCALIZATION_CACHE = {}

def localize(value: object) -> str:
    text = str(value)
    if CURRENT_LANGUAGE != "ru":
        return text
    direct = _LOCALIZATION_CACHE.get(text)
    if direct is not None:
        return direct
    # Translate common fragments in generated status strings without changing IDs/names.
    replacements = (
        ("NOT ENOUGH COINS", "НЕДОСТАТОЧНО МОНЕТ"),
        ("MAX LEVEL", "МАКС. УРОВЕНЬ"),
        ("AVAILABLE CURRENCY", "ДОСТУПНЫЕ СРЕДСТВА"),
        ("WALLET", "КОШЕЛЁК"), ("COINS", "МОНЕТЫ"),
        ("SECTOR", "СЕКТОР"), ("LEVEL", "УРОВЕНЬ"),
        ("DEATHS", "СМЕРТИ"), ("SECRETS", "СЕКРЕТЫ"),
        ("TIME", "ВРЕМЯ"), ("COST", "ЦЕНА"),
        ("UNLOCKED", "ОТКРЫТО"), ("LOCKED", "ЗАКРЫТО"),
        ("INSTALLED", "УСТАНОВЛЕНО"), ("PAID", "ВЫПЛАЧЕНО"),
        ("CHECKPOINT // SAVED", "ЧЕКПОИНТ // СОХРАНЕНО"),
        ("EXP ARCHIVE", "АРХИВ EXP"),
        ("EXP CASSETTE", "КАССЕТА EXP"),
        ("RECOVERED", "НАЙДЕНА"),
        ("AUDIO NOT INSTALLED", "АУДИО ПОКА НЕ ДОБАВЛЕНО"),
        ("SIGNAL REQUIRED", "НУЖЕН СИГНАЛ"),
        ("AWAKENS", "ПРОБУЖДАЕТСЯ"), ("DESTROYED", "УНИЧТОЖЕН"),
        ("RETURN TO MAIN MENU", "В ГЛАВНОЕ МЕНЮ"),
        ("CURRENT RUNNER:", "ТЕКУЩИЙ БОЕЦ:"),
        ("TALK TO", "ПОГОВОРИТЬ С"), ("ENTER MOD BAY", "ОТКРЫТЬ МОДУЛЬНУЮ СТАНЦИЮ"),
        ("DEPLOY TO NEXT SECTOR", "ПЕРЕЙТИ В СЛЕДУЮЩИЙ СЕКТОР"),
        ("EXIT SEALED", "ВЫХОД ЗАПЕЧАТАН"), ("DEFEAT", "ПОБЕДИ"),
        ("WAVE", "ВОЛНА"), ("SCRAP YARD", "СВАЛКА"),
        ("SIGNAL RESTORED", "СИГНАЛ ВОССТАНОВЛЕН"),
        ("BUFFER READY", "БУФЕР ГОТОВ"),
        ("CHARGE", "ЗАРЯД"),
        ("NEXT RUN", "СЛЕДУЮЩИЙ ВЫХОД"),
        ("ALREADY INSTALLED", "УЖЕ УСТАНОВЛЕНО"),
        ("MODULES", "МОДУЛЕЙ"),
        ("OPERATIVE", "БОЕЦ"),
        ("SERVICE OXYGEN FILTER", "ОБСЛУЖИТЬ КИСЛОРОДНЫЙ ФИЛЬТР"),
        ("OXYGEN FILTER", "КИСЛОРОДНЫЙ ФИЛЬТР"),
        ("CHOOSE RUNNER AND DEPLOY", "ВЫБРАТЬ БОЙЦА И ВЫЙТИ НА ЗАДАНИЕ"),
        ("OPEN ABILITY MODULES", "ОТКРЫТЬ МОДУЛИ СПОСОБНОСТЕЙ"),
        ("DOUBLE COINS FOR 20 SECONDS", "УДВОЕНИЕ МОНЕТ НА 20 СЕКУНД"),
        ("COINS x2", "МОНЕТЫ x2"),
        ("ACHIEVEMENT UNLOCKED", "ДОСТИЖЕНИЕ ОТКРЫТО"),
        ("FILTER SERVICED", "ФИЛЬТР ОБСЛУЖЕН"),
        ("FILTER NEEDS 8 COINS FOR MAINTENANCE", "ДЛЯ ОБСЛУЖИВАНИЯ ФИЛЬТРА НУЖНО 8 МОНЕТ"),
        ("OXYGEN BUFFER READY", "КИСЛОРОДНЫЙ БУФЕР ГОТОВ"),
        ("OXYGEN BUFFER CHARGED", "КИСЛОРОДНЫЙ БУФЕР ЗАРЯЖЕН"),
        ("NEXT DEPLOYMENT", "СЛЕДУЮЩИЙ ВЫХОД"),
        ("COIN CACHE", "МОНЕТНЫЙ ТАЙНИК"),
        ("COST", "ЦЕНА"),
    )
    for source, translated in replacements:
        text = text.replace(source, translated)
    # Long content labels (achievement names, level names, character abilities)
    # also occur inside composed status strings, so translate those fragments too.
    for source, translated in sorted(_LOCALIZATION_CACHE.items(), key=lambda item: len(item[0]), reverse=True):
        if len(source) >= 7 and source in text:
            text = text.replace(source, translated)
    return text

BG_TOP = (7, 10, 25)
BG_BOTTOM = (15, 20, 43)
WHITE = (235, 248, 255)
MUTED = (133, 157, 183)
CYAN = (63, 245, 226)
CYAN_DARK = (20, 130, 135)
PINK = (255, 70, 150)
YELLOW = (255, 218, 104)
RED = (255, 76, 91)


def make_synth_sfx(duration: float, start_freq: float, end_freq: float,
                   volume: float = 0.35, waveform: str = "sine",
                   noise: float = 0.0, seed: int = 167) -> pygame.mixer.Sound:
    """Build a tiny synthesized SFX in memory (no extra asset downloads)."""
    sample_rate = 22050
    count = max(1, int(sample_rate * duration))
    samples = array("h")
    rng = random.Random(seed)
    phase = 0.0
    for i in range(count):
        t = i / max(1, count - 1)
        frequency = start_freq + (end_freq - start_freq) * t
        phase += (2.0 * math.pi * frequency) / sample_rate
        if waveform == "square":
            tone = 1.0 if math.sin(phase) >= 0 else -1.0
        elif waveform == "triangle":
            tone = (2.0 / math.pi) * math.asin(math.sin(phase))
        elif waveform == "saw":
            tone = 2.0 * ((phase / (2.0 * math.pi)) % 1.0) - 1.0
        else:
            tone = math.sin(phase)
        attack = min(1.0, i / max(1.0, sample_rate * 0.008))
        release = min(1.0, (count - i) / max(1.0, sample_rate * 0.035))
        envelope = attack * release
        sample = (tone + rng.uniform(-1.0, 1.0) * noise) * volume * envelope
        samples.append(int(max(-1.0, min(1.0, sample)) * 32767))
    return pygame.mixer.Sound(buffer=samples.tobytes())

THEMES = [
    {"accent": (62, 242, 224), "accent2": (255, 79, 161), "sky": (8, 17, 36)},
    {"accent": (174, 111, 255), "accent2": (63, 222, 255), "sky": (18, 11, 39)},
    {"accent": (255, 185, 76), "accent2": (255, 76, 132), "sky": (30, 13, 28)},
    {"accent": (166, 255, 84), "accent2": (59, 225, 180), "sky": (10, 26, 28)},
    {"accent": (255, 91, 91), "accent2": (255, 194, 79), "sky": (29, 9, 24)},
    {"accent": (68, 190, 255), "accent2": (162, 112, 255), "sky": (5, 19, 39)},
    {"accent": (255, 92, 194), "accent2": (91, 230, 255), "sky": (26, 8, 35)},
    {"accent": (118, 255, 144), "accent2": (255, 196, 88), "sky": (6, 27, 27)},
    {"accent": (255, 129, 74), "accent2": (174, 120, 255), "sky": (31, 13, 20)},
    {"accent": (232, 245, 255), "accent2": (95, 120, 255), "sky": (7, 10, 31)},
]


CHARACTERS = {
    "runner": {
        "name": "VANTA",
        "role": "THE RUNNER",
        "ability": "AIR DASH",
        "description": "Burst through danger. Fast, sharp, unstoppable.",
        "accent": (73, 247, 226),
        "accent2": (255, 76, 153),
        "hint": "SHIFT / X  DASH",
    },
    "jumper": {
        "name": "ECHO",
        "role": "THE PHASER",
        "ability": "DOUBLE JUMP",
        "description": "Jump again in mid-air to reach higher routes.",
        "accent": (177, 118, 255),
        "accent2": (90, 225, 255),
        "hint": "SPACE  DOUBLE JUMP",
    },
    "shooter": {
        "name": "CIPHER",
        "role": "THE GUNNER",
        "ability": "PULSE SHOT",
        "description": "Fire energy bolts to destroy enemies from range.",
        "accent": (255, 191, 82),
        "accent2": (255, 86, 125),
        "hint": "J / C / LMB  SHOOT",
    },
    "flyer": {
        "name": "AERIS",
        "role": "THE ASCENDED",
        "ability": "FLIGHT + BLAST",
        "description": "Take to the air and fire rapid energy bolts.",
        "accent": (112, 190, 255),
        "accent2": (190, 245, 255),
        "hint": "HOLD SPACE  FLY  //  J  SHOOT",
    },
}
CHARACTER_IDS = tuple(CHARACTERS.keys())

ACHIEVEMENTS = [
    ("first_blood", "FIRST CONTACT", "Defeat your first enemy."),
    ("coin_runner", "COIN RUNNER", "Earn 50 coins from all sources."),
    ("hidden_paths", "OFF THE MAP", "Discover a secret room."),
    ("wall_dancer", "WALL DANCER", "Perform 10 wall jumps."),
    ("machine_breaker", "MACHINE BREAKER", "Defeat 25 enemies."),
    ("core_down", "CORE DOWN", "Defeat THE CORE in sector 05."),
    ("signal_complete", "OXYGEN RESTORED", "Complete all ten sectors."),
    ("contract_runner", "GOOD NEIGHBOR", "Complete a safehouse contract."),
    ("arena_survivor", "SCRAP NEVER SLEEPS", "Survive 5 arena waves."),
    ("warden_down", "WARDEN FALLEN", "Defeat the OXYGEN WARDEN in sector 10."),
    ("perfect_signal", "PERFECT FREQUENCY", "Earn an S rank in five sectors."),
]

SKILL_NODES = [
    ("wall_mastery", "WALL MASTERY", 35, "Grip walls longer and leap farther."),
    ("coin_echo", "COIN ECHO", 30, "Attract nearby coins from a short distance."),
    ("signal_shield", "SIGNAL SHIELD", 50, "Increase maximum health from 3 to 4."),
    ("air_overdrive", "AIR OVERDRIVE", 45, "Improve airborne steering and momentum."),
]

QUESTS = [
    {"id": "engineer_hunt", "npc": "ENGINEER RHEA", "role": "FIELD TECHNICIAN",
     "title": "CLEAR THE PERIMETER", "metric": "kills", "target": 20,
     "reward": 70, "brief": "The old sentries are still active. Disable twenty hostile machines."},
    {"id": "archivist_memory", "npc": "QUARTERMASTER NOX", "role": "SUPPLY KEEPER",
     "title": "SALVAGE THE GRID", "metric": "coins_collected", "target": 35,
     "reward": 65, "brief": "Recover thirty-five coin charges from the ruins. We need power for the shelter."},
    {"id": "drifter_secrets", "npc": "THE DRIFTER", "role": "TUNNEL RUNNER",
     "title": "OFF THE MAP", "metric": "secrets", "target": 3,
     "reward": 80, "brief": "Find three hidden rooms. I marked their echoes, not their doors."},
    {"id": "restore_lights", "npc": "MARA", "role": "SHELTER ELECTRICIAN",
     "title": "BRING BACK THE LIGHTS", "metric": "kills", "target": 12,
     "reward": 55, "brief": "The backup grid is almost dead. Clear twelve machines and I can reroute power to the lamps."},
]


ABILITY_MODS = {
    "runner": [
        ("phase_burn", "PHASE BURN", 45, "Dash hits deal extra damage to the Core."),
        ("long_dash", "AFTERIMAGE DRIVE", 55, "Dash lasts longer and recharges faster."),
    ],
    "jumper": [
        ("third_step", "THIRD PULSE", 55, "Unlock one extra mid-air jump."),
        ("shock_stomp", "SHOCK LANDING", 50, "Stomps deal +1 damage to enemies."),
    ],
    "shooter": [
        ("piercing_rounds", "PIERCING ROUNDS", 60, "Shots can pass through one enemy."),
        ("quick_charge", "QUICK CHARGE", 55, "Reduce shot cooldown from 1.3s to 0.95s."),
    ],
    "flyer": [
        ("ion_wings", "ION WINGS", 60, "Increase flight fuel capacity by 35%."),
        ("starfall", "STARFALL CORE", 70, "Energy shots deal extra damage to the Core."),
    ],
}

@dataclass
class Platform:
    x: int
    y: int
    w: int
    h: int

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.w, self.h)


@dataclass
class MovingPlatform:
    x: float
    y: float
    w: int
    h: int
    axis: str
    travel: float
    speed: float
    phase: float = 0.0
    origin_x: float = 0.0
    origin_y: float = 0.0
    delta_x: float = 0.0
    delta_y: float = 0.0

    def __post_init__(self) -> None:
        self.origin_x = float(self.x)
        self.origin_y = float(self.y)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.x), round(self.y), self.w, self.h)

    def update(self, elapsed: float) -> None:
        old_x, old_y = self.x, self.y
        offset = math.sin(elapsed * self.speed + self.phase) * self.travel
        if self.axis == "vertical":
            self.x, self.y = self.origin_x, self.origin_y + offset
        else:
            self.x, self.y = self.origin_x + offset, self.origin_y
        self.delta_x = self.x - old_x
        self.delta_y = self.y - old_y


@dataclass
class Coin:
    x: float
    y: float
    phase: float = 0.0
    collected: bool = False


@dataclass
class Drone:
    x: float
    y: float
    left: float
    right: float
    speed: float = 105.0
    direction: int = 1
    phase: float = 0.0
    alive: bool = True
    hp: int = 3

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 19), int(self.y - 15), 38, 30)

    def update(self, dt: float, solids: list[pygame.Rect] | None = None) -> None:
        if not self.alive:
            return
        self.phase += dt * 5.0
        old_x = self.x
        self.x += self.speed * self.direction * dt
        if self.x < self.left:
            self.x = self.left
            self.direction = 1
        elif self.x > self.right:
            self.x = self.right
            self.direction = -1
        if solids:
            candidate = self.rect
            if any(candidate.colliderect(solid) for solid in solids):
                self.x = old_x
                self.direction *= -1


@dataclass
class Seeker:
    """A roaming hunter orb that homes in on the player at close range."""
    x: float
    y: float
    left: float
    right: float
    speed: float = 112.0
    phase: float = 0.0
    alive: bool = True
    vx: float = 0.0
    vy: float = 0.0
    hp: int = 3

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 16), int(self.y - 16), 32, 32)

    def update(self, dt: float, target_x: float, target_y: float,
               solids: list[pygame.Rect] | None = None) -> None:
        if not self.alive:
            return
        self.phase += dt * 3.2
        dx = target_x - self.x
        dy = (target_y + 20) - self.y
        distance = math.hypot(dx, dy)
        # Hunters only home in when a clear corridor exists. They patrol instead
        # of phasing through walls when the player is on the other side.
        line_blocked = False
        if solids and distance < 390:
            line_blocked = any(solid.clipline((round(self.x), round(self.y)),
                                              (round(target_x), round(target_y + 20)))
                               for solid in solids)

        if distance < 390 and distance > 1 and not line_blocked:
            desired_vx = dx / distance * self.speed
            desired_vy = dy / distance * self.speed * 0.78
            blend = min(1.0, dt * 2.6)
            self.vx += (desired_vx - self.vx) * blend
            self.vy += (desired_vy - self.vy) * blend
        else:
            midpoint = (self.left + self.right) * 0.5
            amplitude = max(12.0, (self.right - self.left) * 0.42)
            desired_x = midpoint + math.sin(self.phase * 0.48) * amplitude
            desired_y = 255.0 + math.sin(self.phase * 1.7) * 34.0
            self.vx += (max(-self.speed * 0.55, min(self.speed * 0.55,
                            (desired_x - self.x) * 1.4)) - self.vx) * min(1.0, dt * 2.0)
            self.vy += ((desired_y - self.y) * 2.0 - self.vy * 1.8) * min(1.0, dt)

        next_x = max(self.left, min(self.right, self.x + self.vx * dt))
        next_y = max(135.0, min(440.0, self.y + self.vy * dt))
        if solids:
            test_x = pygame.Rect(round(next_x - 16), round(self.y - 16), 32, 32)
            if any(test_x.colliderect(solid) for solid in solids):
                self.vx *= -0.35
            else:
                self.x = next_x
            test_y = pygame.Rect(round(self.x - 16), round(next_y - 16), 32, 32)
            if any(test_y.colliderect(solid) for solid in solids):
                self.vy *= -0.35
            else:
                self.y = next_y
        else:
            self.x, self.y = next_x, next_y


@dataclass
class Spider:
    """A vertical wall-crawler that patrols between two heights."""
    x: float
    y: float
    top: float
    bottom: float
    speed: float = 82.0
    phase: float = 0.0
    alive: bool = True
    hp: int = 3

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 16), int(self.y - 13), 32, 26)

    def update(self, dt: float, solids: list[pygame.Rect] | None = None) -> None:
        if not self.alive:
            return
        previous_y = self.y
        self.phase += dt * 2.0
        midpoint = (self.top + self.bottom) * 0.5
        amplitude = max(0.0, (self.bottom - self.top) * 0.5)
        candidate_y = midpoint + math.sin(self.phase) * amplitude
        if solids:
            current_rect = self.rect
            candidate_rect = pygame.Rect(int(self.x - 16), int(candidate_y - 13), 32, 26)
            # A crawler may touch the wall it is attached to, but it cannot
            # enter a *new* solid tile while moving along the surface.
            entered_solid = any(candidate_rect.colliderect(solid)
                                and not current_rect.colliderect(solid)
                                for solid in solids)
            if entered_solid:
                self.phase = math.pi - self.phase
                candidate_y = previous_y
        self.y = candidate_y


@dataclass
class Turret:
    """A stationary sentry that periodically fires an aimed energy bolt."""
    x: float
    y: float
    cooldown: float = 1.1
    alive: bool = True
    hp: int = 3
    phase: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 18), int(self.y - 20), 36, 40)

    def update(self, dt: float, target_x: float, target_y: float,
               solids: list[pygame.Rect] | None = None) -> Projectile | None:
        if not self.alive:
            return None
        self.phase += dt * 2.5
        self.cooldown -= dt
        dx, dy = target_x - self.x, target_y - self.y
        distance = math.hypot(dx, dy)
        line_blocked = bool(solids and any(
            solid.clipline((round(self.x), round(self.y)),
                           (round(target_x), round(target_y))) for solid in solids))
        if self.cooldown <= 0 and 40 < distance < 760 and not line_blocked:
            self.cooldown = 2.0
            speed = 360.0
            return Projectile(self.x, self.y, dx / distance * speed,
                              dy / distance * speed, (255, 105, 125),
                              damage=1, life=2.6, radius=7)
        if self.cooldown <= 0 and line_blocked:
            self.cooldown = 0.25
        return None


@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    color: tuple[int, int, int]
    damage: int = 1
    life: float = 1.65
    alive: bool = True
    radius: int = 6
    pierce: int = 0
    last_hit_target: int = 0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.radius), int(self.y - self.radius),
                           self.radius * 2, self.radius * 2)

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False


class Boss:
    """A configurable multi-phase boss with telegraphed attacks."""
    def __init__(self, variant="core", x=4130.0, base_y=242.0,
                 left=3990.0, right=4250.0, hp=36, name="THE CORE"):
        self.variant = variant
        self.name = name
        self.x = float(x)
        self.base_y = float(base_y)
        self.y = self.base_y
        self.left = float(left)
        self.right = float(right)
        self.hp = int(hp)
        self.max_hp = int(hp)
        self.active = False
        self.defeated = False
        self.phase = 0.0
        self.invuln = 0.0
        self.flash = 0.0
        self.state = "idle"
        self.state_timer = 0.0
        self.attack_timer = 1.5
        self.charge_vx = 0.0
        self.shots: list[Projectile] = []

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 48), int(self.y - 52), 96, 104)

    def take_hit(self, damage: int = 1) -> bool:
        if self.defeated or self.invuln > 0:
            return False
        self.hp = max(0, self.hp - damage)
        self.invuln = 0.16
        self.flash = 0.16
        if self.hp <= 0:
            self.defeated = True
            self.state = "defeated"
            self.shots.clear()
            return True
        return False

    def update(self, dt: float, target_x: float, target_y: float) -> None:
        if not self.active or self.defeated:
            return
        self.phase += dt
        self.invuln = max(0.0, self.invuln - dt)
        self.flash = max(0.0, self.flash - dt)
        self.y = self.base_y + math.sin(self.phase * 2.3) * 8
        phase_two = self.hp <= self.max_hp // 2

        if self.state == "idle":
            self.attack_timer -= dt
            drift = math.sin(self.phase * 0.8) * (42 if not phase_two else 60)
            self.x += drift * dt
            self.x = max(self.left, min(self.right, self.x))
            if self.attack_timer <= 0:
                distance = abs(target_x - self.x)
                self.state = "windup_charge" if distance < 245 else "windup_volley"
                self.state_timer = 0.62 if not phase_two else 0.43
        elif self.state.startswith("windup"):
            self.state_timer -= dt
            if self.state_timer <= 0:
                if self.state == "windup_charge":
                    self.state = "charge"
                    direction = 1 if target_x >= self.x else -1
                    self.charge_vx = direction * (560 if not phase_two else 760)
                    self.state_timer = 0.43 if not phase_two else 0.52
                else:
                    self.fire_volley(target_x, target_y, phase_two)
                    self.state = "recover"
                    self.state_timer = 0.72 if not phase_two else 0.48
        elif self.state == "charge":
            self.x += self.charge_vx * dt
            if self.x < self.left or self.x > self.right:
                self.x = max(self.left, min(self.right, self.x))
                self.charge_vx *= -0.35
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "recover"
                self.state_timer = 0.55
        elif self.state == "recover":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.state = "idle"
                self.attack_timer = 0.95 if not phase_two else 0.48

        for shot in self.shots:
            shot.update(dt)
        self.shots = [shot for shot in self.shots if shot.alive]

    def fire_volley(self, target_x: float, target_y: float, phase_two: bool) -> None:
        dx = target_x - self.x
        dy = target_y - (self.y - 8)
        base_angle = math.atan2(dy, dx)
        speed = 350 if not phase_two else 420
        spread = (-0.22, 0.0, 0.22) if not phase_two else (-0.30, -0.10, 0.10, 0.30)
        for angle_offset in spread:
            angle = base_angle + angle_offset
            shot_color = (255, 75, 116) if self.variant == "core" else (91, 225, 255) if self.variant == "warden" else (255, 205, 91)
            self.shots.append(Projectile(
                self.x, self.y - 8, math.cos(angle) * speed,
                math.sin(angle) * speed, shot_color, damage=1,
                life=2.4, radius=8))


class OxygenWarden(Boss):
    """Final sector boss: a suspended signal guardian with a denser volley."""
    def __init__(self, world_width: int):
        super().__init__(variant="warden", x=world_width - 455, base_y=190,
                         left=world_width - 665, right=world_width - 285,
                         hp=72, name="OXYGEN WARDEN")
        self.attack_timer = 1.25

    def fire_volley(self, target_x: float, target_y: float, phase_two: bool) -> None:
        dx = target_x - self.x
        dy = target_y - (self.y + 4)
        angle = math.atan2(dy, dx)
        speed = 390 if not phase_two else 485
        offsets = (-0.48, -0.24, 0.0, 0.24, 0.48) if not phase_two else (-0.65, -0.43, -0.22, 0.0, 0.22, 0.43, 0.65)
        for offset in offsets:
            a = angle + offset
            self.shots.append(Projectile(
                self.x, self.y + 4, math.cos(a) * speed, math.sin(a) * speed,
                (91, 225, 255), damage=1, life=2.8, radius=8))


@dataclass
class HealingCrystal:
    x: float
    y: float
    phase: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.x - 13), round(self.y - 13), 26, 26)

    def update(self, dt: float) -> None:
        self.phase += dt * 2.2

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        sx = int(self.x - camera_x)
        sy = int(self.y + math.sin(self.phase) * 5)
        if sx < -40 or sx > WIDTH + 40:
            return
        glow = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.circle(glow, (62, 242, 224, 35), (32, 32), 28)
        surface.blit(glow, (sx - 32, sy - 32))
        pygame.draw.polygon(surface, (54, 246, 220),
                            [(sx, sy - 15), (sx + 11, sy), (sx, sy + 15), (sx - 11, sy)])
        pygame.draw.polygon(surface, (205, 255, 250),
                            [(sx, sy - 9), (sx + 5, sy), (sx, sy + 9), (sx - 5, sy)])
        pygame.draw.circle(surface, WHITE, (sx, sy), 3)


@dataclass
class CoinDoubler:
    x: float
    y: float
    phase: float = 0.0
    collected: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.x - 15), round(self.y - 15), 30, 30)

    def update(self, dt: float) -> None:
        self.phase += dt * 3.0

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        sx, sy = int(self.x - camera_x), int(self.y + math.sin(self.phase) * 5)
        if sx < -45 or sx > WIDTH + 45:
            return
        draw_glow(surface, sx, sy, (255, 207, 93), 36)
        pygame.draw.polygon(surface, (255, 192, 70),
                            [(sx, sy - 17), (sx + 15, sy), (sx, sy + 17), (sx - 15, sy)])
        pygame.draw.polygon(surface, (255, 248, 205),
                            [(sx, sy - 9), (sx + 7, sy), (sx, sy + 9), (sx - 7, sy)])
        draw_text(surface, pygame.font.SysFont("consolas", 12, bold=True), "x2",
                  (13, 26, 45), (sx, sy - 7), center=True, shadow=False)


class SafehouseWorld:
    """Small collision map for the refuge, including the elevated filter route."""
    width = WIDTH
    index = 0
    wall_jump_enabled = False

    def __init__(self):
        # Shared player physics checks this collection after hard landings.
        # The refuge has no launch pads, so expose an empty collection here.
        self.launch_pads = []
        self.solids = [
            pygame.Rect(25, 500, 1050, 50),
            pygame.Rect(25, 72, 18, 428),
            pygame.Rect(1057, 72, 18, 428),
            # Compact maintenance lift route stays left of the MOD BAY.
            pygame.Rect(330, 425, 120, 14),
            pygame.Rect(405, 345, 120, 14),
            pygame.Rect(480, 265, 120, 14),
            pygame.Rect(485, 185, 210, 16),
            pygame.Rect(43, 72, 1014, 12),
        ]


@dataclass
class Checkpoint:
    x: int
    y: int
    active: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x - 12, self.y - 58, 24, 58)


class Particle:
    def __init__(self, x: float, y: float, color: tuple[int, int, int],
                 vx: float, vy: float, life: float, size: float = 3.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 260 * dt
        self.vx *= 0.985
        return self.life > 0

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        k = max(0.0, self.life / self.max_life)
        r = max(1, int(self.size * k))
        pygame.draw.circle(surface, self.color,
                           (int(self.x - camera_x), int(self.y)), r)


# -----------------------------------------------------------------------------
# Level data — all geometry is generated from these simple coordinates.
# -----------------------------------------------------------------------------
LEVELS = [
    {
        "name": "THE LAST SIGNAL",
        "subtitle": "THE CITY FORGOT THE SUN",
        "width": 3400,
        "spawn": (80, 410),
        "platforms": [
            (0, 475, 560, 100), (690, 475, 470, 100),
            (1290, 475, 490, 100), (1920, 475, 450, 100),
            (2520, 475, 880, 100),
            (310, 390, 155, 18), (520, 330, 145, 18),
            (800, 390, 155, 18), (1030, 335, 155, 18),
            (1430, 385, 165, 18), (1670, 325, 150, 18),
            (2050, 385, 160, 18), (2290, 325, 155, 18),
            (2660, 385, 160, 18), (2900, 330, 155, 18),
        ],
        "coins": [
            (365, 352), (575, 292), (850, 350), (1085, 297),
            (1480, 345), (1720, 287), (2095, 345), (2345, 287),
            (2705, 345), (2945, 290), (120, 425), (740, 420),
            (1370, 420), (1980, 420), (2570, 420), (3180, 420),
        ],
        "drones": [(900, 355, 820, 930), (1540, 435, 1380, 1760),
                   (2165, 350, 2050, 2220), (2780, 350, 2650, 2820)],
        "spikes": [(780, 452, 72), (1450, 452, 74), (2720, 452, 72)],
        "checkpoints": [(1740, 475), (2640, 475)],
        "exit": (3280, 393),
    },
    {
        "name": "PURPLE STATIC",
        "subtitle": "EVERY MEMORY HAS A PRICE",
        "width": 3900,
        "spawn": (80, 410),
        "platforms": [
            (0, 475, 400, 100), (520, 475, 440, 100),
            (1080, 475, 480, 100), (1700, 475, 420, 100),
            (2250, 475, 470, 100), (2870, 475, 1030, 100),
            (220, 385, 150, 18), (455, 315, 150, 18),
            (745, 370, 155, 18), (1030, 305, 150, 18),
            (1260, 370, 155, 18), (1515, 305, 160, 18),
            (1840, 375, 155, 18), (2070, 310, 155, 18),
            (2390, 370, 155, 18), (2650, 305, 150, 18),
            (2990, 380, 160, 18), (3235, 315, 170, 18),
            (3500, 375, 155, 18),
        ],
        "coins": [
            (255, 347), (490, 277), (785, 332), (1065, 267),
            (1300, 332), (1555, 267), (1880, 337), (2110, 272),
            (2430, 332), (2690, 267), (3030, 342), (3275, 277),
            (3540, 337), (580, 425), (1150, 425), (1770, 425),
            (2300, 425), (2920, 425), (3650, 425),
        ],
        "drones": [(820, 340, 750, 895), (1380, 435, 1120, 1540),
                   (1940, 340, 1830, 2040), (2480, 340, 2380, 2570),
                   (3330, 285, 3250, 3390)],
        "spikes": [(650, 452, 70), (1320, 452, 70), (3020, 452, 72)],
        "checkpoints": [(1600, 475), (2820, 475)],
        "exit": (3770, 393),
    },
    {
        "name": "RED AFTERGLOW",
        "subtitle": "ONE MORE STEP INTO THE UNKNOWN",
        "width": 4350,
        "spawn": (80, 410),
        "platforms": [
            (0, 475, 480, 100), (620, 475, 440, 100),
            (1210, 475, 410, 100), (1760, 475, 470, 100),
            (2390, 475, 390, 100), (2920, 475, 460, 100),
            (3520, 475, 830, 100),
            (280, 390, 160, 18), (545, 315, 155, 18),
            (810, 370, 155, 18), (1080, 300, 155, 18),
            (1350, 365, 160, 18), (1580, 300, 155, 18),
            (1900, 375, 150, 18), (2150, 305, 155, 18),
            (2500, 370, 155, 18), (2740, 300, 155, 18),
            (3040, 375, 160, 18), (3290, 305, 155, 18),
            (3650, 370, 165, 18), (3910, 300, 165, 18),
            (4160, 375, 145, 18),
        ],
        "coins": [
            (315, 352), (580, 277), (845, 332), (1115, 262),
            (1395, 327), (1620, 262), (1940, 337), (2190, 267),
            (2540, 332), (2780, 262), (3080, 337), (3330, 267),
            (3690, 332), (3950, 262), (4200, 337),
            (100, 425), (710, 425), (1300, 425), (1830, 425),
            (2450, 425), (3000, 425), (3590, 425), (4280, 425),
        ],
        "drones": [(900, 340, 820, 955), (1450, 335, 1340, 1550),
                   (2020, 340, 1900, 2110), (2600, 335, 2500, 2700),
                   (3190, 340, 3090, 3290), (3990, 265, 3900, 4060)],
        "spikes": [(700, 452, 70), (1400, 452, 72),
                   (3060, 452, 72), (4050, 452, 70)],
        "checkpoints": [(1680, 475), (2860, 475), (3480, 475)],
        "exit": (4265, 393),
    },
    {
        "name": "THE HOLLOW ENGINE",
        "subtitle": "SOMETHING IS STILL BREATHING",
        "width": 4050,
        "spawn": (80, 410),
        "platforms": [
            (0, 475, 430, 100), (565, 475, 415, 100),
            (1115, 475, 460, 100), (1710, 475, 430, 100),
            (2275, 475, 470, 100), (2890, 475, 390, 100),
            (3415, 475, 635, 100),
            (180, 385, 155, 18), (415, 315, 150, 18),
            (690, 365, 155, 18), (950, 300, 155, 18),
            (1245, 370, 155, 18), (1490, 305, 160, 18),
            (1815, 375, 155, 18), (2070, 305, 155, 18),
            (2395, 365, 155, 18), (2660, 300, 155, 18),
            (3020, 375, 155, 18), (3260, 305, 155, 18),
            (3590, 370, 160, 18), (3840, 305, 155, 18),
        ],
        "coins": [
            (220, 347), (455, 277), (730, 327), (990, 262),
            (1285, 332), (1535, 267), (1855, 337), (2110, 267),
            (2435, 327), (2700, 262), (3060, 337), (3300, 267),
            (3635, 332), (3885, 267), (100, 425), (620, 425),
            (1170, 425), (1760, 425), (2320, 425), (2940, 425),
            (3470, 425), (3980, 425),
        ],
        "drones": [(760, 335, 700, 860), (1330, 435, 1180, 1500),
                   (1985, 340, 1880, 2070), (2500, 335, 2420, 2610),
                   (3150, 340, 3030, 3220), (3750, 275, 3670, 3890)],
        "seekers": [(1040, 220, 940, 1130), (2220, 205, 2110, 2340),
                    (3380, 220, 3290, 3500)],
        "spikes": [(700, 452, 70), (1280, 452, 70), (3020, 452, 70)],
        "checkpoints": [(1660, 475), (2840, 475), (3380, 475)],
        "exit": (3960, 393),
    },
    {
        "name": "BLACK SUN",
        "subtitle": "THE LAST LIGHT FIGHTS BACK",
        "width": 4550,
        "spawn": (80, 410),
        "platforms": [
            (0, 475, 470, 100), (620, 475, 400, 100),
            (1160, 475, 430, 100), (1730, 475, 420, 100),
            (2290, 475, 420, 100), (2860, 475, 410, 100),
            (3410, 475, 410, 100), (3960, 475, 590, 100),
            (250, 385, 155, 18), (500, 310, 155, 18),
            (760, 365, 155, 18), (1010, 295, 155, 18),
            (1290, 360, 155, 18), (1530, 295, 155, 18),
            (1850, 365, 155, 18), (2100, 295, 155, 18),
            (2410, 365, 155, 18), (2660, 295, 155, 18),
            (2980, 365, 155, 18), (3230, 295, 155, 18),
            (3525, 365, 155, 18), (3770, 295, 155, 18),
            (4080, 365, 155, 18), (4320, 300, 155, 18),
        ],
        "coins": [
            (290, 347), (540, 272), (800, 327), (1050, 257),
            (1330, 322), (1570, 257), (1890, 327), (2140, 257),
            (2450, 327), (2700, 257), (3020, 327), (3270, 257),
            (3565, 327), (3810, 257), (4120, 327), (4360, 262),
            (100, 425), (680, 425), (1220, 425), (1790, 425),
            (2350, 425), (2920, 425), (3470, 425), (4020, 425),
            (4470, 425),
        ],
        "drones": [(850, 335, 780, 940), (1410, 335, 1320, 1510),
                   (1960, 335, 1880, 2070), (2520, 335, 2430, 2650),
                   (3090, 335, 3000, 3200), (3650, 335, 3550, 3760),
                   (4210, 270, 4130, 4330)],
        "seekers": [(1080, 190, 970, 1160), (2215, 205, 2110, 2320),
                    (3330, 190, 3230, 3440), (3900, 205, 3800, 4020)],
        "spikes": [(760, 452, 68), (1320, 452, 68),
                   (3010, 452, 70)],
        "checkpoints": [(1670, 475), (2810, 475), (3900, 475)],
        "exit": (4470, 393),
    },
]


# Sectors 06–10: rebuilt around readable jumps, open sight-lines and moving lifts.
# Wall-jump is deliberately disabled here; the vertical slabs from the old layout are gone.
LEVELS.extend([
    {
        "name": "VERTICAL ENTRY", "subtitle": "THE CITY HAS NO FLOOR ANYMORE",
        "width": 3650, "spawn": (80, 410),
        "platforms": [
            (0,475,520,100),(680,475,430,100),(1270,475,480,100),
            (1910,475,430,100),(2510,475,440,100),(3120,475,530,100),
            (260,385,150,18),(535,325,150,18),(835,390,155,18),
            (1120,335,150,18),(1450,385,165,18),(1715,315,155,18),
            (2050,380,155,18),(2320,320,155,18),(2670,375,155,18),
            (2940,315,155,18),(3260,365,160,18),
        ],
        "moving_platforms": [(1000,300,125,16,"vertical",72,0.85,0.4),
                             (1810,260,135,16,"horizontal",105,0.85,1.1),
                             (2860,250,130,16,"vertical",78,0.8,2.0)],
        "launch_pads": [(850,390,72),(2070,380,72)],
        "coins": [(300,345),(575,285),(875,350),(1160,295),(1490,345),(1755,275),
                  (2090,340),(2360,280),(2710,335),(2980,275),(3300,325),
                  (570,425),(1190,425),(1810,425),(2430,425),(3050,425),(3480,425)],
        "drones": [(820,435,740,920),(1510,340,1430,1610),(2110,335,2020,2220),(3300,335,3200,3400)],
        "seekers": [(1110,190,1010,1210),(2730,190,2630,2830)],
        "spiders": [(1740,280,150,390)], "turrets": [(1320,432),(2550,432)],
        "spikes": [(590,452,64),(1190,452,64),(1830,452,64),(2450,452,64)],
        "checkpoints": [(1050,475),(2280,475),(3060,475)],
        "secrets": [(930,170,105,70,"SERVICE SHAFT"),(2780,135,100,70,"ROOFTOP CACHE")],
        "exit": (3560,393)
    },
    {
        "name": "HANGING GARDENS", "subtitle": "ROOTS GROW THROUGH THE SERVERS",
        "width": 3900, "spawn": (80,410),
        "platforms": [
            (0,475,450,100),(610,475,450,100),(1230,475,440,100),
            (1840,475,450,100),(2460,475,450,100),(3090,475,810,100),
            (210,385,155,18),(500,325,155,18),(820,370,155,18),
            (1110,300,155,18),(1400,380,155,18),(1690,315,155,18),
            (2010,370,155,18),(2310,300,155,18),(2630,375,155,18),
            (2920,310,155,18),(3240,370,155,18),(3540,300,160,18),(3730,385,120,18)
        ],
        "moving_platforms": [(930,285,135,16,"horizontal",105,0.85,0.0),
                             (1770,250,135,16,"vertical",82,0.9,1.5),
                             (2820,255,135,16,"horizontal",120,0.8,2.0),
                             (3440,235,135,16,"vertical",75,0.85,0.6)],
        "launch_pads": [(830,370,72),(2635,375,72)],
        "coins": [(250,345),(540,285),(860,330),(1150,260),(1440,340),(1730,275),
                  (2050,330),(2350,260),(2670,335),(2960,270),(3280,330),(3580,260),
                  (500,425),(1120,425),(1740,425),(2360,425),(2980,425),(3600,425)],
        "drones": [(700,435,640,820),(1450,335,1360,1550),(2070,335,1980,2190),(2700,335,2610,2820),(3450,335,3350,3560)],
        "seekers": [(1020,180,930,1120),(2510,180,2410,2610),(3610,170,3510,3710)],
        "spiders": [(1590,275,140,390),(3000,260,130,390)], "turrets": [(1180,432),(2400,432),(3140,432)],
        "spikes": [(530,452,60),(1150,452,60),(1780,452,60),(2400,452,60),(3020,452,60)],
        "checkpoints": [(1100,475),(2380,475),(3000,475)],
        "secrets": [(870,65,105,65,"ROOT SERVER"),(3370,150,105,65,"GARDEN CACHE")],
        "exit": (3820,393)
    },
    {
        "name": "THE GLASS ASCENT", "subtitle": "EVERY REFLECTION IS A DIFFERENT EXIT",
        "width": 4150, "spawn": (80,410),
        "platforms": [
            (0,475,500,100),(680,475,430,100),(1290,475,440,100),
            (1910,475,440,100),(2530,475,440,100),(3150,475,1000,100),
            (200,385,155,18),(500,315,155,18),(800,365,155,18),
            (1090,290,155,18),(1390,365,155,18),(1680,305,155,18),
            (2000,365,155,18),(2300,295,155,18),(2610,365,155,18),
            (2920,300,155,18),(3240,365,155,18),(3550,295,155,18),(3860,350,155,18)
        ],
        "moving_platforms": [(970,255,130,16,"vertical",90,0.95,0.2),
                             (1840,245,130,16,"horizontal",130,0.85,1.0),
                             (2760,250,130,16,"vertical",92,0.9,2.0),
                             (3670,220,135,16,"horizontal",115,0.85,0.3)],
        "launch_pads": [(810,365,72),(2615,365,72)],
        "coins": [(240,345),(540,275),(840,325),(1130,250),(1430,325),(1720,265),
                  (2040,325),(2340,255),(2650,325),(2960,260),(3280,325),(3590,255),(3900,310),
                  (560,425),(1180,425),(1800,425),(2420,425),(3040,425),(3660,425)],
        "drones": [(800,435,730,900),(1450,335,1360,1550),(2070,335,1980,2190),(2690,335,2600,2810),(3520,335,3430,3640)],
        "seekers": [(1040,175,950,1140),(2810,175,2710,2910),(3810,175,3710,3910)],
        "spiders": [(1650,265,130,390),(3000,255,130,390),(3400,255,130,390)],
        "turrets": [(1220,432),(2460,432),(3080,432)],
        "spikes": [(590,452,62),(1210,452,62),(1830,452,62),(2450,452,62),(3070,452,62)],
        "checkpoints": [(1160,475),(2400,475),(3020,475)],
        "secrets": [(900,45,100,65,"MIRROR VAULT"),(3300,145,100,65,"GLASS CACHE")],
        "exit": (4070,393)
    },
    {
        "name": "SIGNAL STORM", "subtitle": "THE SKY HAS LEARNED TO HUNT",
        "width": 4400, "spawn": (80,410),
        "platforms": [
            (0,475,470,100),(650,475,440,100),(1270,475,440,100),
            (1890,475,440,100),(2510,475,440,100),(3130,475,440,100),(3750,475,650,100),
            (190,380,155,18),(480,315,155,18),(790,365,155,18),
            (1080,290,155,18),(1380,365,155,18),(1670,300,155,18),
            (1980,365,155,18),(2280,295,155,18),(2600,365,155,18),
            (2890,300,155,18),(3220,365,155,18),(3510,295,155,18),(3850,350,155,18),(4140,285,155,18)
        ],
        "moving_platforms": [(930,250,135,16,"horizontal",115,0.9,0.0),
                             (1810,240,135,16,"vertical",95,0.9,1.0),
                             (2740,245,135,16,"horizontal",135,0.85,2.0),
                             (3650,225,135,16,"vertical",90,0.9,0.5)],
        "launch_pads": [(800,365,72),(2610,365,72)],
        "coins": [(230,340),(520,275),(830,325),(1120,250),(1420,325),(1710,260),
                  (2020,325),(2320,255),(2640,325),(2930,260),(3260,325),(3540,255),(3880,310),(4170,245),
                  (560,425),(1180,425),(1800,425),(2420,425),(3040,425),(3660,425),(4260,425)],
        "drones": [(750,435,680,850),(1420,335,1330,1520),(2040,335,1950,2140),(2660,335,2570,2760),(3280,335,3190,3380),(3900,335,3810,4020)],
        "seekers": [(1030,175,940,1130),(2600,175,2500,2700),(3650,175,3550,3750),(4200,170,4100,4300)],
        "spiders": [(1610,260,130,390),(2950,260,130,390),(3480,250,130,390)],
        "turrets": [(1200,432),(2440,432),(3060,432),(3680,432)],
        "spikes": [(560,452,60),(1180,452,60),(1800,452,60),(2420,452,60),(3040,452,60),(3660,452,60)],
        "checkpoints": [(1120,475),(2360,475),(3600,475)],
        "secrets": [(900,40,105,65,"STORM RELAY"),(3370,140,110,70,"STATIC CACHE")],
        "exit": (4320,393)
    },
    {
        "name": "THE LAST BREATH", "subtitle": "ONE SIGNAL LEFT",
        "width": 4700, "spawn": (80,410),
        "platforms": [
            (0,475,500,100),(680,475,440,100),(1300,475,440,100),
            (1920,475,440,100),(2540,475,440,100),(3160,475,440,100),(3780,475,920,100),
            (210,380,155,18),(510,310,155,18),(830,365,155,18),
            (1130,285,155,18),(1430,365,155,18),(1730,300,155,18),
            (2050,365,155,18),(2350,290,155,18),(2670,365,155,18),
            (2970,295,155,18),(3290,365,155,18),(3590,290,155,18),(3910,350,155,18),(4240,285,155,18),(4500,355,150,18)
        ],
        "moving_platforms": [(980,245,135,16,"vertical",95,0.9,0.0),
                             (1850,235,135,16,"horizontal",140,0.85,1.0),
                             (2780,240,135,16,"vertical",100,0.9,2.0),
                             (3710,220,140,16,"horizontal",135,0.85,0.5),
                             (4380,230,135,16,"vertical",85,0.85,1.5)],
        "launch_pads": [(840,365,72),(3295,365,72)],
        "coins": [(250,340),(550,270),(870,325),(1170,245),(1470,325),(1770,260),
                  (2090,325),(2390,250),(2710,325),(3010,255),(3330,325),(3630,250),(3950,310),(4280,245),(4540,315),
                  (560,425),(1180,425),(1800,425),(2420,425),(3040,425),(3660,425),(4280,425),(4580,425)],
        "drones": [(800,435,730,900),(1460,335,1370,1550),(2080,335,1990,2170),(2700,335,2610,2790),(3320,335,3230,3410),(3940,335,3850,4030),(4480,335,4390,4580)],
        "seekers": [(1080,170,980,1180),(2750,170,2650,2850),(3900,170,3800,4000),(4500,165,4400,4600)],
        "spiders": [(1660,260,130,390),(3000,255,130,390),(3620,250,130,390),(4180,250,130,390)],
        "turrets": [(1240,432),(2480,432),(3100,432),(3720,432),(4340,432)],
        "spikes": [(590,452,60),(1210,452,60),(1830,452,60),(2450,452,60),(3070,452,60),(3690,452,60)],
        "checkpoints": [(1160,475),(2400,475),(3640,475)],
        "secrets": [(900,40,105,65,"THE FIRST MEMORY"),(3370,55,110,70,"ROOT ACCESS"),(4420,220,100,65,"FINAL CACHE")],
        "exit": (4610,393)
    }
])

class Level:
    def __init__(self, index: int):
        self.load(index)

    def load(self, index: int) -> None:
        self.index = index
        data = LEVELS[index]
        self.name = data["name"]
        self.subtitle = data["subtitle"]
        self.width = data["width"]
        self.spawn = data["spawn"]
        self.moving_platforms = [MovingPlatform(*item) for item in data.get("moving_platforms", [])]
        self.platforms = [Platform(*p) for p in data["platforms"]] + self.moving_platforms
        self.solids = [p.rect for p in self.platforms]
        self.wall_jump_enabled = bool(data.get("wall_jump", False))
        self.launch_pads = [pygame.Rect(x, y - 12, w, 12)
                            for x, y, w in data.get("launch_pads", [])]
        self.coins = [Coin(x, y, random.random() * math.tau) for x, y in data["coins"]]
        self.drones = [Drone(*d, direction=random.choice([-1, 1])) for d in data["drones"]]
        self.seekers = [Seeker(*enemy) for enemy in data.get("seekers", [])]
        self.spiders = [Spider(*item) for item in data.get("spiders", [])]
        self.turrets = [Turret(*item) for item in data.get("turrets", [])]
        if index >= 5:
            for enemy in self.spiders + self.turrets:
                enemy.hp = 6
        # THE CORE guards sector 05; the OXYGEN WARDEN guards sector 10.
        self.boss = Boss() if index == 4 else OxygenWarden(self.width) if index == 9 else None
        self.enemy_shots: list[Projectile] = []
        # Snap spike strips to real floor platforms first. Several authored
        # coordinates were on gaps or floating ledges in the original sectors.
        floor_platforms = [p for p in self.platforms if p.h >= 60 and p.y >= 450]
        normalized_spikes = []
        for raw_x, _raw_y, width in data["spikes"]:
            candidates = []
            for platform in floor_platforms:
                left = int(platform.x) + 8
                right = int(platform.x + platform.w) - int(width) - 8
                if right < left:
                    continue
                candidate_x = max(left, min(right, int(raw_x)))
                distance = abs((candidate_x + width / 2) - (raw_x + width / 2))
                candidates.append((distance, candidate_x, int(platform.y)))
            if candidates:
                _distance, spike_x, floor_y = min(candidates, key=lambda item: item[0])
                normalized_spikes.append(pygame.Rect(spike_x, floor_y - 24, int(width), 24))
        self.spikes = normalized_spikes

        # Place every checkpoint on a floor segment and keep a generous gap
        # from the *final* spike positions, including spikes that had to move.
        normalized_checkpoints = []
        for raw_x, _raw_y in data["checkpoints"]:
            candidates = []
            for platform in floor_platforms:
                left = int(platform.x) + 34
                right = int(platform.x + platform.w) - 34
                if right <= left:
                    continue
                sample_x = max(left, min(right, int(raw_x)))
                samples = set(range(left, right + 1, 24))
                samples.update((left, right, sample_x,
                                max(left, min(right, sample_x - 72)),
                                max(left, min(right, sample_x + 72))))
                safe_samples = [x for x in samples
                                if all(x < spike.left - 48 or x > spike.right + 48
                                       for spike in normalized_spikes)]
                if not safe_samples:
                    continue
                chosen_x = min(safe_samples, key=lambda x: abs(x - raw_x))
                candidates.append((abs(chosen_x - raw_x), chosen_x, int(platform.y)))
            if candidates:
                _distance, cp_x, cp_y = min(candidates, key=lambda item: item[0])
                normalized_checkpoints.append(Checkpoint(int(cp_x), int(cp_y)))
        self.checkpoints = normalized_checkpoints
        self.exit_rect = pygame.Rect(data["exit"][0], data["exit"][1], 54, 82)
        self.secret_rooms = [
            {"rect": pygame.Rect(x, y, w, h), "name": name, "found": False}
            for x, y, w, h, name in data.get("secrets", [])
        ]
        self.cassettes = []
        target_x = int(self.width * (0.27 + 0.045 * index))
        cassette_candidates = []
        for platform in floor_platforms:
            if platform.w < 120:
                continue
            left = int(platform.x) + 30
            right = int(platform.x + platform.w) - 30
            if right < left:
                continue
            cassette_x = max(left, min(right, target_x))
            cassette_y = int(platform.y) - 34
            if any(spike.inflate(76, 24).collidepoint(cassette_x, cassette_y)
                   for spike in self.spikes):
                continue
            if any(abs(cassette_x - checkpoint.x) < 72 for checkpoint in self.checkpoints):
                continue
            cassette_candidates.append((abs(cassette_x - target_x), cassette_x, cassette_y))
        if cassette_candidates:
            _distance, cassette_x, cassette_y = min(cassette_candidates, key=lambda item: item[0])
        elif floor_platforms:
            platform = max(floor_platforms, key=lambda item: item.w)
            cassette_x = int(platform.x + platform.w / 2)
            cassette_y = int(platform.y) - 34
        else:
            cassette_x, cassette_y = self.spawn[0] + 30, self.spawn[1] - 34
        self.cassettes.append({
            "id": str(index), "x": float(cassette_x), "y": float(cassette_y),
            "rect": pygame.Rect(cassette_x - 20, cassette_y - 13, 40, 26),
            "collected": False,
        })
        # Story fragments are no longer world collectibles; the campaign lore
        # is delivered through the safehouse crew dialogue instead.
        self.notes = []
        self.checkpoint_spawn = self.spawn
        self.elapsed = 0.0
        self.coin_doubler: CoinDoubler | None = None
        if index in (2, 5, 8):
            target_x = int(self.width * 0.58)
            item_candidates = []
            for platform in floor_platforms:
                if platform.w < 120:
                    continue
                x = max(int(platform.x) + 38, min(int(platform.x + platform.w) - 38, target_x))
                if any(spike.left - 45 <= x <= spike.right + 45 for spike in self.spikes):
                    continue
                item_candidates.append((abs(x - target_x), x, int(platform.y) - 38))
            if item_candidates:
                _distance, item_x, item_y = min(item_candidates, key=lambda item: item[0])
                self.coin_doubler = CoinDoubler(float(item_x), float(item_y))

    def update(self, dt: float, target_x: float, target_y: float) -> None:
        self.elapsed += dt
        for platform in self.moving_platforms:
            platform.update(self.elapsed)
        self.solids = [p.rect for p in self.platforms]
        for drone in self.drones:
            drone.update(dt, self.solids)
        for seeker in self.seekers:
            seeker.update(dt, target_x, target_y, self.solids)
        for spider in self.spiders:
            spider.update(dt, self.solids)
        for turret in self.turrets:
            shot = turret.update(dt, target_x, target_y, self.solids)
            if shot is not None:
                self.enemy_shots.append(shot)
        for shot in self.enemy_shots:
            shot.update(dt)
            if any(shot.rect.colliderect(solid) for solid in self.solids):
                shot.alive = False
        self.enemy_shots = [shot for shot in self.enemy_shots if shot.alive]
        if self.boss is not None:
            self.boss.update(dt, target_x, target_y)


class Player:
    def __init__(self, spawn: tuple[int, int], character_id: str = "runner",
                 speed_level: int = 0):
        self.character_id = character_id if character_id in CHARACTERS else "runner"
        self.speed_level = max(0, min(3, int(speed_level)))
        self.w, self.h = 30, 43
        self.spawn = spawn
        self.x = float(spawn[0])
        self.y = float(spawn[1])
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1
        self.on_ground = False
        self.coyote = 0.0
        self.jump_buffer = 0.0
        self.dash_time = 0.0
        self.dash_cooldown = 0.0
        self.invuln = 0.0
        self.anim = 0.0
        self.hp = 3
        self.max_hp = 3
        self.dash_used = False
        self.jump_count = 0
        self.shoot_cooldown = 0.0
        self.flight_fuel = 1.65
        self.flight_fuel_max = 1.65
        self.stomp_grace = 0.0
        self.wall_jump_lock = 0.0
        self.touching_left = False
        self.touching_right = False
        self.wall_jump_count = 0
        self.wall_mastery = False
        self.air_overdrive = False
        self.dash_duration = 0.16
        self.dash_cooldown_base = 0.72
        self.extra_jumps = 0
        self.is_flying = False
        self.flight_requested = False
        # Browser touch input; desktop keyboard controls remain unchanged.
        self.mobile_axis = 0.0
        self.mobile_jump = False
        self.mobile_jump_held = False
        # Preserve a brief minimum hold after a touch tap, even if the finger
        # is lifted between browser frames (otherwise mobile jumps become tiny).
        self.mobile_jump_hold_timer = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.x), round(self.y), self.w, self.h)

    def respawn(self, spawn: tuple[int, int], keep_hp: bool = True) -> None:
        old_hp = self.hp
        self.x, self.y = float(spawn[0]), float(spawn[1])
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.coyote = self.jump_buffer = 0.0
        self.dash_time = 0.0
        self.dash_cooldown = 0.25
        self.invuln = 1.4
        self.hp = old_hp if keep_hp else self.max_hp
        self.dash_used = False
        self.jump_count = 0
        self.shoot_cooldown = 0.0
        self.flight_requested = False
        self.flight_fuel = self.flight_fuel_max
        self.stomp_grace = 0.0
        self.wall_jump_lock = 0.0
        self.touching_left = self.touching_right = False

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper,
               level: Level, particles: list[Particle]) -> None:
        self.anim += dt
        self.invuln = max(0.0, self.invuln - dt)
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        self.dash_time = max(0.0, self.dash_time - dt)
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        self.mobile_jump_hold_timer = max(0.0, self.mobile_jump_hold_timer - dt)
        self.shoot_cooldown = max(0.0, self.shoot_cooldown - dt)
        self.stomp_grace = max(0.0, self.stomp_grace - dt)
        self.wall_jump_lock = max(0.0, self.wall_jump_lock - dt)

        left = keys[pygame.K_a] or keys[pygame.K_LEFT] or self.mobile_axis < -0.18
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT] or self.mobile_axis > 0.18
        jump_held = (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]
                     or self.mobile_jump_held or self.mobile_jump_hold_timer > 0.0)

        if left:
            self.facing = -1
        elif right:
            self.facing = 1

        if self.dash_time <= 0 and self.wall_jump_lock <= 0:
            speed_multiplier = 1.0 + 0.12 * self.speed_level
            if not self.on_ground and self.air_overdrive:
                speed_multiplier *= 1.18
            target = (int(right) - int(left)) * 310.0 * speed_multiplier
            accel = (1900.0 if self.on_ground else 1150.0) * speed_multiplier
            if target:
                self.vx += max(-accel * dt, min(accel * dt, target - self.vx))
            else:
                friction = 2200.0 if self.on_ground else 620.0
                if abs(self.vx) <= friction * dt:
                    self.vx = 0.0
                else:
                    self.vx -= math.copysign(friction * dt, self.vx)

        if self.on_ground:
            self.coyote = 0.105
            self.dash_used = False
            self.jump_count = 0
        else:
            self.coyote = max(0.0, self.coyote - dt)

        can_ground_jump = self.coyote > 0
        max_jumps = 2 + self.extra_jumps if self.character_id == "jumper" else 1
        can_double_jump = self.character_id == "jumper" and self.jump_count < max_jumps
        can_wall_jump = level.wall_jump_enabled and not self.on_ground and (self.touching_left or self.touching_right)
        if self.jump_buffer > 0 and (can_ground_jump or can_wall_jump or can_double_jump):
            burst_color = CHARACTERS[self.character_id]["accent"]
            if can_ground_jump:
                # VANTA and CIPHER receive a campaign-specific lift in sectors 06–10
                # so the vertical routes remain fair without changing earlier worlds.
                vertical_boost = level.index >= 5 and self.character_id in ("runner", "shooter")
                self.vy = -800.0 if vertical_boost else -720.0
                self.jump_count += 1
            elif can_wall_jump:
                direction = 1 if self.touching_left else -1
                self.vx = direction * (535.0 if self.wall_mastery else 455.0)
                vertical_boost = level.index >= 5 and self.character_id in ("runner", "shooter")
                wall_launch = 790.0 if vertical_boost else 705.0 if self.wall_mastery else 650.0
                self.vy = -wall_launch
                self.facing = direction
                self.wall_jump_lock = 0.18
                self.wall_jump_count += 1
                self.jump_count = 0
                for _ in range(12):
                    particles.append(Particle(self.x + (self.w if direction > 0 else 0), self.y + self.h / 2,
                                              burst_color, random.uniform(-110, 110),
                                              random.uniform(-170, 30), 0.42, 3.5))
            else:
                self.vy = -700.0
                self.jump_count += 1
            self.on_ground = False
            self.coyote = 0.0
            self.jump_buffer = 0.0
            for _ in range(7):
                particles.append(Particle(self.x + self.w / 2, self.y + self.h,
                                          burst_color, random.uniform(-100, 100),
                                          random.uniform(-145, -25), 0.34, 3.2))

        if not jump_held and self.vy < -190:
            self.vy += 1750.0 * dt

        # Dash is triggered by a fresh key press in the main event loop.
        if self.dash_time <= 0:
            self.vy = min(900.0, self.vy + 1750.0 * dt)
        else:
            self.vy *= 0.94

        # AERIS applies lift after normal gravity, so holding Space really
        # produces upward acceleration instead of merely cancelling gravity.
        self.is_flying = False
        if self.character_id == "flyer":
            # AERIS only starts flying after a second, fresh jump-key press in
            # the air. Holding the first jump never spends flight fuel.
            if self.flight_requested and not self.on_ground and self.flight_fuel > 0:
                self.is_flying = True
                self.vy = max(-330.0, self.vy - 3100.0 * dt)
                self.flight_fuel = max(0.0, self.flight_fuel - dt)
                if self.flight_fuel <= 0.001:
                    self.flight_requested = False
            elif self.on_ground:
                self.flight_requested = False
                self.flight_fuel = min(self.flight_fuel_max,
                                       self.flight_fuel + 1.05 * dt)
            else:
                self.flight_fuel = min(self.flight_fuel_max,
                                       self.flight_fuel + 0.24 * dt)

        # Horizontal collision.
        self.x += self.vx * dt
        rect = self.rect
        for solid in level.solids:
            if rect.colliderect(solid):
                if self.vx > 0:
                    rect.right = solid.left
                elif self.vx < 0:
                    rect.left = solid.right
                self.x = float(rect.x)
                self.vx = 0.0
        probe = self.rect
        self.touching_left = level.wall_jump_enabled and any(
            probe.move(-3, 0).colliderect(solid) and probe.bottom > solid.top + 4
            and probe.top < solid.bottom - 4 for solid in level.solids)
        self.touching_right = level.wall_jump_enabled and any(
            probe.move(3, 0).colliderect(solid) and probe.bottom > solid.top + 4
            and probe.top < solid.bottom - 4 for solid in level.solids)
        if level.wall_jump_enabled and not self.on_ground and (self.touching_left or self.touching_right) and self.vy > 245:
            self.vy = min(self.vy, 205.0 if self.wall_mastery else 315.0)

        # Vertical collision.
        incoming_vertical_speed = self.vy
        self.y += self.vy * dt
        rect = self.rect
        self.on_ground = False
        for solid in level.solids:
            if rect.colliderect(solid):
                if self.vy > 0:
                    rect.bottom = solid.top
                    self.on_ground = True
                    self.dash_used = False
                    self.jump_count = 0
                elif self.vy < 0:
                    rect.top = solid.bottom
                self.y = float(rect.y)
                self.vy = 0.0

        if self.on_ground and incoming_vertical_speed > 120:
            feet = pygame.Rect(int(self.x), int(self.y + self.h - 3), self.w, 8)
            if any(feet.colliderect(pad) for pad in level.launch_pads):
                self.vy = -865.0
                self.on_ground = False
                self.jump_count = 1
                for _ in range(12):
                    particles.append(Particle(self.x + self.w / 2, self.y + self.h,
                                              (91, 245, 226), random.uniform(-100, 100),
                                              random.uniform(80, 210), 0.38, 3.5))

        self.x = max(0.0, min(self.x, level.width - self.w))
        if self.y < 0:
            self.y = 0.0
            self.vy = max(0.0, self.vy)

    def begin_dash(self, particles: list[Particle]) -> None:
        if self.character_id == "runner" and self.dash_cooldown <= 0 and not self.dash_used:
            self.dash_time = self.dash_duration
            self.dash_cooldown = self.dash_cooldown_base
            self.dash_used = True
            self.vx = self.facing * 900.0
            self.vy = 0.0
            for _ in range(12):
                particles.append(Particle(self.x + self.w / 2, self.y + self.h / 2,
                                          CYAN, random.uniform(-220, 220),
                                          random.uniform(-100, 100), 0.28, 3.5))

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        if self.invuln > 0 and int(self.invuln * 12) % 2 == 0:
            return
        x, y = int(self.x - camera_x), int(self.y)
        # Trailing dash streak.
        if self.dash_time > 0:
            for i in range(4):
                alpha = 95 - i * 18
                trail = pygame.Surface((52 + i * 8, 28 + i * 5), pygame.SRCALPHA)
                pygame.draw.ellipse(trail, (55, 238, 227, alpha), trail.get_rect())
                surface.blit(trail, (x - 20 - i * 10 if self.facing > 0 else x - 15 + i * 10,
                                     y + 8 - i * 2))

        # Shadow / feet.
        pygame.draw.ellipse(surface, (4, 7, 17), (x - 5, y + 38, 40, 9))
        cfg = CHARACTERS[self.character_id]
        accent, accent2 = cfg["accent"], cfg["accent2"]
        body = pygame.Rect(x + 2, y + 8, 26, 31)
        pygame.draw.rect(surface, (15, 31, 48), body, border_radius=8)
        pygame.draw.rect(surface, accent, body, 2, border_radius=8)
        # Hood and visor are shared, while each class gets a distinct color.
        hood = pygame.Rect(x, y + 1, 30, 27)
        pygame.draw.rect(surface, (20, 35, 57), hood, border_radius=10)
        pygame.draw.rect(surface, accent, hood, 2, border_radius=10)
        visor = pygame.Rect(x + 5, y + 9, 20, 9)
        pygame.draw.rect(surface, (4, 11, 25), visor, border_radius=4)
        eye_x = x + (18 if self.facing > 0 else 8)
        pygame.draw.circle(surface, accent2, (eye_x, y + 13), 2)
        scarf_points = [(x + 6, y + 25), (x + 25, y + 24),
                        (x + 31 + (3 if self.facing > 0 else -3), y + 30),
                        (x + 16, y + 31)]
        pygame.draw.polygon(surface, accent2, scarf_points)
        if self.character_id == "jumper":
            # Split halo marks the extra mid-air jump.
            pygame.draw.arc(surface, accent2, (x - 5, y - 8, 40, 28), 0.15, 2.85, 2)
            pygame.draw.arc(surface, accent, (x - 5, y - 8, 40, 28), 3.35, 6.05, 2)
        elif self.character_id == "shooter":
            gun_x = x + (22 if self.facing > 0 else -8)
            pygame.draw.rect(surface, (49, 57, 77), (gun_x, y + 22, 16, 7), border_radius=2)
            pygame.draw.rect(surface, accent, (gun_x + (11 if self.facing > 0 else 0), y + 24, 5, 3))
        elif self.character_id == "flyer":
            wing_y = y + 17 + int(math.sin(self.anim * 13) * 3)
            wing_dir = 1 if self.facing > 0 else -1
            pygame.draw.polygon(surface, accent2,
                                [(x + 4, wing_y), (x - 12 * wing_dir, wing_y - 12),
                                 (x + 2, wing_y + 9)])
            pygame.draw.polygon(surface, accent2,
                                [(x + 26, wing_y), (x + 42 * wing_dir, wing_y - 12),
                                 (x + 28, wing_y + 9)])
            gun_x = x + (22 if self.facing > 0 else -8)
            pygame.draw.rect(surface, (49, 57, 77), (gun_x, y + 22, 16, 7), border_radius=2)
            pygame.draw.rect(surface, accent, (gun_x + (11 if self.facing > 0 else 0), y + 24, 5, 3))
        # Feet animate while moving.
        step = math.sin(self.anim * 15) * 2 if abs(self.vx) > 30 and self.on_ground else 0
        pygame.draw.rect(surface, (37, 71, 88), (x + 4, y + 36, 9, 6 + int(step)), border_radius=3)
        pygame.draw.rect(surface, (37, 71, 88), (x + 17, y + 36, 9, 6 - int(step)), border_radius=3)


def spike_hits_player(player_rect: pygame.Rect, spike: pygame.Rect) -> bool:
    """Check against the visible triangular teeth, not the whole spike strip.

    The old rectangular hitbox covered empty space between sloped spike sides,
    so it could hurt the player even when the sprite looked clear.
    """
    count = max(2, spike.w // 22)
    step = spike.w / count
    for i in range(count):
        x1 = spike.x + i * step
        x2 = spike.x + (i + 1) * step
        xm = (x1 + x2) * 0.5
        left = max(player_rect.left, int(x1))
        right = min(player_rect.right, int(x2))
        if left >= right:
            continue
        # The triangle is solid below its two sloping edges. Find the highest
        # edge point inside the player's horizontal span.
        samples = (left, right - 1, max(left, min(right - 1, int(xm))))
        highest_edge = spike.bottom
        half = max(1.0, (x2 - x1) * 0.5)
        for px in samples:
            edge_y = spike.bottom - (spike.bottom - spike.top) * (1.0 - abs(px - xm) / half)
            highest_edge = min(highest_edge, edge_y)
        if player_rect.bottom > highest_edge and player_rect.top < spike.bottom:
            return True
    return False


# -----------------------------------------------------------------------------
# Drawing helpers
# -----------------------------------------------------------------------------
def lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_gradient() -> pygame.Surface:
    surf = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        pygame.draw.line(surf, lerp_color(BG_TOP, BG_BOTTOM, t), (0, y), (WIDTH, y))
    return surf


def draw_text(surface: pygame.Surface, font: pygame.font.Font, text: str,
              color: tuple[int, int, int], pos: tuple[int, int],
              center: bool = False, shadow: bool = False) -> pygame.Rect:
    text = localize(text)
    image = font.render(text, True, color)
    rect = image.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    if shadow:
        shadow_image = font.render(text, True, (0, 0, 0))
        shadow_rect = rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 3
        surface.blit(shadow_image, shadow_rect)
    surface.blit(image, rect)
    return rect


_GLOW_CACHE: dict[tuple[tuple[int, int, int], int], pygame.Surface] = {}

def draw_glow(surface: pygame.Surface, x: int, y: int,
              color: tuple[int, int, int], radius: int) -> None:
    # Glows are static textures. Building an alpha surface for every coin,
    # enemy and projectile on every frame was needlessly expensive.
    key = (tuple(color), int(radius))
    glow = _GLOW_CACHE.get(key)
    if glow is None:
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for r in range(radius, 2, -4):
            alpha = max(2, int(22 * (r / radius) ** 2))
            pygame.draw.circle(glow, (*color, alpha), (radius, radius), r)
        _GLOW_CACHE[key] = glow
    surface.blit(glow, (x - radius, y - radius), special_flags=pygame.BLEND_RGBA_ADD)


def draw_coin(surface: pygame.Surface, coin: Coin, camera_x: float, now: float,
              accent: tuple[int, int, int]) -> None:
    if coin.collected:
        return
    x = int(coin.x - camera_x)
    if x < -30 or x > WIDTH + 30:
        return
    y = int(coin.y + math.sin(now * 4 + coin.phase) * 5)
    pulse = 1.0 + 0.12 * math.sin(now * 7 + coin.phase)
    r = int(9 * pulse)
    draw_glow(surface, x, y, accent, 22)
    pygame.draw.circle(surface, (255, 240, 178), (x, y), r + 2, 1)
    pygame.draw.polygon(surface, accent,
                        [(x, y - r), (x + r, y), (x, y + r), (x - r, y)])
    pygame.draw.circle(surface, (255, 255, 230), (x - 2, y - 2), 2)


def draw_drone(surface: pygame.Surface, drone: Drone, camera_x: float,
               accent2: tuple[int, int, int]) -> None:
    if not drone.alive:
        return
    x = int(drone.x - camera_x)
    y = int(drone.y + math.sin(drone.phase) * 3)
    draw_glow(surface, x, y, accent2, 28)
    shell = pygame.Rect(x - 18, y - 12, 36, 24)
    pygame.draw.rect(surface, (31, 28, 51), shell, border_radius=9)
    pygame.draw.rect(surface, accent2, shell, 2, border_radius=9)
    pygame.draw.line(surface, (165, 178, 205), (x - 12, y - 13), (x - 18, y - 20), 2)
    pygame.draw.line(surface, (165, 178, 205), (x + 12, y - 13), (x + 18, y - 20), 2)
    pygame.draw.circle(surface, (255, 237, 235), (x, y), 5)
    pygame.draw.circle(surface, accent2, (x, y), 3)
    pygame.draw.line(surface, (8, 12, 28), (x - 11, y + 16), (x + 11, y + 16), 2)


def draw_seeker(surface: pygame.Surface, seeker: Seeker, camera_x: float,
                accent: tuple[int, int, int]) -> None:
    if not seeker.alive:
        return
    x = int(seeker.x - camera_x)
    y = int(seeker.y + math.sin(seeker.phase * 1.8) * 3)
    draw_glow(surface, x, y, accent, 36)
    pygame.draw.circle(surface, (30, 25, 48), (x, y), 16)
    pygame.draw.circle(surface, accent, (x, y), 15, 2)
    # Broken, rotating outer ring makes this enemy visually distinct from drones.
    angle = seeker.phase * 1.4
    for i in range(4):
        a = angle + i * math.pi / 2
        p1 = (int(x + math.cos(a) * 19), int(y + math.sin(a) * 19))
        p2 = (int(x + math.cos(a + 0.42) * 24), int(y + math.sin(a + 0.42) * 24))
        pygame.draw.line(surface, WHITE, p1, p2, 3)
    pygame.draw.circle(surface, (255, 247, 225), (x, y), 6)
    pygame.draw.circle(surface, accent, (x, y), 3)


def draw_spider(surface: pygame.Surface, spider: Spider, camera_x: float, accent) -> None:
    if not spider.alive:
        return
    x, y = int(spider.x - camera_x), int(spider.y)
    draw_glow(surface, x, y, accent, 28)
    pygame.draw.circle(surface, (24, 28, 48), (x, y), 12)
    pygame.draw.circle(surface, accent, (x, y), 11, 2)
    for side in (-1, 1):
        for dy in (-7, 0, 7):
            pygame.draw.line(surface, accent, (x + side * 7, y + dy),
                             (x + side * 18, y + dy + side * 4), 2)
    pygame.draw.circle(surface, WHITE, (x - 3, y - 2), 2)
    pygame.draw.circle(surface, WHITE, (x + 3, y - 2), 2)


def draw_turret(surface: pygame.Surface, turret: Turret, camera_x: float, accent) -> None:
    if not turret.alive:
        return
    x, y = int(turret.x - camera_x), int(turret.y)
    draw_glow(surface, x, y, accent, 32)
    body = pygame.Rect(x - 17, y - 16, 34, 32)
    pygame.draw.rect(surface, (31, 28, 49), body, border_radius=5)
    pygame.draw.rect(surface, accent, body, 2, border_radius=5)
    pygame.draw.circle(surface, (255, 228, 226), (x, y), 6)
    pygame.draw.circle(surface, accent, (x, y), 3)
    pygame.draw.line(surface, accent, (x, y + 16), (x, y + 22), 3)


def draw_secret_marker(surface: pygame.Surface, secret: dict, camera_x: float, now: float, accent) -> None:
    if secret["found"]:
        return
    rect = secret["rect"]
    x = rect.centerx - camera_x
    if -140 < x < WIDTH + 140:
        pulse = int(70 + 35 * math.sin(now * 2.4))
        r = pygame.Rect(int(x - rect.w / 2), rect.y, rect.w, rect.h)
        pygame.draw.rect(surface, (*accent, pulse), r, 2, border_radius=5)
        pygame.draw.line(surface, accent, (r.centerx, r.top + 8), (r.centerx, r.bottom - 8), 2)


def draw_projectile(surface: pygame.Surface, shot: Projectile, camera_x: float) -> None:
    x, y = int(shot.x - camera_x), int(shot.y)
    fade = max(0.18, min(1.0, shot.life / 0.22))
    radius = max(1, int(shot.radius * fade))
    draw_glow(surface, x, y, shot.color, max(2, int((20 if shot.radius <= 6 else 25) * fade)))
    pygame.draw.circle(surface, shot.color, (x, y), radius)
    pygame.draw.circle(surface, WHITE, (x - 2, y - 2), max(1, radius // 2))


def draw_boss(surface: pygame.Surface, boss: Boss, camera_x: float) -> None:
    if not boss.active or boss.defeated:
        return
    x, y = int(boss.x - camera_x), int(boss.y)
    phase_two = boss.hp <= boss.max_hp // 2
    if boss.variant == "warden":
        core = (105, 244, 255) if not phase_two else (240, 255, 255)
        shell_color = (18, 42, 67) if not phase_two else (28, 63, 88)
    elif boss.variant == "arena":
        core = (255, 203, 91) if not phase_two else (255, 130, 75)
        shell_color = (54, 43, 29) if not phase_two else (71, 35, 25)
    else:
        core = (255, 65, 108) if phase_two else (255, 119, 91)
        shell_color = (45, 28, 53) if phase_two else (27, 37, 58)
    if boss.state.startswith("windup") or boss.state == "charge":
        draw_glow(surface, x, y, core, 100 if boss.state == "charge" else 70)
    else:
        draw_glow(surface, x, y, core, 58)
    # Floating armor, broad shoulders and a split mechanical crown.
    pygame.draw.polygon(surface, shell_color,
                        [(x - 35, y - 40), (x - 52, y - 60), (x - 19, y - 53),
                         (x, y - 65), (x + 19, y - 53), (x + 52, y - 60),
                         (x + 35, y - 40), (x + 43, y + 34), (x + 22, y + 52),
                         (x - 22, y + 52), (x - 43, y + 34)])
    pygame.draw.polygon(surface, (112, 75, 104) if phase_two else (69, 96, 119),
                        [(x - 35, y - 40), (x - 52, y - 60), (x - 19, y - 53),
                         (x, y - 65), (x + 19, y - 53), (x + 52, y - 60),
                         (x + 35, y - 40), (x + 43, y + 34), (x + 22, y + 52),
                         (x - 22, y + 52), (x - 43, y + 34)], 3)
    # Side armor and claws.
    pygame.draw.rect(surface, shell_color, (x - 61, y - 17, 23, 43), border_radius=7)
    pygame.draw.rect(surface, shell_color, (x + 38, y - 17, 23, 43), border_radius=7)
    pygame.draw.line(surface, core, (x - 51, y + 20), (x - 62, y + 39), 4)
    pygame.draw.line(surface, core, (x + 51, y + 20), (x + 62, y + 39), 4)
    # Faceplate and eyes.
    face = pygame.Rect(x - 30, y - 29, 60, 47)
    pygame.draw.rect(surface, (7, 12, 29), face, border_radius=12)
    pygame.draw.rect(surface, core, face, 2, border_radius=12)
    eye_y = y - 10
    pygame.draw.line(surface, core, (x - 21, eye_y), (x - 7, eye_y), 5)
    pygame.draw.line(surface, core, (x + 7, eye_y), (x + 21, eye_y), 5)
    pygame.draw.circle(surface, WHITE, (x, y + 7), 5)
    pygame.draw.circle(surface, core, (x, y + 7), 3)
    if boss.variant == "warden":
        # Three orbital relays make the final boss visually distinct from THE CORE.
        for i in range(3):
            angle = boss.phase * (1.0 if i % 2 == 0 else -1.2) + i * math.tau / 3
            ox = x + int(math.cos(angle) * 76)
            oy = y + int(math.sin(angle) * 54)
            pygame.draw.circle(surface, (22, 62, 82), (ox, oy), 13)
            pygame.draw.circle(surface, core, (ox, oy), 8, 2)
            pygame.draw.circle(surface, WHITE, (ox, oy), 2)
        pygame.draw.polygon(surface, core,
                            [(x, y - 82), (x + 12, y - 65), (x, y - 52), (x - 12, y - 65)], 2)
    elif boss.variant == "arena":
        pygame.draw.rect(surface, core, (x - 24, y - 5, 48, 10), border_radius=4)
        pygame.draw.circle(surface, WHITE, (x, y), 5)
    # Visible wind-up cue.
    if boss.state.startswith("windup"):
        pygame.draw.circle(surface, core, (x, y), 73, 2)
        pygame.draw.arc(surface, WHITE, (x - 78, y - 78, 156, 156),
                        boss.phase, boss.phase + 2.2, 3)
    if boss.flash > 0:
        pygame.draw.circle(surface, WHITE, (x, y), 58, 3)


def draw_platform(surface: pygame.Surface, p: Platform, camera_x: float,
                  accent: tuple[int, int, int]) -> None:
    x = int(p.x - camera_x)
    if x > WIDTH or x + p.w < 0:
        return
    rect = pygame.Rect(x, p.y, p.w, p.h)
    shadow_rect = pygame.Rect(x + 4, p.y + 7, p.w, p.h)
    pygame.draw.rect(surface, (5, 9, 20), shadow_rect, border_radius=4)
    pygame.draw.rect(surface, (17, 26, 45), rect, border_radius=4)
    pygame.draw.rect(surface, (37, 55, 75), rect, 1, border_radius=4)
    pygame.draw.line(surface, accent, (x + 3, p.y), (x + p.w - 3, p.y), 3)
    # Subtle panels and bolts.
    # Recessed panels, tiny fasteners and a lower bevel give the metal more
    # depth without relying on external low-resolution textures.
    pygame.draw.line(surface, (76, 103, 126), (x + 5, p.y + 4),
                     (x + p.w - 5, p.y + 4), 1)
    pygame.draw.line(surface, (7, 12, 25), (x + 4, p.y + p.h - 3),
                     (x + p.w - 4, p.y + p.h - 3), 2)
    for px in range(x + 18, x + p.w - 8, 42):
        pygame.draw.rect(surface, (22, 37, 57), (px, p.y + 8, 25, max(8, p.h - 15)), 1, border_radius=2)
        pygame.draw.line(surface, (40, 58, 79), (px + 4, p.y + 12),
                         (px + 15, p.y + 12), 1)
        pygame.draw.circle(surface, (91, 119, 139), (px + 3, p.y + 5), 1)
        pygame.draw.circle(surface, (8, 14, 27), (px + 20, p.y + 5), 1)


def draw_spikes(surface: pygame.Surface, spike: pygame.Rect, camera_x: float,
                accent2: tuple[int, int, int]) -> None:
    x = int(spike.x - camera_x)
    if x > WIDTH or x + spike.w < 0:
        return
    count = max(2, spike.w // 22)
    step = spike.w / count
    for i in range(count):
        x1 = int(x + i * step)
        x2 = int(x + (i + 1) * step)
        xm = (x1 + x2) // 2
        points = [(x1, spike.bottom), (xm, spike.top), (x2, spike.bottom)]
        pygame.draw.polygon(surface, (43, 24, 45), points)
        pygame.draw.lines(surface, accent2, False,
                          [(x1, spike.bottom), (xm, spike.top), (x2, spike.bottom)], 2)


def draw_checkpoint(surface: pygame.Surface, cp: Checkpoint, camera_x: float,
                    accent: tuple[int, int, int], now: float) -> None:
    x = cp.x - camera_x
    if x < -40 or x > WIDTH + 40:
        return
    color = accent if cp.active else (94, 109, 133)
    pygame.draw.line(surface, (95, 113, 137), (int(x), cp.y - 58), (int(x), cp.y), 3)
    wave = math.sin(now * 4 + cp.x) * 5
    flag = [(int(x), cp.y - 56), (int(x + 29 + wave), cp.y - 48),
            (int(x), cp.y - 38)]
    pygame.draw.polygon(surface, color, flag)
    if cp.active:
        draw_glow(surface, int(x + 8), cp.y - 47, accent, 20)
        pygame.draw.circle(surface, WHITE, (int(x), cp.y - 57), 3)


def draw_exit(surface: pygame.Surface, rect: pygame.Rect, camera_x: float,
              accent: tuple[int, int, int], now: float) -> None:
    x = int(rect.x - camera_x)
    if x < -100 or x > WIDTH + 100:
        return
    center = (x + rect.w // 2, rect.y + rect.h // 2)
    draw_glow(surface, center[0], center[1], accent, 66)
    frame = pygame.Rect(x, rect.y, rect.w, rect.h)
    pygame.draw.rect(surface, (14, 21, 40), frame, border_radius=25)
    pygame.draw.rect(surface, accent, frame, 3, border_radius=25)
    inner = frame.inflate(-13, -13)
    pygame.draw.rect(surface, (8, 12, 28), inner, border_radius=20)
    pulse = 3 + int(2 * math.sin(now * 6))
    pygame.draw.ellipse(surface, accent, inner.inflate(-13 + pulse, -8 + pulse), 2)
    pygame.draw.line(surface, WHITE, (center[0], rect.y + 18),
                     (center[0], rect.bottom - 18), 1)


# -----------------------------------------------------------------------------
# Main game
# -----------------------------------------------------------------------------
_BACKGROUND_WASH_CACHE: dict[tuple[tuple[int, int, int], tuple[int, int, int]], pygame.Surface] = {}

class Game:
    def __init__(self):
        # Keep the browser mixer lightweight: mono at 22.05 kHz uses
        # substantially less processing than 44.1 kHz stereo. A larger buffer
        # gives the WebAssembly audio callback more room during busy frames.
        if sys.platform == "emscripten":
            mixer_config = {"frequency": 22050, "size": -16, "channels": 1, "buffer": 2048}
        else:
            mixer_config = {"frequency": 22050, "size": -16, "channels": 1, "buffer": 512}
        try:
            pygame.mixer.pre_init(**mixer_config)
        except pygame.error:
            pass
        pygame.init()
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(**mixer_config)
        except pygame.error:
            pass
        pygame.display.set_caption(TITLE + "  |  v2.0")
        self.fullscreen = False
        self.show_fps = False
        self.windowed_size = (WIDTH, HEIGHT)
        self.display = self.create_display()
        # All game drawing stays at a fixed logical resolution. The final frame
        # is scaled into the window/monitor viewport, avoiding SCALED-mode
        # fullscreen bugs and stretched coordinates after F11.
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self.clock = pygame.time.Clock()
        self.running = True
        self.gradient = make_gradient()
        self.surface_grain = self.make_surface_grain()
        self.vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(self.vignette, (0, 0, 0, 62), (0, 0, WIDTH, 35))
        pygame.draw.rect(self.vignette, (0, 0, 0, 48), (0, HEIGHT - 42, WIDTH, 42))
        self.pause_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.pause_overlay.fill((3, 5, 16, 190))
        self.level_banner_surface = pygame.Surface((WIDTH, 105), pygame.SRCALPHA)
        # The skyline is pre-rendered once per sector. Windows are baked into
        # the buildings, so they can never flicker or drift independently.
        self.skyline_layers = [self.make_skyline(i) for i in range(len(LEVELS))]
        # Arial has more balanced proportions and remains readable after browser scaling.
        self.font_xs = pygame.font.SysFont("arial", 14, bold=True)
        self.font_s = pygame.font.SysFont("arial", 17, bold=True)
        self.font_m = pygame.font.SysFont("arial", 23, bold=True)
        self.font_l = pygame.font.SysFont("arial", 38, bold=True)
        self.font_xl = pygame.font.SysFont("arial", 70, bold=True)
        self.font_title = pygame.font.SysFont("arial", 84, bold=True)
        self.stars = []
        rng = random.Random(167)
        for _ in range(100):
            self.stars.append((rng.randrange(0, 5000), rng.randrange(20, 440),
                               rng.choice([0.08, 0.14, 0.22, 0.32]),
                               rng.randrange(1, 3), rng.random() * math.tau))
        self.browser_save_key = "oxygen_savegame_v2"
        self.browser_owner_marker_key = "oxygen_owner_save_recovered_v1"
        self.browser_storage = None
        self.browser_storage_error = None
        self.migrate_legacy_seed = False
        self.keep_legacy_seed = False
        if sys.platform == "emscripten":
            # Pygbag's documented browser persistence API. localStorage is
            # isolated per browser profile and is synchronous, so coin pickups
            # are committed before the frame continues.
            try:
                import platform as browser_platform
                self.browser_storage = browser_platform.window.localStorage
                query = str(browser_platform.window.location.search or "")
                self.migrate_legacy_seed = "keep_legacy_save=1" in query
                self.keep_legacy_seed = (
                    self.migrate_legacy_seed
                    or str(self.browser_storage.getItem(self.browser_owner_marker_key)) == "1"
                )
                if self.migrate_legacy_seed:
                    # Remember that this profile intentionally owns the
                    # recovered legacy save, even after the URL is cleaned.
                    self.browser_storage.setItem(self.browser_owner_marker_key, "1")
            except Exception as exc:
                self.browser_storage_error = str(exc)
            # Keep the previous file path only as a one-time migration source.
            self.save_path = Path("/data/savegame.json")
            try:
                self.save_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        else:
            self.save_path = Path(__file__).with_name("savegame.json")
        self.save_data = self.load_save_data()
        self.language = self.save_data.get("language", "en")
        set_language(self.language)
        self.character_selected = bool(self.save_data.get("character_selected", False))
        saved_character = self.save_data.get("selected_character", "runner")
        self.character_index = CHARACTER_IDS.index(saved_character) if saved_character in CHARACTER_IDS else 0
        self.pending_start_level: int | None = None
        self.collected_coin_keys = set(self.save_data.get("collected_coins", []))
        self.total_coins = int(self.save_data.get("coins", 0))
        self.apply_pending_achievement_rewards()
        self.mode = "menu"
        self.mobile_jump_was_down = False
        self.mobile_menu_requested = False
        self.level_index = 0
        self.level = Level(0)
        self.player = Player(self.level.spawn, speed_level=self.save_data["speed_level"])
        self.camera_x = 0.0
        self.particles: list[Particle] = []
        self.score = 0
        self.time = 0.0
        self.level_banner = 2.8
        self.notice = ""
        self.notice_timer = 0.0
        self.shake = 0.0
        self.pause_selection = 0
        self.menu_selection = 0
        self.skill_selection = 0
        self.journal_selection = 0
        self.level_select_selection = 0
        self.character_select_selection = self.character_index
        self.projectiles: list[Projectile] = []
        self.store_selection = 0
        self.achievement_scroll = 0
        self.last_wall_jump_count = 0
        self.menu_notice = ""
        self.menu_notice_timer = 0.0
        self._scaled_frame: pygame.Surface | None = None
        self._scaled_size: tuple[int, int] | None = None
        self._shake_offset = 0
        self.level_elapsed = 0.0
        self.level_deaths = 0
        self.footstep_timer = 0.0
        self.level_coins = 0
        self.level_secrets = 0
        self.pending_next_level: int | None = None
        self.last_rating: dict = {}
        self.safehouse_selection = 0
        self.safehouse_player_speed = 250.0
        self.safehouse_dialog_npc = None
        self.safehouse_dialog_selection = 0
        self.safehouse_interaction_hint = ""
        self.cassette_selection = 0
        self.cassette_playing = False
        self.secret_167_page = 0
        self.safehouse_event_active = False
        self.safehouse_event_elapsed = 0.0
        self.personnel_selection = 0
        self.personnel_open = False
        self.mods_return_mode = "safehouse"
        # Only the three actual quest-givers appear in the shelter.
        self.hub_npc_positions = (270, 770, 900, 490)
        self.hub_armory_x = 1015
        self.hub_gate_x = 85
        self.safehouse_world = SafehouseWorld()
        self.safehouse_filter_x = 545
        self.filter_dialog_open = False
        self.run_filter_hp_bonus = False
        self.character_return_mode = "menu"
        self.coin_multiplier_timer = 0.0
        self.achievement_popup_title = ""
        self.achievement_popup_timer = 0.0
        self.boss_arena_active = False
        self.boss_arena_bounds: tuple[int, int, int] | None = None
        self.is_arena_mode = False
        self.arena_wave = 1
        self.arena_spawn_remaining = 0
        self.arena_spawned = 0
        self.arena_spawn_target = 0
        self.arena_spawn_timer = 0.0
        self.arena_boss_spawned = False
        self.arena_bosses_defeated = 0
        self.mods_character_index = self.character_index
        self.mods_selection = 0
        self.ranking_scroll = 0
        self.music_scene = None
        self.music_transition_target: tuple[str, float] | None = None
        self.music_transition_timer = 0.0
        self.music_enabled = bool(pygame.mixer.get_init())
        self.music_volume = max(0.0, min(1.0, float(self.save_data.get("music_volume", 0.75))))
        self.sfx_volume = max(0.0, min(1.0, float(self.save_data.get("sfx_volume", 0.75))))
        self.music_track_volume = 0.17
        self.settings_drag: str | None = None
        self.audio_root = Path(__file__).with_name("assets") / "audio"
        self.music_root = self.audio_root / "music"
        self.sfx_root = self.audio_root / "sfx"
        self.sfx: dict[str, pygame.mixer.Sound] = {}
        self.sfx_gains = {"checkpoint": 0.58, "kill": 0.48, "death": 0.58,
                          "footstep": 0.13, "landing": 0.20, "jump": 0.16}
        self.boss_music: dict[str, pygame.mixer.Sound] = {}
        self.boss_music_channel = None
        self.active_boss_music: str | None = None
        self.load_audio_assets()
        self.healing_crystal: HealingCrystal | None = None
        self.boss_crystal_timer = 0.0  # campaign-play cooldown (30 minutes)
        self.boss_fight_elapsed = 0.0
        self.boss_crystal_delay = random.uniform(25.0, 50.0)
        self.set_music_scene("menu")
        if sys.platform == "emscripten":
            # Create a clean per-browser save immediately on first launch and
            # persist any successfully migrated legacy progress.
            self.save_progress()

    def load_save_data(self) -> dict:
        defaults = {"coins": 0, "unlocked_levels": 1, "boss_cleared": False,
                    "unlocked_flyer": False, "collected_coins": [],
                    "speed_level": 0, "strength_level": 0,
                    "found_secrets": [], "achievements": [],
                    "completed_levels": [],
                    "skills": {"wall_mastery": False, "coin_echo": False,
                               "signal_shield": False, "air_overdrive": False},
                    "stats": {"coins_collected": 0, "kills": 0, "wall_jumps": 0,
                              "levels_completed": 0, "deaths": 0},
                    "quest_claimed": [], "quest_active": [], "quest_baselines": {},
                    "achievement_rewards": [], "arena_best_wave": 0,
                    "warden_cleared": False,
                    "character_mods": {cid: [] for cid in CHARACTER_IDS},
                    "level_ratings": {}, "last_level": -1, "language": "en",
                    "selected_character": "runner", "character_selected": False,
                    "filter_charge": 35, "filter_boost": False,
                    "collected_doublers": [], "collected_cassettes": [],
                    "postgame_event_pending": False, "postgame_event_seen": False,
                    "secret_167_unlocked": False, "safehouse_lighting_upgraded": False,
                    "radio_log_index": 0, "last_run_deaths": 0,
                    "music_volume": 0.75,
                    "sfx_volume": 0.75}
        def is_bundled_test_save(data: dict) -> bool:
            # This exact profile was accidentally shipped to every new player
            # in an older web archive. Do not migrate it into a fresh browser.
            stats = data.get("stats", {})
            return (
                data.get("coins") == 194
                and data.get("unlocked_levels") == 4
                and data.get("collected_coins") and len(data["collected_coins"]) == 58
                and data.get("completed_levels") == ["0", "1", "2"]
                and data.get("last_level") == 3
                and set(data.get("achievements", [])) == {
                    "first_signal", "coin_archive", "first_blood",
                    "coin_runner", "machine_breaker", "contract_runner"
                }
                and isinstance(stats, dict)
                and stats.get("coins_collected") == 219
                and stats.get("kills") == 44
                and stats.get("deaths") == 13
            )

        try:
            loaded = None
            if self.browser_storage is not None:
                stored_text = self.browser_storage.getItem(self.browser_save_key)
                if stored_text:
                    candidate = json.loads(str(stored_text))
                    if isinstance(candidate, dict):
                        if (
                            sys.platform == "emscripten"
                            and is_bundled_test_save(candidate)
                            and not self.keep_legacy_seed
                        ):
                            # A previous web release may already have copied
                            # the bundled test profile into localStorage.
                            # Normal visitors must not inherit that profile.
                            loaded = None
                        else:
                            loaded = candidate

            # One-time migration for a genuinely changed legacy browser save.
            # The known 194-coin bundled test profile is deliberately ignored.
            # Allow the owner's one-time recovery link to replace only a
            # pristine localStorage save created by an earlier rollout.
            if (
                self.migrate_legacy_seed
                and isinstance(loaded, dict)
                and int(loaded.get("coins", 0) or 0) == 0
                and not loaded.get("collected_coins")
                and int(loaded.get("unlocked_levels", 1) or 1) <= 1
                and not loaded.get("completed_levels")
                and not loaded.get("achievements")
            ):
                loaded = None

            if loaded is None and self.save_path.exists():
                candidate = json.loads(self.save_path.read_text(encoding="utf-8"))
                if isinstance(candidate, dict) and (
                    sys.platform != "emscripten"
                    or not is_bundled_test_save(candidate)
                    or self.keep_legacy_seed
                ):
                    loaded = candidate

            if isinstance(loaded, dict):
                defaults.update(loaded)
        except Exception:
            # A damaged/blocked browser save should never prevent the game
            # from starting; the next successful save will create a clean file.
            pass
        def safe_int(value, fallback=0):
            try:
                return int(value)
            except (TypeError, ValueError, OverflowError):
                return fallback
        defaults["coins"] = max(0, safe_int(defaults.get("coins", 0)))
        defaults["unlocked_levels"] = max(1, min(len(LEVELS), safe_int(defaults.get("unlocked_levels", 1), 1)))
        if defaults.get("boss_cleared"):
            defaults["unlocked_levels"] = max(defaults["unlocked_levels"], 6)
        defaults["speed_level"] = max(0, min(3, safe_int(defaults.get("speed_level", 0))))
        defaults["strength_level"] = max(0, min(2, safe_int(defaults.get("strength_level", 0))))
        defaults["boss_cleared"] = bool(defaults.get("boss_cleared", False))
        defaults["unlocked_flyer"] = bool(defaults.get("unlocked_flyer", False) or defaults["boss_cleared"])
        raw_coins = defaults.get("collected_coins", [])
        defaults["collected_coins"] = [str(v) for v in raw_coins] if isinstance(raw_coins, list) else []
        for key in ("found_secrets", "achievements", "completed_levels",
                    "quest_claimed", "quest_active", "achievement_rewards",
                    "collected_doublers", "collected_cassettes"):
            raw = defaults.get(key, [])
            defaults[key] = [str(v) for v in raw] if isinstance(raw, list) else []
        raw_skills = defaults.get("skills", {})
        if not isinstance(raw_skills, dict):
            raw_skills = {}
        skill_names = ("wall_mastery", "coin_echo", "signal_shield", "air_overdrive")
        defaults["skills"] = {name: bool(raw_skills.get(name, False)) for name in skill_names}
        if not isinstance(defaults.get("quest_baselines"), dict):
            defaults["quest_baselines"] = {}
        defaults["arena_best_wave"] = max(0, safe_int(defaults.get("arena_best_wave", 0)))
        defaults["warden_cleared"] = bool(defaults.get("warden_cleared", False))
        defaults["postgame_event_pending"] = bool(defaults.get("postgame_event_pending", False))
        defaults["postgame_event_seen"] = bool(defaults.get("postgame_event_seen", False))
        defaults["secret_167_unlocked"] = bool(
            defaults.get("secret_167_unlocked", False) or defaults["postgame_event_seen"])
        defaults["safehouse_lighting_upgraded"] = bool(
            defaults.get("safehouse_lighting_upgraded", False)
            or "restore_lights" in defaults.get("quest_claimed", []))
        defaults["collected_cassettes"] = sorted(
            {str(value) for value in defaults["collected_cassettes"]
             if str(value).isdigit() and 0 <= int(value) < len(LEVELS)},
            key=lambda value: int(value))
        raw_stats = defaults.get("stats", {})
        if not isinstance(raw_stats, dict):
            raw_stats = {}
        stat_names = ("coins_collected", "kills", "wall_jumps", "levels_completed",
                      "deaths", "contracts_completed", "arena_bosses")
        defaults["stats"] = {name: max(0, safe_int(raw_stats.get(name, 0))) for name in stat_names}
        raw_mods = defaults.get("character_mods", {})
        if not isinstance(raw_mods, dict):
            raw_mods = {}
        defaults["character_mods"] = {}
        for cid, allowed in ABILITY_MODS.items():
            allowed_ids = {item[0] for item in allowed}
            owned = raw_mods.get(cid, [])
            defaults["character_mods"][cid] = [str(v) for v in owned if str(v) in allowed_ids] if isinstance(owned, list) else []
        if not isinstance(defaults.get("level_ratings"), dict):
            defaults["level_ratings"] = {}
        # Retire v1.8's optional ending/archive state during migration.
        defaults.pop("found_notes", None)
        defaults.pop("endings_unlocked", None)
        defaults.pop("endings_seen", None)
        defaults.pop("ending_choice", None)
        # Migrate progress from earlier releases while preserving existing wallet and unlocks.
        if not defaults["completed_levels"] and defaults["unlocked_levels"] > 1:
            # Older saves only stored the highest unlocked sector. Reconstruct
            # the sequential campaign progress without discarding chapters 2.
            old_cleared = min(len(LEVELS), defaults["unlocked_levels"] - 1)
            if defaults["boss_cleared"]:
                old_cleared = max(5, old_cleared)
            defaults["completed_levels"] = [str(i) for i in range(old_cleared)]
        defaults["stats"]["levels_completed"] = max(
            defaults["stats"]["levels_completed"], len(defaults["completed_levels"]))
        defaults["stats"]["coins_collected"] = max(
            defaults["stats"]["coins_collected"], len(defaults["collected_coins"]))
        defaults["filter_charge"] = max(0, min(100, safe_int(defaults.get("filter_charge", 35), 35)))
        defaults["filter_boost"] = bool(defaults.get("filter_boost", False))
        defaults["language"] = "ru" if defaults.get("language") == "ru" else "en"
        selected = defaults.get("selected_character", "runner")
        defaults["selected_character"] = selected if selected in CHARACTER_IDS else "runner"
        defaults["character_selected"] = bool(defaults.get("character_selected", False))
        saved_last = safe_int(defaults.get("last_level", -1), -1)
        if saved_last < 0:
            completed = set(defaults["completed_levels"])
            saved_last = next((i for i in range(defaults["unlocked_levels"])
                               if str(i) not in completed),
                              max(0, defaults["unlocked_levels"] - 1))
        defaults["last_level"] = max(0, min(len(LEVELS) - 1, saved_last))
        return defaults

    def save_progress(self) -> None:
        self.save_data["coins"] = int(self.total_coins)
        self.save_data["collected_coins"] = sorted(self.collected_coin_keys)
        try:
            payload = json.dumps(self.save_data, ensure_ascii=False, separators=(",", ":"))
            if sys.platform == "emscripten":
                if self.browser_storage is None:
                    raise RuntimeError("Browser localStorage is unavailable")
                self.browser_storage.setItem(self.browser_save_key, payload)
                # Verify the write immediately rather than silently claiming
                # that progress was saved when browser storage rejected it.
                if str(self.browser_storage.getItem(self.browser_save_key)) != payload:
                    raise RuntimeError("Browser save verification failed")
            else:
                self.save_path.write_text(payload, encoding="utf-8")
        except Exception:
            self.menu_notice = "SAVE FAILED // BROWSER STORAGE UNAVAILABLE"
            self.menu_notice_timer = 4.0
            self.notice = self.menu_notice
            self.notice_timer = 4.0

    def level_is_unlocked(self, index: int) -> bool:
        return index < int(self.save_data.get("unlocked_levels", 1))

    def character_is_unlocked(self, character_id: str) -> bool:
        return character_id != "flyer" or bool(self.save_data.get("unlocked_flyer", False))

    def purchase_store_item(self, item_index: int) -> None:
        if item_index == 0:
            costs = (25, 40, 60)
            level = self.save_data["speed_level"]
            if level >= len(costs):
                self.menu_notice = "RUN SPEED // MAX LEVEL"
            elif self.total_coins >= costs[level]:
                self.total_coins -= costs[level]
                self.save_data["speed_level"] = level + 1
                self.menu_notice = "RUN SPEED UPGRADED"
                self.save_progress()
            else:
                self.menu_notice = "NOT ENOUGH COINS"
        elif item_index == 1:
            costs = (30, 45)
            level = self.save_data["strength_level"]
            if level >= len(costs):
                self.menu_notice = "STOMP POWER // MAX LEVEL"
            elif self.total_coins >= costs[level]:
                self.total_coins -= costs[level]
                self.save_data["strength_level"] = level + 1
                self.menu_notice = "STOMP POWER UPGRADED"
                self.save_progress()
            else:
                self.menu_notice = "NOT ENOUGH COINS"
        self.menu_notice_timer = 2.0
        self.save_progress()

    def load_audio_assets(self) -> None:
        """Load replaceable music/SFX assets. Missing files are intentionally optional."""
        if not self.music_enabled:
            return
        try:
            pygame.mixer.set_num_channels(max(10, pygame.mixer.get_num_channels()))
            self.flight_sfx_channel = pygame.mixer.Channel(7)
            self.boss_music_channel = pygame.mixer.Channel(8)
        except pygame.error:
            self.flight_sfx_channel = None
            self.boss_music_channel = None
        # Decode boss themes during the initial audio setup, not at the exact
        # moment a boss appears. Sound channels can then switch instantly while
        # the campaign music stream remains loaded and ready to resume.
        for key, filename in (("boss_05", "boss_sector_05.ogg"),
                              ("boss_10", "boss_sector_10.ogg")):
            path = self.music_root / filename
            if path.exists():
                try:
                    self.boss_music[key] = pygame.mixer.Sound(str(path))
                except Exception as exc:
                    print(f"OXYGEN boss music preload failed ({filename}): {exc}", file=sys.stderr)
        for name in ("shoot", "dash", "double_jump", "flight", "coin", "achievement"):
            extension = "ogg" if sys.platform == "emscripten" else "wav"
            path = self.sfx_root / f"{name}.{extension}"
            if path.exists():
                try:
                    self.sfx[name] = pygame.mixer.Sound(str(path))
                    self.sfx[name].set_volume(self.sfx_volume)
                except pygame.error:
                    pass

        # These small synthesized cues keep the repository lightweight and
        # avoid adding more streamed audio files to the browser build.
        try:
            generated = {
                "checkpoint": make_synth_sfx(0.34, 620, 1040, 0.30, "sine", 0.015, 11),
                "kill": make_synth_sfx(0.17, 520, 145, 0.28, "triangle", 0.10, 23),
                "death": make_synth_sfx(0.43, 360, 58, 0.32, "saw", 0.16, 37),
                "footstep": make_synth_sfx(0.055, 105, 62, 0.20, "sine", 0.28, 41),
                "landing": make_synth_sfx(0.12, 115, 48, 0.26, "sine", 0.34, 53),
                "jump": make_synth_sfx(0.11, 210, 390, 0.20, "sine", 0.015, 67),
            }
            for name, sound in generated.items():
                self.sfx[name] = sound
                sound.set_volume(self.sfx_volume * self.sfx_gains[name])
        except Exception as exc:
            print(f"OXYGEN generated SFX unavailable: {exc}", file=sys.stderr)

    def apply_music_volume(self) -> None:
        if self.music_enabled:
            try:
                # The campaign stream stays loaded underneath a boss theme.
                stream_volume = 0.0 if self.active_boss_music else self.music_track_volume
                pygame.mixer.music.set_volume(stream_volume * self.music_volume)
                if self.active_boss_music and self.boss_music_channel:
                    self.boss_music_channel.set_volume(self.music_volume * 0.72)
            except Exception:
                pass

    def set_audio_slider(self, name: str, value: float, save: bool = False) -> None:
        value = max(0.0, min(1.0, float(value)))
        if name == "music":
            self.music_volume = value
            self.save_data["music_volume"] = value
            self.apply_music_volume()
        elif name == "sfx":
            self.sfx_volume = value
            self.save_data["sfx_volume"] = value
            for name, sound in self.sfx.items():
                sound.set_volume(value * self.sfx_gains.get(name, 1.0))
        if save:
            self.save_progress()

    def audio_slider_value_from_x(self, x: int) -> float:
        left, right = 430, 720
        return max(0.0, min(1.0, (x - left) / (right - left)))

    def play_sfx(self, name: str) -> None:
        if not self.music_enabled:
            return
        sound = self.sfx.get(name)
        if sound is None:
            return
        try:
            if name == "flight" and self.flight_sfx_channel is not None:
                if not self.flight_sfx_channel.get_busy():
                    self.flight_sfx_channel.play(sound, loops=-1)
                return
            sound.play()
        except pygame.error:
            pass

    def stop_flight_sfx(self) -> None:
        try:
            if self.flight_sfx_channel is not None and self.flight_sfx_channel.get_busy():
                self.flight_sfx_channel.fadeout(100)
        except pygame.error:
            pass

    def set_music_scene(self, scene: str) -> None:
        """Switch music without asynchronous fades that can stall browser audio."""
        if not self.music_enabled or scene == self.music_scene:
            return
        tracks = {
            "menu": "main_menu.ogg",
            "hub": "safehouse.ogg",
            "arena": "salvage_arena.ogg",
            "campaign_01_05": "sectors_01_05.ogg",
            "boss_05": "boss_sector_05.ogg",
            "campaign_06_09": "sectors_06_09.ogg",
            "boss_10": "boss_sector_10.ogg",
            "ending": "main_menu.ogg",
            "signal_167": "167_signal.ogg",
        }
        filename = tracks.get(scene)
        if not filename:
            return
        path = self.music_root / filename
        if scene == "signal_167" and not path.exists():
            # Until the user's custom track is uploaded, keep the normal refuge ambience.
            scene = "hub"
            filename = tracks[scene]
            path = self.music_root / filename
        volume = 0.20 if scene == "signal_167" else (0.22 if scene.startswith("boss") else 0.17)
        self.music_track_volume = volume
        self.music_scene = scene
        self.music_transition_target = None
        self.music_transition_timer = 0.0
        try:
            # Stop first, then replace the stream. Browser/Pygbag audio backends
            # can become unresponsive when fadeout and a delayed load overlap.
            pygame.mixer.music.stop()
            if not path.exists():
                return
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(volume * self.music_volume)
            pygame.mixer.music.play(-1)
        except Exception as exc:
            # Audio is optional: a decoder/backend error must never stop gameplay
            # or prevent keyboard events from being processed.
            print(f"OXYGEN music switch failed ({scene}): {exc}", file=sys.stderr)
            self.music_enabled = False
            self.music_transition_target = None

    def update_music_scene(self, dt: float = 0.0) -> None:
        # Keep scene selection in the game loop, but never decode a large OGG
        # at the boss trigger. Boss themes are preloaded as Sound objects.
        if self.mode in ("playing", "paused"):
            if self.is_arena_mode:
                scene = "arena"
            else:
                scene = "campaign_01_05" if self.level_index <= 4 else "campaign_06_09"
        elif self.mode in ("safehouse", "safehouse_dialog", "ability_mods",
                           "cassette_deck", "secret_room_167"):
            scene = ("signal_167" if self.save_data.get("postgame_event_seen", False)
                     else "hub")
        elif self.mode == "victory":
            scene = "ending"
        else:
            scene = "menu"
        self.set_music_scene(scene)

        boss = getattr(self.level, "boss", None) if self.mode in ("playing", "paused") and not self.is_arena_mode else None
        boss_key = None
        if boss is not None and boss.active and not boss.defeated:
            boss_key = "boss_05" if self.level_index <= 4 else "boss_10"

        if boss_key != self.active_boss_music:
            if self.boss_music_channel:
                try:
                    self.boss_music_channel.stop()
                except Exception:
                    pass
            self.active_boss_music = boss_key
            if boss_key and boss_key in self.boss_music and self.boss_music_channel:
                try:
                    self.boss_music_channel.play(self.boss_music[boss_key], loops=-1)
                    self.boss_music_channel.set_volume(self.music_volume * 0.72)
                except Exception as exc:
                    print(f"OXYGEN boss music playback failed ({boss_key}): {exc}", file=sys.stderr)
                    self.active_boss_music = None
            self.apply_music_volume()

        # ESC pauses both the game and its currently active boss theme.
        if self.boss_music_channel and self.active_boss_music:
            try:
                if self.mode == "paused":
                    self.boss_music_channel.pause()
                else:
                    self.boss_music_channel.unpause()
            except Exception:
                pass

    def raw_quest_metric(self, metric: str) -> int:
        if metric == "secrets":
            return len(self.save_data.get("found_secrets", []))
        return int(self.save_data.get("stats", {}).get(metric, 0))

    def quest_progress(self, quest: dict) -> int:
        quest_id = quest["id"]
        if quest_id not in self.save_data.get("quest_active", []):
            return quest["target"] if quest_id in self.save_data.get("quest_claimed", []) else 0
        baseline = int(self.save_data.get("quest_baselines", {}).get(quest_id, 0))
        return min(quest["target"], max(0, self.raw_quest_metric(quest["metric"]) - baseline))

    def enter_safehouse(self) -> None:
        self.coin_multiplier_timer = 0.0
        self.mode = "safehouse"
        self.safehouse_dialog_npc = None
        self.filter_dialog_open = False
        # The refuge uses the currently selected operative too. Rebuild the
        # player if the menu's saved selection differs from the temporary menu actor.
        if self.player.character_id != self.character_id:
            self.player = Player((170, 457), self.character_id,
                                 speed_level=self.save_data["speed_level"])
        self.apply_player_skills()
        self.player.x = 170.0
        self.player.y = 457.0
        self.player.vx = 0.0
        self.player.vy = 0.0
        self.player.on_ground = True
        self.player.flight_requested = False
        self.player.hp = self.player.max_hp
        self.player.facing = 1
        self.safehouse_interaction_hint = ""
        self.projectiles.clear()
        self.stop_flight_sfx()
        if (len(set(self.save_data.get("completed_levels", []))) >= len(LEVELS)
                and not self.save_data.get("postgame_event_seen", False)):
            self.save_data["postgame_event_pending"] = True
            self.save_progress()
        if (self.save_data.get("postgame_event_pending", False)
                and not self.save_data.get("postgame_event_seen", False)):
            self.begin_167_signal_event()

    def begin_167_signal_event(self) -> None:
        self.safehouse_event_active = True
        self.safehouse_event_elapsed = 0.0
        self.cassette_playing = False
        self.mode = "safehouse"

    def collected_cassette_ids(self) -> list[str]:
        found = self.save_data.get("collected_cassettes", [])
        return sorted(
            {str(value) for value in found
             if str(value).isdigit() and 0 <= int(value) < len(LEVELS)},
            key=lambda value: int(value))

    def toggle_cassette_playback(self) -> None:
        tapes = self.collected_cassette_ids()
        if not tapes:
            self.cassette_playing = False
            return
        self.cassette_selection = max(0, min(self.cassette_selection, len(tapes) - 1))
        # The deck transport can be tested now; no audio has been linked yet.
        self.cassette_playing = not self.cassette_playing

    def nearby_safehouse_object(self) -> tuple[str, int] | None:
        px = self.player.x + self.player.w / 2
        # The purifier is reached from the elevated maintenance catwalk.
        if abs(px - self.safehouse_filter_x) < 100 and self.player.y < 205:
            return ("filter", 0)
        if abs(px - self.hub_gate_x) < 68:
            return ("gate", 0)
        if abs(px - 650) < 76 and self.player.y > 390:
            return ("cassette_deck", 0)
        if abs(px - 861) < 78 and self.player.y > 390:
            return ("radio", 0)
        if abs(px - 410) < 62 and self.player.y > 390:
            return ("secret_167" if self.save_data.get("secret_167_unlocked", False)
                    else "locked_167", 0)
        for i, npc_x in enumerate(self.hub_npc_positions):
            if i == 3 and len(set(self.save_data.get("completed_levels", []))) < 3:
                continue
            if abs(px - npc_x) < 72 and self.player.y > 400:
                return ("npc", i)
        if abs(px - self.hub_armory_x) < 76 and self.player.y > 390:
            return ("armory", 0)
        return None

    def service_oxygen_filter(self) -> None:
        if self.save_data.get("filter_boost", False):
            self.menu_notice = "OXYGEN BUFFER READY // NEXT DEPLOYMENT +1 HP"
        elif int(self.save_data.get("filter_charge", 0)) >= 60:
            self.save_data["filter_charge"] -= 60
            self.save_data["filter_boost"] = True
            self.menu_notice = "OXYGEN BUFFER CHARGED // NEXT DEPLOYMENT +1 HP"
            self.save_progress()
        elif self.total_coins >= 8:
            self.total_coins -= 8
            self.save_data["filter_charge"] = min(100, int(self.save_data.get("filter_charge", 0)) + 25)
            charge = self.save_data["filter_charge"]
            self.menu_notice = f"FILTER SERVICED // {charge}% CHARGE // 8 COINS"
            self.save_progress()
        else:
            self.menu_notice = "FILTER NEEDS 8 COINS FOR MAINTENANCE"
        self.menu_notice_timer = 3.0

    def interact_safehouse(self) -> None:
        target = self.nearby_safehouse_object()
        if target is None:
            self.menu_notice = "MOVE CLOSER TO A CREW MEMBER OR THE MOD BAY"
            self.menu_notice_timer = 1.8
            return
        kind, index = target
        if kind == "gate":
            self.deploy_from_safehouse()
        elif kind == "filter":
            self.service_oxygen_filter()
        elif kind == "radio":
            transmissions = [
                "RADIO // ...IF ANYONE HEARS THIS, DO NOT ANSWER THE SECOND SIGNAL.",
                "UNKNOWN VOICE // THE SHELTER IS NOT THE ONLY PLACE STILL LIT.",
                "STATIC // 167 IS NOT A FREQUENCY. REPEAT: NOT A FREQUENCY.",
                "DISTANT TRANSMISSION // WE COUNTED SIX. THERE WERE SEVEN.",
                "RADIO // CARRIER LOST. SOMETHING IS LISTENING."
            ]
            index = int(self.save_data.get("radio_log_index", 0)) % len(transmissions)
            self.menu_notice = transmissions[index]
            self.save_data["radio_log_index"] = index + 1
            self.save_progress()
            self.menu_notice_timer = 5.0
        elif kind == "npc":
            self.safehouse_dialog_npc = index
            self.safehouse_dialog_selection = 0
            self.mode = "safehouse_dialog"
        elif kind == "armory":
            self.mods_character_index = self.character_index
            self.mods_selection = 0
            self.mods_return_mode = "safehouse"
            self.mode = "ability_mods"
        elif kind == "cassette_deck":
            self.cassette_selection = 0
            self.cassette_playing = False
            self.mode = "cassette_deck"
        elif kind == "secret_167":
            self.secret_167_page = 0
            self.mode = "secret_room_167"
        elif kind == "locked_167":
            self.menu_notice = "167 ARCHIVE // SIGNAL REQUIRED"
            self.menu_notice_timer = 2.4

    def safehouse_dialog_action(self) -> None:
        if self.safehouse_dialog_npc is None:
            self.mode = "safehouse"
            return
        quest = QUESTS[self.safehouse_dialog_npc]
        quest_id = quest["id"]
        active = self.save_data.setdefault("quest_active", [])
        claimed = self.save_data.setdefault("quest_claimed", [])
        if self.safehouse_dialog_selection == 1:
            self.mode = "safehouse"
            self.safehouse_dialog_npc = None
            return
        if quest_id in claimed:
            self.menu_notice = "CONTRACT ALREADY COMPLETED"
        elif quest_id not in active:
            active.append(quest_id)
            self.save_data.setdefault("quest_baselines", {})[quest_id] = self.raw_quest_metric(quest["metric"])
            self.menu_notice = f"CONTRACT ACCEPTED // {quest['title']}"
            self.save_progress()
        elif self.quest_progress(quest) >= quest["target"]:
            self.grant_coins(quest["reward"], reason="CONTRACT REWARD")
            claimed.append(quest_id)
            active.remove(quest_id)
            if quest_id == "restore_lights":
                self.save_data["safehouse_lighting_upgraded"] = True
            self.save_data.setdefault("stats", {})["contracts_completed"] = len(claimed)
            self.save_progress()
            self.unlock_achievement("contract_runner")
            self.menu_notice = f"CONTRACT COMPLETE // +{quest['reward']} COINS"
        else:
            self.menu_notice = "CONTRACT ACTIVE // KEEP GOING"
        self.menu_notice_timer = 2.4
        self.mode = "safehouse"
        self.safehouse_dialog_npc = None

    def update_safehouse(self, dt: float) -> None:
        if self.safehouse_event_active:
            self.safehouse_event_elapsed += dt
            if self.safehouse_event_elapsed >= 8.0:
                self.safehouse_event_active = False
                self.save_data["postgame_event_pending"] = False
                self.save_data["postgame_event_seen"] = True
                self.save_data["secret_167_unlocked"] = True
                self.save_progress()
                self.menu_notice = "167 SIGNAL // ARCHIVE ACCESS GRANTED"
                self.menu_notice_timer = 4.0
            return
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        if self.player.character_id in ("shooter", "flyer") and (
                keys[pygame.K_j] or keys[pygame.K_c] or self.mobile_fire
                or (mouse_buttons and mouse_buttons[0])):
            self.fire_player_shot()
        previous_jump_count = self.player.jump_count
        previous_on_ground = self.player.on_ground
        self.footstep_timer = max(0.0, self.footstep_timer - dt)
        self.player.update(dt, keys, self.safehouse_world, self.particles)
        if self.player.jump_count > previous_jump_count:
            self.play_sfx("jump")
        if not previous_on_ground and self.player.on_ground:
            self.play_sfx("landing")
        if (self.player.on_ground and abs(self.player.vx) > 115
                and self.player.dash_time <= 0 and self.footstep_timer <= 0):
            self.play_sfx("footstep")
            self.footstep_timer = 0.34
        if (self.player.character_id == "jumper" and previous_jump_count >= 1
                and self.player.jump_count > previous_jump_count):
            self.play_sfx("double_jump")
        self.player.x = max(45.0, min(WIDTH - 45.0 - self.player.w, self.player.x))
        for shot in self.projectiles:
            shot.update(dt)
        self.projectiles = [shot for shot in self.projectiles
                            if shot.alive and -40 < shot.x < WIDTH + 40]
        self.particles = [particle for particle in self.particles if particle.update(dt)]
        if self.player.is_flying:
            self.play_sfx("flight")
        else:
            self.stop_flight_sfx()
        target = self.nearby_safehouse_object()
        if target and target[0] == "filter":
            self.safehouse_interaction_hint = "E  //  SERVICE OXYGEN FILTER"
        elif target and target[0] == "gate":
            self.safehouse_interaction_hint = "E  //  CHOOSE RUNNER AND DEPLOY"
        elif target and target[0] == "radio":
            self.safehouse_interaction_hint = "E  //  LISTEN TO RADIO"
        elif target and target[0] == "npc":
            self.safehouse_interaction_hint = "E  //  TALK TO " + QUESTS[target[1]]["npc"]
        elif target and target[0] == "armory":
            self.safehouse_interaction_hint = "E  //  OPEN ABILITY MODULES"
        elif target and target[0] == "cassette_deck":
            self.safehouse_interaction_hint = "E  //  OPEN EXP TAPE DECK"
        elif target and target[0] == "secret_167":
            self.safehouse_interaction_hint = "E  //  ENTER ROOM 167"
        elif target and target[0] == "locked_167":
            self.safehouse_interaction_hint = "167 // SIGNAL LOCKED"
        else:
            self.safehouse_interaction_hint = ""

    def apply_player_mods(self) -> None:
        owned = set(self.save_data.get("character_mods", {}).get(self.player.character_id, []))
        if self.player.character_id == "runner":
            if "long_dash" in owned:
                self.player.dash_duration = 0.22
                self.player.dash_cooldown_base = 0.58
        elif self.player.character_id == "jumper":
            self.player.extra_jumps = 1 if "third_step" in owned else 0
        elif self.player.character_id == "flyer":
            if "ion_wings" in owned:
                self.player.flight_fuel_max = 2.25
                self.player.flight_fuel = self.player.flight_fuel_max

    def purchase_ability_mod(self, mod_index: int) -> None:
        cid = CHARACTER_IDS[self.mods_character_index]
        mods = ABILITY_MODS[cid]
        if not 0 <= mod_index < len(mods):
            return
        mod_id, title, cost, _desc = mods[mod_index]
        owned = self.save_data.setdefault("character_mods", {}).setdefault(cid, [])
        if mod_id in owned:
            self.menu_notice = f"{title} // ALREADY INSTALLED"
        elif cid == "flyer" and not self.character_is_unlocked("flyer"):
            self.menu_notice = "AERIS LOCKED // DEFEAT THE CORE FIRST"
        elif self.total_coins < cost:
            self.menu_notice = "NOT ENOUGH COINS"
        else:
            self.total_coins -= cost
            owned.append(mod_id)
            self.menu_notice = f"{title} // INSTALLED"
            self.save_progress()
            if self.player.character_id == cid:
                self.apply_player_mods()
        self.menu_notice_timer = 2.8

    def calculate_level_rating(self) -> dict:
        elapsed = max(0.01, self.level_elapsed)
        target = 72.0 + self.level_index * 5.0
        has_secret_route = bool(self.level.secret_rooms)
        secret_condition = self.level_secrets > 0 or not has_secret_route
        if self.level_deaths == 0 and elapsed <= target and secret_condition:
            grade = "S"
        elif self.level_deaths <= 1 and elapsed <= target * 1.55:
            grade = "A"
        elif self.level_deaths <= 3:
            grade = "B"
        else:
            grade = "C"
        return {"grade": grade, "time": round(elapsed, 2), "deaths": self.level_deaths,
                "coins": self.level_coins, "secrets": self.level_secrets,
                "score": int(self.score)}

    def continue_from_level_result(self) -> None:
        if self.pending_next_level is not None:
            # This is the one intentional path that bypasses character selection:
            # the player is continuing the same uninterrupted campaign run.
            next_level = self.pending_next_level
            self.pending_next_level = None
            self.load_level(next_level)
        elif self.save_data.get("postgame_event_pending", False):
            self.enter_safehouse()
        else:
            self.mode = "menu"

    def deploy_from_safehouse(self) -> None:
        target = self.pending_next_level
        if target is None:
            target = int(self.save_data.get("last_level", 0))
        self.pending_next_level = None
        self.pending_start_level = max(0, min(len(LEVELS) - 1, int(target)))
        self.character_return_mode = "safehouse"
        self.personnel_open = False
        self.character_select_selection = self.character_index
        self.mode = "character_select"

    @property
    def character_id(self) -> str:
        return CHARACTER_IDS[self.character_index]

    def create_display(self) -> pygame.Surface:
        """Create a desktop window or the fixed browser canvas."""
        if sys.platform == "emscripten":
            return pygame.display.set_mode((WIDTH, HEIGHT))
        return pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)

    def toggle_fullscreen(self) -> None:
        if sys.platform == "emscripten":
            return  # Browser fullscreen is controlled by the hosting page/user gesture.
        if not self.fullscreen:
            self.windowed_size = self.display.get_size()
            try:
                sizes = pygame.display.get_desktop_sizes()
                desktop_size = sizes[0] if sizes else (WIDTH, HEIGHT)
            except (AttributeError, pygame.error):
                info = pygame.display.Info()
                desktop_size = (info.current_w or WIDTH, info.current_h or HEIGHT)
            self.display = pygame.display.set_mode(desktop_size, pygame.FULLSCREEN)
            self.fullscreen = True
        else:
            self.display = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            self.fullscreen = False
        # A display-mode change can leave a stale mouse position; the viewport
        # is recalculated on every presentation and mouse click.
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self._scaled_frame = None
        self._scaled_size = None

    def logical_mouse_pos(self, position: tuple[int, int]) -> tuple[int, int]:
        dw, dh = self.display.get_size()
        dw, dh = max(1, dw), max(1, dh)
        scale = min(dw / WIDTH, dh / HEIGHT)
        view_w, view_h = int(WIDTH * scale), int(HEIGHT * scale)
        ox, oy = (dw - view_w) // 2, (dh - view_h) // 2
        px, py = position
        if px < ox or py < oy or px >= ox + view_w or py >= oy + view_h:
            return -10000, -10000
        return int((px - ox) / scale), int((py - oy) / scale)

    def present_display(self) -> None:
        dw, dh = self.display.get_size()
        dw, dh = max(1, dw), max(1, dh)
        scale = min(dw / WIDTH, dh / HEIGHT)
        view_w, view_h = max(1, int(WIDTH * scale)), max(1, int(HEIGHT * scale))
        ox, oy = (dw - view_w) // 2, (dh - view_h) // 2
        self.viewport = pygame.Rect(ox, oy, view_w, view_h)
        self.display.fill((0, 0, 0))
        if (view_w, view_h) == (WIDTH, HEIGHT):
            self.display.blit(self.screen, (ox, oy))
        else:
            # Reuse the destination buffer and use pygame's fast C scaler.
            # The previous version accidentally cached the *image* itself,
            # which both cost a lot and would freeze the displayed frame.
            target_size = (view_w, view_h)
            if self._scaled_frame is None or self._scaled_size != target_size:
                self._scaled_frame = pygame.Surface(target_size).convert()
                self._scaled_size = target_size
            pygame.transform.scale(self.screen, target_size, self._scaled_frame)
            self.display.blit(self._scaled_frame, (ox, oy))
        pygame.display.flip()

    def start_game(self) -> None:
        self.pending_next_level = None
        self.coin_multiplier_timer = 0.0
        self.score = 0
        self.notice = ""
        self.notice_timer = 0.0
        self.shake = 0.0
        self.pending_start_level = int(self.save_data.get("last_level", 0))
        self.character_return_mode = "menu"
        self.personnel_open = False
        self.character_select_selection = self.character_index
        self.mode = "character_select"

    def start_selected_level(self, index: int) -> None:
        if not self.level_is_unlocked(index):
            self.menu_notice = "SECTOR LOCKED // COMPLETE THE PREVIOUS SECTOR"
            self.menu_notice_timer = 2.0
            return
        self.coin_multiplier_timer = 0.0
        self.pending_start_level = int(index)
        self.character_return_mode = "level_select"
        self.personnel_open = False
        self.character_select_selection = self.character_index
        self.mode = "character_select"

    def start_arena_mode(self) -> None:
        self.coin_multiplier_timer = 0.0
        self.is_arena_mode = True
        self.pending_next_level = None
        self.level_index = 0
        self.level = Level(0)
        self.level.width = WIDTH
        self.level.spawn = (70, 420)
        self.level.platforms = [Platform(0, 500, WIDTH, 120), Platform(180, 390, 170, 16),
                                Platform(430, 325, 150, 16), Platform(720, 385, 160, 16)]
        self.level.moving_platforms = []
        self.level.solids = [p.rect for p in self.level.platforms]
        self.level.coins = []
        self.level.drones = []
        self.level.seekers = []
        self.level.spiders = []
        self.level.turrets = []
        self.level.enemy_shots = []
        self.level.spikes = []
        self.level.checkpoints = []
        self.level.secret_rooms = []
        self.level.notes = []
        self.level.boss = None
        self.level.exit_rect = pygame.Rect(-500, -500, 1, 1)
        self.player = Player(self.level.spawn, self.character_id,
                             speed_level=self.save_data["speed_level"])
        self.apply_player_skills()
        self.camera_x = 0.0
        self.score = 0
        self.level_elapsed = 0.0
        self.level_deaths = 0
        self.level_coins = 0
        self.arena_wave = 1
        self.arena_spawned = 0
        self.arena_spawn_target = 0
        self.arena_spawn_remaining = 0
        self.arena_spawn_timer = 0.0
        self.arena_boss_spawned = False
        self.arena_bosses_defeated = 0
        self.projectiles.clear()
        self.particles.clear()
        self.begin_arena_wave()
        self.mode = "playing"
        self.notice = "SALVAGE ARENA // SURVIVE THE WAVES"
        self.notice_timer = 2.8

    def begin_arena_wave(self) -> None:
        self.arena_spawn_target = min(4 + self.arena_wave, 24)
        self.arena_spawn_remaining = self.arena_spawn_target
        self.arena_spawned = 0
        self.arena_spawn_timer = 0.35
        self.arena_boss_spawned = False
        self.level.boss = None

    def spawn_arena_enemy(self) -> None:
        wave = self.arena_wave
        x = random.randint(100, WIDTH - 100)
        kind_pool = ["drone"] * 4
        if wave >= 2:
            kind_pool += ["seeker"]
        if wave >= 3:
            kind_pool += ["spider"]
        if wave >= 4:
            kind_pool += ["turret"]
        kind = random.choice(kind_pool)
        if kind == "drone":
            enemy = Drone(x, 435, max(40, x - random.randint(75, 130)),
                          min(WIDTH - 40, x + random.randint(75, 130)),
                          speed=95 + wave * 7, hp=3)
            self.level.drones.append(enemy)
        elif kind == "seeker":
            self.level.seekers.append(Seeker(x, random.randint(210, 350),
                                             max(40, x - 130), min(WIDTH - 40, x + 130),
                                             speed=105 + wave * 7, hp=3 + wave // 4))
        elif kind == "spider":
            self.level.spiders.append(Spider(x, 310, 160, 435,
                                             speed=80 + wave * 5, hp=6))
        else:
            self.level.turrets.append(Turret(x, 460, cooldown=1.2, hp=6))
        self.arena_spawn_remaining -= 1
        self.arena_spawned += 1

    def update_arena_progression(self, dt: float) -> None:
        if not self.is_arena_mode or self.mode != "playing":
            return
        if self.level.boss is not None:
            return
        if self.arena_spawn_remaining > 0:
            self.arena_spawn_timer -= dt
            if self.arena_spawn_timer <= 0:
                self.spawn_arena_enemy()
                self.arena_spawn_timer = max(0.25, 0.95 - self.arena_wave * 0.045)
            return
        alive = any(enemy.alive for group in (self.level.drones, self.level.seekers,
                                               self.level.spiders, self.level.turrets)
                    for enemy in group)
        if alive:
            return
        if self.arena_wave % 5 == 0 and not self.arena_boss_spawned:
            self.arena_boss_spawned = True
            boss = Boss(variant="arena", x=820, base_y=245, left=660, right=950,
                        hp=12 + self.arena_bosses_defeated * 3, name="SCRAP TITAN")
            boss.active = True
            boss.attack_timer = 1.0
            self.level.boss = boss
            self.notice = "SCRAP TITAN // BOSS INCOMING"
            self.notice_timer = 2.6
            self.shake = 0.3
        else:
            self.arena_wave += 1
            self.save_data["arena_best_wave"] = max(int(self.save_data.get("arena_best_wave", 0)), self.arena_wave - 1)
            self.check_achievements()
            self.begin_arena_wave()

    def handle_boss_defeated(self, boss: Boss) -> None:
        if self.is_arena_mode and boss.variant == "arena":
            self.arena_bosses_defeated += 1
            self.save_data.setdefault("stats", {})["arena_bosses"] = self.arena_bosses_defeated
            self.grant_coins(10, reason="SCRAP TITAN DESTROYED")
            self.level.boss = None
            self.arena_wave += 1
            self.save_data["arena_best_wave"] = max(int(self.save_data.get("arena_best_wave", 0)), self.arena_wave - 1)
            self.begin_arena_wave()
            self.notice = "SCRAP TITAN DESTROYED // +10 COINS // NEXT WAVE"
            self.notice_timer = 3.0
            return
        if boss.variant == "warden":
            self.save_data["warden_cleared"] = True
            self.save_progress()
            self.unlock_achievement("warden_down")
            self.notice = "OXYGEN WARDEN DESTROYED // EXIT OPEN"
        else:
            self.notice = "THE CORE DESTROYED // EXIT OPEN"
        self.score += 2500
        self.notice_timer = 3.0
        self.shake = 0.65

    def start_boss_arena(self) -> None:
        """Move story bosses to a contained combat deck with safe side walls."""
        boss = self.level.boss
        if boss is None or self.is_arena_mode or self.boss_arena_active:
            return
        center_x = int(boss.x)
        arena_width = 860
        arena_left = max(40, min(self.level.width - arena_width - 40, center_x - arena_width // 2))
        arena_right = arena_left + arena_width
        floor_y = 475
        # Remove ordinary hostiles and their bullets: this is a dedicated boss encounter.
        self.level.drones.clear()
        self.level.seekers.clear()
        self.level.spiders.clear()
        self.level.turrets.clear()
        self.level.enemy_shots.clear()
        self.projectiles.clear()
        self.level.spikes = [spike for spike in self.level.spikes
                             if spike.right < arena_left or spike.left > arena_right]
        arena_parts = [
            Platform(arena_left, floor_y, arena_width, 130),
            Platform(arena_left, 245, 22, floor_y - 245),
            Platform(arena_right - 22, 245, 22, floor_y - 245),
        ]
        self.level.platforms.extend(arena_parts)
        self.level.solids = [platform.rect for platform in self.level.platforms]
        boss.left = arena_left + 115
        boss.right = arena_left + arena_width - 115
        boss.x = max(boss.left, min(boss.right, center_x))
        boss.base_y = 315 if boss.variant == "core" else 290
        boss.y = boss.base_y
        self.boss_arena_bounds = (arena_left, arena_right, floor_y)
        self.boss_arena_active = True
        self.player.x = float(arena_left + 78)
        self.player.y = float(floor_y - self.player.h)
        self.player.vx = self.player.vy = 0.0
        self.player.on_ground = True
        self.player.invuln = max(self.player.invuln, 1.0)
        self.level.exit_rect.x = arena_right - 92
        self.camera_x = max(0.0, min(arena_left - 90, self.level.width - WIDTH))
        self.player.x = max(arena_left + 34, min(self.player.x, arena_right - self.player.w - 34))
        self.make_burst(self.player.x + 15, self.player.y + 18, THEMES[self.level_index]["accent"], 24)

    def load_level(self, index: int) -> None:
        self.is_arena_mode = False
        self.boss_arena_active = False
        self.boss_arena_bounds = None
        # Keep an active x2 pickup while flowing directly into the next sector.
        self.healing_crystal = None
        self.boss_fight_elapsed = 0.0
        self.boss_crystal_delay = random.uniform(25.0, 50.0)
        # Keep the 30-minute cooldown across sectors so it measures the whole campaign.
        self.level_index = index
        self.save_data["last_level"] = int(index)
        self.save_progress()
        self.level = Level(index)
        if self.level.coin_doubler is not None and str(index) in self.save_data.get("collected_doublers", []):
            self.level.coin_doubler.collected = True
        for coin_index, coin in enumerate(self.level.coins):
            coin.collected = f"{index}:{coin_index}" in self.collected_coin_keys
        found_cassettes = self.collected_cassette_ids()
        for cassette in self.level.cassettes:
            cassette["collected"] = cassette["id"] in found_cassettes
        self.player = Player(self.level.spawn, self.character_id,
                             speed_level=self.save_data["speed_level"])
        self.apply_player_skills()
        self.run_filter_hp_bonus = bool(self.save_data.get("filter_boost", False))
        if self.run_filter_hp_bonus:
            self.player.max_hp = min(5, self.player.max_hp + 1)
            self.player.hp = self.player.max_hp
            self.save_data["filter_boost"] = False
            self.save_progress()
        self.last_wall_jump_count = 0
        for i, secret in enumerate(self.level.secret_rooms):
            secret["found"] = f"{index}:{i}" in self.save_data["found_secrets"]
        self.camera_x = 0.0
        self.particles.clear()
        self.projectiles.clear()
        self.level_banner = 2.8
        self.level_elapsed = 0.0
        self.level_deaths = 0
        self.level_coins = 0
        self.level_secrets = sum(1 for secret in self.level.secret_rooms if secret["found"])
        self.mode = "playing"

    def restart_level(self) -> None:
        if self.is_arena_mode:
            self.start_arena_mode()
            return
        self.healing_crystal = None
        self.boss_arena_active = False
        self.boss_arena_bounds = None
        self.coin_multiplier_timer = 0.0
        self.boss_fight_elapsed = 0.0
        self.boss_crystal_delay = random.uniform(25.0, 50.0)
        self.level = Level(self.level_index)
        if self.level.coin_doubler is not None and str(self.level_index) in self.save_data.get("collected_doublers", []):
            self.level.coin_doubler.collected = True
        for coin_index, coin in enumerate(self.level.coins):
            coin.collected = f"{self.level_index}:{coin_index}" in self.collected_coin_keys
        self.player = Player(self.level.spawn, self.character_id,
                             speed_level=self.save_data["speed_level"])
        self.apply_player_skills()
        if getattr(self, "run_filter_hp_bonus", False):
            self.player.max_hp = min(5, self.player.max_hp + 1)
        # A restart is a fresh sector attempt: restore all lives, including
        # SIGNAL SHIELD and the current deployment's oxygen-buffer bonus.
        self.player.hp = self.player.max_hp
        for i, secret in enumerate(self.level.secret_rooms):
            secret["found"] = f"{self.level_index}:{i}" in self.save_data["found_secrets"]
        self.last_wall_jump_count = 0
        self.camera_x = 0.0
        self.particles.clear()
        self.projectiles.clear()
        self.level_banner = 1.4
        self.level_elapsed = 0.0
        self.level_deaths = 0
        self.level_coins = 0
        self.level_secrets = sum(1 for secret in self.level.secret_rooms if secret["found"])
        self.mode = "playing"

    def apply_player_skills(self) -> None:
        skills = self.save_data.get("skills", {})
        if skills.get("wall_mastery"):
            self.player.wall_mastery = True
        if skills.get("air_overdrive"):
            self.player.air_overdrive = True
        if skills.get("signal_shield"):
            self.player.max_hp = 4
            self.player.hp = 4
        self.apply_player_mods()

    def purchase_skill(self, skill_index: int) -> None:
        if not 0 <= skill_index < len(SKILL_NODES):
            return
        skill_id, title, cost, _desc = SKILL_NODES[skill_index]
        if self.save_data["skills"].get(skill_id):
            self.menu_notice = f"{title} // ALREADY UNLOCKED"
        elif self.total_coins < cost:
            self.menu_notice = "NOT ENOUGH COINS"
        else:
            self.total_coins -= cost
            self.save_data["skills"][skill_id] = True
            self.menu_notice = f"{title} // UNLOCKED"
            self.save_progress()
            if self.mode == "playing":
                self.apply_player_skills()
        self.menu_notice_timer = 2.2

    def grant_coins(self, amount: int, count_as_collected: bool = True, reason: str = "") -> None:
        amount = max(0, int(amount))
        if amount <= 0:
            return
        applied_amount = amount * (2 if self.coin_multiplier_timer > 0 else 1)
        self.total_coins += applied_amount
        if count_as_collected:
            self.save_data.setdefault("stats", {})["coins_collected"] = (
                int(self.save_data["stats"].get("coins_collected", 0)) + applied_amount)
        self.save_progress()
        if reason:
            self.notice = f"{reason} // +{applied_amount} COINS"
            self.notice_timer = 2.0
        self.check_achievements()

    def register_enemy_kill(self, enemy_kind: str = "enemy") -> None:
        stats = self.save_data.setdefault("stats", {})
        stats["kills"] = int(stats.get("kills", 0)) + 1
        if self.is_arena_mode:
            reward = 1
        else:
            reward = {"shooter": 2, "flyer": 0}.get(self.player.character_id, 1)
        if reward:
            reward *= 2 if self.coin_multiplier_timer > 0 else 1
            self.total_coins += reward
            stats["coins_collected"] = int(stats.get("coins_collected", 0)) + reward
            self.notice = f"{enemy_kind.upper()} DESTROYED // +{reward} COINS"
            self.notice_timer = 1.35
        self.save_progress()
        self.check_achievements()

    def apply_pending_achievement_rewards(self) -> None:
        """Pay 5 coins once for each earned achievement, including old saves."""
        earned = set(self.save_data.get("achievements", []))
        paid = set(self.save_data.get("achievement_rewards", []))
        known = {item[0] for item in ACHIEVEMENTS}
        pending = earned.intersection(known) - paid
        if pending:
            self.total_coins += 5 * len(pending)
            self.save_data["achievement_rewards"] = sorted(paid.union(pending))
            self.save_progress()

    def unlock_achievement(self, achievement_id: str) -> None:
        unlocked = self.save_data["achievements"]
        if achievement_id not in unlocked:
            unlocked.append(achievement_id)
            paid = self.save_data.setdefault("achievement_rewards", [])
            if achievement_id not in paid:
                self.total_coins += 5
                paid.append(achievement_id)
            label = next((item[1] for item in ACHIEVEMENTS if item[0] == achievement_id), achievement_id)
            self.menu_notice = f"ACHIEVEMENT UNLOCKED // {label}"
            self.menu_notice_timer = 3.0
            self.notice = f"ACHIEVEMENT UNLOCKED // {label}"
            self.notice_timer = 3.0
            self.achievement_popup_title = label
            self.achievement_popup_timer = 4.2
            self.play_sfx("achievement")
            self.save_progress()

    def check_achievements(self) -> None:
        stats = self.save_data["stats"]
        conditions = {
            "first_blood": stats["kills"] >= 1,
            "coin_runner": stats["coins_collected"] >= 50,
            "hidden_paths": len(self.save_data.get("found_secrets", [])) >= 1,
            "wall_dancer": stats["wall_jumps"] >= 10,
            "machine_breaker": stats["kills"] >= 25,
            "core_down": bool(self.save_data.get("boss_cleared")),
            "signal_complete": stats["levels_completed"] >= 10,
            "contract_runner": len(self.save_data.get("quest_claimed", [])) >= 1,
            "arena_survivor": int(self.save_data.get("arena_best_wave", 0)) >= 5,
            "warden_down": bool(self.save_data.get("warden_cleared")),
            "perfect_signal": sum(1 for item in self.save_data.get("level_ratings", {}).values()
                                  if isinstance(item, dict) and item.get("grade") == "S") >= 5,
        }
        for achievement_id, condition in conditions.items():
            if condition:
                self.unlock_achievement(achievement_id)


    def complete_current_level(self) -> None:
        completed_key = str(self.level_index)
        if completed_key not in self.save_data["completed_levels"]:
            self.save_data["completed_levels"].append(completed_key)
        self.save_data["stats"]["levels_completed"] = len(self.save_data["completed_levels"])
        self.score += 500
        rating = self.calculate_level_rating()
        ratings = self.save_data.setdefault("level_ratings", {})
        previous = ratings.get(completed_key)
        grade_order = {"C": 1, "B": 2, "A": 3, "S": 4}
        if (not isinstance(previous, dict) or
                grade_order.get(rating["grade"], 0) > grade_order.get(previous.get("grade", "C"), 0) or
                (rating["grade"] == previous.get("grade") and rating["time"] < float(previous.get("time", 999999)))):
            ratings[completed_key] = rating
        self.last_rating = rating
        self.save_data["filter_charge"] = min(100, int(self.save_data.get("filter_charge", 0)) + 8)

        if self.level_index == 4:
            self.save_data["boss_cleared"] = True
            self.save_data["unlocked_flyer"] = True
            self.save_data["unlocked_levels"] = max(self.save_data["unlocked_levels"], 6)
            self.pending_next_level = 5
            self.notice = "AERIS UNLOCKED // THE VERTICAL SIGNAL BEGINS"
        elif self.level_index < len(LEVELS) - 1:
            self.save_data["unlocked_levels"] = max(
                self.save_data["unlocked_levels"], self.level_index + 2)
            self.pending_next_level = self.level_index + 1
            self.notice = f"SECTOR {self.level_index + 2:02d} UNLOCKED"
        else:
            self.pending_next_level = None
            self.save_data["warden_cleared"] = True
            self.notice = "OXYGEN // THE WARDEN IS SILENT"
            if (len(set(self.save_data.get("completed_levels", []))) >= len(LEVELS)
                    and not self.save_data.get("postgame_event_seen", False)):
                self.save_data["postgame_event_pending"] = True
        self.save_data["last_level"] = (self.pending_next_level if self.pending_next_level is not None
                                         else self.level_index)
        self.notice_timer = 3.2
        self.save_progress()
        self.check_achievements()
        self.mode = "level_result"

    def choose_character(self, index: int) -> None:
        index = max(0, min(len(CHARACTER_IDS) - 1, index))
        if not self.character_is_unlocked(CHARACTER_IDS[index]):
            self.menu_notice = "AERIS LOCKED // CLEAR ALL 5 SECTORS + THE CORE"
            self.menu_notice_timer = 2.6
            return
        self.character_index = index
        self.character_select_selection = self.character_index
        self.character_selected = True
        self.save_data["selected_character"] = self.character_id
        self.save_data["character_selected"] = True
        self.save_progress()
        if self.pending_start_level is not None:
            pending = self.pending_start_level
            self.pending_start_level = None
            self.pending_next_level = None
            self.score = 0
            self.notice = ""
            self.notice_timer = 0.0
            self.shake = 0.0
            self.load_level(pending)
            return
        self.mode = "personnel" if self.personnel_open else "menu"
        self.menu_selection = 0

    def fire_player_shot(self) -> None:
        character_id = self.player.character_id
        if self.mode not in ("playing", "safehouse") or character_id not in ("shooter", "flyer"):
            return
        if self.player.shoot_cooldown > 0:
            return
        direction = self.player.facing
        x = self.player.x + self.player.w / 2 + direction * 21
        y = self.player.y + 19
        is_flyer = character_id == "flyer"
        color = CHARACTERS[character_id]["accent"]
        # Cipher needs two shots for a 3-HP mob and 36 shots for the Core.
        # Aeris kills a normal mob in one shot and needs 18 shots for the Core.
        damage = 3 if is_flyer else 2
        cooldown = 0.5 if is_flyer else 1.3
        owned = set(self.save_data.get("character_mods", {}).get(character_id, []))
        if character_id == "shooter" and "quick_charge" in owned:
            cooldown = 0.95
        if character_id == "flyer" and "starfall" in owned:
            damage = 4
        self.projectiles.append(Projectile(
            x, y, direction * (880.0 if is_flyer else 760.0), 0.0,
            color, damage=damage, life=0.72 if is_flyer else 0.78, radius=7 if is_flyer else 6,
            pierce=1 if character_id == "shooter" and "piercing_rounds" in owned else 0))
        self.play_sfx("shoot")
        self.player.shoot_cooldown = cooldown
        self.make_burst(x, y, color, 4 if is_flyer else 3)

    def make_burst(self, x: float, y: float, color, amount: int = 12) -> None:
        for _ in range(amount):
            angle = random.random() * math.tau
            speed = random.uniform(55, 230)
            self.particles.append(Particle(x, y, color,
                                           math.cos(angle) * speed,
                                           math.sin(angle) * speed,
                                           random.uniform(0.25, 0.65),
                                           random.uniform(2, 4)))
        if len(self.particles) > 420:
            del self.particles[:len(self.particles) - 420]

    def damage_player(self) -> None:
        if self.player.invuln > 0:
            return
        self.player.hp -= 1
        self.play_sfx("death")
        self.level_deaths += 1
        self.save_data.setdefault("stats", {}).setdefault("deaths", 0)
        self.save_data["stats"]["deaths"] += 1
        self.save_data["last_run_deaths"] = int(self.save_data.get("last_run_deaths", 0)) + 1
        self.shake = 0.25
        self.make_burst(self.player.x + 15, self.player.y + 20, RED, 22)
        if self.player.hp <= 0:
            self.save_data["last_level"] = self.level_index
            self.save_data["filter_charge"] = max(0, int(self.save_data.get("filter_charge", 0)) - 10)
            self.pending_next_level = None
            self.save_progress()
            deaths = int(self.save_data.get("last_run_deaths", 0))
            self.notice = "SIGNAL LOST // CREW RECOVERED YOU"
            self.notice_timer = 3.0
            self.enter_safehouse()
            self.menu_notice = f"RECOVERY LOG // {deaths} FATAL SIGNALS RECORDED"
            self.menu_notice_timer = 3.2
        else:
            self.player.respawn(self.level.checkpoint_spawn, keep_hp=True)
            self.notice = "SIGNAL RESTORED"
            self.notice_timer = 1.3

    def process_dash_event(self) -> None:
        if self.mode == "playing":
            old_dash = self.player.dash_time
            self.player.begin_dash(self.particles)
            if self.player.dash_time > old_dash:
                self.play_sfx("dash")

    def toggle_language(self) -> None:
        self.language = "ru" if self.language == "en" else "en"
        self.save_data["language"] = self.language
        set_language(self.language)
        self.save_progress()

    def spawn_healing_crystal(self) -> None:
        """Place a rare boss-heal crystal on a safe, solid platform, never over a pit."""
        candidates = []
        for platform in self.level.platforms:
            if platform.h < 45 or platform.w < 90 or platform.y < 420:
                continue
            if self.boss_arena_bounds is not None:
                arena_left, arena_right, _floor_y = self.boss_arena_bounds
                if platform.x < arena_left or platform.x + platform.w > arena_right:
                    continue
            left = int(platform.x) + 34
            right = int(platform.x + platform.w) - 34
            if right <= left:
                continue
            for _ in range(5):
                x = random.randint(left, right)
                if any(spike.left - 40 <= x <= spike.right + 40 for spike in self.level.spikes):
                    continue
                candidates.append((x, platform.y - 24))
        if candidates:
            x, y = random.choice(candidates)
            self.healing_crystal = HealingCrystal(float(x), float(y), random.random() * math.tau)
            self.notice = "RARE HEALING CRYSTAL // +1 HP"
            self.notice_timer = 3.0

    def open_menu_item(self, index: int) -> None:
        self.menu_selection = max(0, min(7, int(index)))
        if index == 0:
            self.start_game()
        elif index == 1:
            self.enter_safehouse()
        elif index == 2:
            self.mode = "level_select"
            self.level_select_selection = 0
        elif index == 3:
            self.start_arena_mode()
        elif index == 4:
            self.mode = "personnel"
            self.personnel_selection = 0
            self.personnel_open = True
        elif index == 5:
            self.check_achievements()
            self.mode = "achievements"
            self.achievement_scroll = 0
        elif index == 6:
            self.mode = "rankings"
            self.ranking_scroll = 0
        elif index == 7:
            self.running = False

    def draw_personnel(self) -> None:
        self.draw_background(THEMES[1], 1)
        draw_text(self.screen, self.font_l, "PERSONNEL", WHITE, (WIDTH // 2, 83), center=True)
        draw_text(self.screen, self.font_xs, "RUNNERS // SKILLS // FIELD TRAINING",
                  CYAN, (WIDTH // 2, 125), center=True, shadow=False)
        choices = [
            ("CHARACTER ROSTER", "Choose one of the four playable runners."),
            ("SKILL TREE", "Permanent campaign-wide passive upgrades."),
            ("FIELD TRAINING", "Upgrade run speed and stomp strength."),
            ("BACK TO MENU", "Return to the main console."),
        ]
        for i, (title, desc) in enumerate(choices):
            rect = pygame.Rect(235, 165 + i * 91, 630, 72)
            selected = i == self.personnel_selection
            pygame.draw.rect(self.screen, (15, 38, 57) if selected else (8, 19, 35), rect, border_radius=10)
            pygame.draw.rect(self.screen, CYAN if selected else (52, 76, 98), rect, 2 if selected else 1, border_radius=10)
            draw_text(self.screen, self.font_m, title, WHITE, (rect.x + 22, rect.y + 11), shadow=False)
            draw_text(self.screen, self.font_xs, desc, MUTED, (rect.x + 22, rect.y + 46), shadow=False)
        draw_text(self.screen, self.font_xs, "UP / DOWN TO SELECT  //  ENTER TO OPEN  //  ESC BACK",
                  MUTED, (WIDTH // 2, 590), center=True, shadow=False)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE and not self.fullscreen:
            self.windowed_size = (max(640, event.w), max(360, event.h))
            self.display = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            self._scaled_frame = None
            self._scaled_size = None
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11 or (
                    event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
                self.toggle_fullscreen()
                return
            if event.key == pygame.K_F3:
                self.show_fps = not self.show_fps
                return

            if self.mode == "menu" and event.key == pygame.K_l:
                self.toggle_language()
                return

            if self.mode == "menu":
                # Two-column, four-row main menu.
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.menu_selection = max(0, self.menu_selection - 2)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.menu_selection = min(7, self.menu_selection + 2)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    if self.menu_selection % 2:
                        self.menu_selection -= 1
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    if self.menu_selection % 2 == 0 and self.menu_selection < 7:
                        self.menu_selection += 1
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.open_menu_item(self.menu_selection)
                elif event.key == pygame.K_ESCAPE:
                    self.running = False

            elif self.mode == "safehouse":
                if self.safehouse_event_active:
                    return
                if event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                    if self.player.character_id == "flyer" and not self.player.on_ground:
                        self.player.flight_requested = True
                    else:
                        self.player.jump_buffer = 0.13
                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_x):
                    old_dash = self.player.dash_time
                    self.player.begin_dash(self.particles)
                    if self.player.dash_time > old_dash:
                        self.play_sfx("dash")
                elif event.key in (pygame.K_j, pygame.K_c):
                    self.fire_player_shot()
                elif event.key in (pygame.K_e, pygame.K_RETURN):
                    self.interact_safehouse()
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "menu"
                    self.menu_selection = 0

            elif self.mode == "cassette_deck":
                tapes = self.collected_cassette_ids()
                if event.key in (pygame.K_LEFT, pygame.K_a) and tapes:
                    self.cassette_selection = (self.cassette_selection - 1) % len(tapes)
                    self.cassette_playing = False
                elif event.key in (pygame.K_RIGHT, pygame.K_d) and tapes:
                    self.cassette_selection = (self.cassette_selection + 1) % len(tapes)
                    self.cassette_playing = False
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.toggle_cassette_playback()
                elif event.key == pygame.K_ESCAPE:
                    self.cassette_playing = False
                    self.mode = "safehouse"

            elif self.mode == "secret_room_167":
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    self.secret_167_page = (self.secret_167_page - 1) % 3
                elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                    self.secret_167_page = (self.secret_167_page + 1) % 3
                elif event.key in (pygame.K_ESCAPE, pygame.K_e):
                    self.mode = "safehouse"

            elif self.mode == "safehouse_dialog":
                if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                    self.safehouse_dialog_selection = 1 - self.safehouse_dialog_selection
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.safehouse_dialog_action()
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "safehouse"
                    self.safehouse_dialog_npc = None

            elif self.mode == "personnel":
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.personnel_selection = (self.personnel_selection - 1) % 4
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.personnel_selection = (self.personnel_selection + 1) % 4
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.personnel_selection == 0:
                        self.character_select_selection = self.character_index
                        self.personnel_open = True
                        self.mode = "character_select"
                    elif self.personnel_selection == 1:
                        self.skill_selection = 0
                        self.mode = "skills"
                    elif self.personnel_selection == 2:
                        self.store_selection = 0
                        self.mode = "store"
                    else:
                        self.personnel_open = False
                        self.mode = "menu"
                elif event.key == pygame.K_ESCAPE:
                    self.personnel_open = False
                    self.mode = "menu"

            elif self.mode == "character_select":
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    self.character_select_selection = (self.character_select_selection - 1) % len(CHARACTER_IDS)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self.character_select_selection = (self.character_select_selection + 1) % len(CHARACTER_IDS)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.choose_character(self.character_select_selection)
                elif event.key == pygame.K_ESCAPE:
                    if self.personnel_open:
                        self.mode = "personnel"
                    elif self.pending_start_level is not None:
                        self.mode = self.character_return_mode
                        self.pending_start_level = None
                    else:
                        self.mode = "menu"

            elif self.mode == "store":
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.store_selection = (self.store_selection - 1) % 3
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.store_selection = (self.store_selection + 1) % 3
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.store_selection in (0, 1):
                        self.purchase_store_item(self.store_selection)
                    else:
                        self.mode = "personnel"
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "personnel"

            elif self.mode == "level_select":
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.level_select_selection = (self.level_select_selection - 1) % len(LEVELS)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.level_select_selection = (self.level_select_selection + 1) % len(LEVELS)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_selected_level(self.level_select_selection)
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "menu"

            elif self.mode == "skills":
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.skill_selection = (self.skill_selection - 1) % (len(SKILL_NODES) + 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.skill_selection = (self.skill_selection + 1) % (len(SKILL_NODES) + 1)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.skill_selection < len(SKILL_NODES):
                        self.purchase_skill(self.skill_selection)
                    else:
                        self.mode = "personnel"
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "personnel"

            elif self.mode == "ability_mods":
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    self.mods_character_index = (self.mods_character_index - 1) % len(CHARACTER_IDS)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self.mods_character_index = (self.mods_character_index + 1) % len(CHARACTER_IDS)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.mods_selection = (self.mods_selection - 1) % 3
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.mods_selection = (self.mods_selection + 1) % 3
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.mods_selection < 2:
                        self.purchase_ability_mod(self.mods_selection)
                    else:
                        self.mode = "safehouse"
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "safehouse"

            elif self.mode == "achievements":
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.mode = "menu"
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.achievement_scroll = max(0, self.achievement_scroll - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.achievement_scroll = min(max(0, len(ACHIEVEMENTS) - 7), self.achievement_scroll + 1)

            elif self.mode == "rankings":
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.ranking_scroll = max(0, self.ranking_scroll - 1)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.ranking_scroll = min(max(0, len(LEVELS) - 10), self.ranking_scroll + 1)
                elif event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self.mode = "menu"

            elif self.mode == "level_result":
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.continue_from_level_result()
                elif event.key == pygame.K_ESCAPE:
                    # The next sector is the primary continuation; ESC exits to
                    # the menu instead of unexpectedly detouring through SAFEHOUSE.
                    self.mode = "menu"
                    self.menu_selection = 0

            elif self.mode == "playing":
                if event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                    if self.player.character_id == "flyer" and not self.player.on_ground:
                        self.player.flight_requested = True
                    else:
                        self.player.jump_buffer = 0.13
                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_x):
                    self.process_dash_event()
                elif event.key in (pygame.K_j, pygame.K_c):
                    self.fire_player_shot()
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "paused"
                elif event.key == pygame.K_r:
                    self.restart_level()

            elif self.mode == "paused":
                if event.key == pygame.K_ESCAPE:
                    # ESC closes the pause screen and resumes the same run.
                    # Returning to the menu is an explicit pause-menu action.
                    self.mode = "playing"
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.pause_selection = (self.pause_selection - 1) % 5
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.pause_selection = (self.pause_selection + 1) % 5
                elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d) and self.pause_selection in (3, 4):
                    delta = -0.05 if event.key in (pygame.K_LEFT, pygame.K_a) else 0.05
                    key = "music" if self.pause_selection == 3 else "sfx"
                    current = self.music_volume if key == "music" else self.sfx_volume
                    self.set_audio_slider(key, current + delta, save=True)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.pause_selection == 0:
                        self.mode = "playing"
                    elif self.pause_selection == 1:
                        self.restart_level()
                    elif self.pause_selection == 2:
                        self.mode = "menu"
                        self.menu_selection = 0

            elif self.mode in ("gameover", "victory"):
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_arena_mode() if self.is_arena_mode else self.start_game()
                elif event.key == pygame.K_ESCAPE:
                    self.mode = "menu"
            return

        if event.type == pygame.KEYUP and event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
            # AERIS flight is activated by a second airborne press and runs until
            # fuel is spent or the player lands; releasing the key won't cancel it.
            pass

        if event.type == pygame.MOUSEWHEEL and self.mode == "achievements":
            max_scroll = max(0, len(ACHIEVEMENTS) - 7)
            self.achievement_scroll = max(0, min(max_scroll, self.achievement_scroll - event.y))
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5) and self.mode == "achievements":
            max_scroll = max(0, len(ACHIEVEMENTS) - 7)
            delta = -1 if event.button == 4 else 1
            self.achievement_scroll = max(0, min(max_scroll, self.achievement_scroll + delta))
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.settings_drag is not None:
                self.settings_drag = None
                self.save_progress()
            return

        if event.type == pygame.MOUSEMOTION and self.settings_drag is not None:
            mouse_pos = self.logical_mouse_pos(event.pos)
            self.set_audio_slider(self.settings_drag, self.audio_slider_value_from_x(mouse_pos[0]))
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = self.logical_mouse_pos(event.pos)
            if self.mode == "safehouse" and self.safehouse_event_active:
                return
            if self.mode == "paused" and pygame.Rect(410, 446, 340, 34).collidepoint(mouse_pos):
                self.settings_drag = "music"
                self.set_audio_slider("music", self.audio_slider_value_from_x(mouse_pos[0]))
                return
            elif self.mode == "paused" and pygame.Rect(410, 504, 340, 34).collidepoint(mouse_pos):
                self.settings_drag = "sfx"
                self.set_audio_slider("sfx", self.audio_slider_value_from_x(mouse_pos[0]))
                return
            if self.mode == "playing":
                self.fire_player_shot()

            elif self.mode == "menu":
                if pygame.Rect(870, 23, 205, 38).collidepoint(mouse_pos):
                    self.toggle_language()
                    return
                menu_rects = [pygame.Rect(95 + (i % 2) * 460, 270 + (i // 2) * 55, 450, 46)
                              for i in range(8)]
                for menu_i, rect in enumerate(menu_rects):
                    if rect.collidepoint(mouse_pos):
                        self.open_menu_item(menu_i)
                        break

            elif self.mode == "safehouse":
                # Click-to-walk is convenient, but interaction still occurs at the physical station.
                if pygame.Rect(self.safehouse_filter_x - 95, 245, 190, 160).collidepoint(mouse_pos):
                    self.player.x = float(self.safehouse_filter_x - self.player.w / 2)
                    self.player.y = 182.0
                    self.player.vy = 0.0
                    self.player.on_ground = True
                    self.interact_safehouse()
                    return
                for i, npc_x in enumerate(self.hub_npc_positions):
                    if i == 3 and len(set(self.save_data.get("completed_levels", []))) < 3:
                        continue
                    if pygame.Rect(npc_x - 58, 365, 116, 145).collidepoint(mouse_pos):
                        self.player.x = float(npc_x - self.player.w / 2)
                        self.player.y = 457.0
                        self.player.vy = 0.0
                        self.player.on_ground = True
                        self.interact_safehouse()
                        break
                else:
                    if pygame.Rect(600, 410, 112, 100).collidepoint(mouse_pos):
                        self.player.x = float(650 - self.player.w / 2)
                        self.player.y = 457.0
                        self.player.vy = 0.0
                        self.player.on_ground = True
                        self.interact_safehouse()
                    elif pygame.Rect(365, 355, 90, 150).collidepoint(mouse_pos):
                        self.player.x = float(410 - self.player.w / 2)
                        self.player.y = 457.0
                        self.player.vy = 0.0
                        self.player.on_ground = True
                        self.interact_safehouse()
                    elif pygame.Rect(self.hub_armory_x - 55, 385, 110, 125).collidepoint(mouse_pos):
                        self.player.x = float(self.hub_armory_x - self.player.w / 2)
                        self.player.y = 457.0
                        self.player.vy = 0.0
                        self.player.on_ground = True
                        self.interact_safehouse()
                    elif pygame.Rect(self.hub_gate_x - 42, 355, 84, 150).collidepoint(mouse_pos):
                        self.player.x = float(self.hub_gate_x - self.player.w / 2)
                        self.player.y = 457.0
                        self.player.vy = 0.0
                        self.player.on_ground = True
                        self.interact_safehouse()

            elif self.mode == "cassette_deck":
                tapes = self.collected_cassette_ids()
                for index in range(10):
                    col, row = index % 5, index // 5
                    slot = pygame.Rect(65 + col * 198, 145 + row * 112, 184, 94)
                    if slot.collidepoint(mouse_pos) and str(index) in tapes:
                        self.cassette_selection = tapes.index(str(index))
                        self.cassette_playing = False
                        return
                if pygame.Rect(250, 386, 600, 150).collidepoint(mouse_pos):
                    self.toggle_cassette_playback()
                elif mouse_pos[1] > 550:
                    self.cassette_playing = False
                    self.mode = "safehouse"

            elif self.mode == "secret_room_167":
                if mouse_pos[1] > 540:
                    self.mode = "safehouse"
                elif mouse_pos[0] < WIDTH // 2:
                    self.secret_167_page = (self.secret_167_page - 1) % 3
                else:
                    self.secret_167_page = (self.secret_167_page + 1) % 3

            elif self.mode == "safehouse_dialog":
                if pygame.Rect(180, 497, 440, 42).collidepoint(mouse_pos):
                    self.safehouse_dialog_selection = 0
                    self.safehouse_dialog_action()
                elif pygame.Rect(760, 497, 160, 42).collidepoint(mouse_pos):
                    self.safehouse_dialog_selection = 1
                    self.safehouse_dialog_action()

            elif self.mode == "personnel":
                for i in range(4):
                    rect = pygame.Rect(235, 165 + i * 91, 630, 72)
                    if rect.collidepoint(mouse_pos):
                        self.personnel_selection = i
                        if i == 0:
                            self.character_select_selection = self.character_index
                            self.personnel_open = True
                            self.mode = "character_select"
                        elif i == 1:
                            self.skill_selection = 0
                            self.mode = "skills"
                        elif i == 2:
                            self.store_selection = 0
                            self.mode = "store"
                        else:
                            self.personnel_open = False
                            self.mode = "menu"
                        break

            elif self.mode == "character_select":
                for i in range(len(CHARACTER_IDS)):
                    rect = pygame.Rect(48 + i * 250, 160, 230, 350)
                    if rect.collidepoint(mouse_pos):
                        self.choose_character(i)
                        break
                if pygame.Rect(WIDTH // 2 - 145, 526, 290, 52).collidepoint(mouse_pos):
                    if self.personnel_open:
                        self.mode = "personnel"
                    elif self.pending_start_level is not None:
                        self.mode = self.character_return_mode
                        self.pending_start_level = None
                    else:
                        self.mode = "menu"

            elif self.mode == "level_select":
                for i in range(len(LEVELS)):
                    col, row = i // 5, i % 5
                    rect = pygame.Rect(190 + col * 390, 190 + row * 62, 350, 48)
                    if rect.collidepoint(mouse_pos):
                        self.start_selected_level(i)
                        break
                if pygame.Rect(WIDTH // 2 - 145, 510, 290, 48).collidepoint(mouse_pos):
                    self.mode = "menu"

            elif self.mode == "skills":
                for i in range(len(SKILL_NODES)):
                    col, row = i % 2, i // 2
                    rect = pygame.Rect(145 + col * 405, 210 + row * 125, 365, 105)
                    if rect.collidepoint(mouse_pos):
                        self.purchase_skill(i)
                if pygame.Rect(WIDTH // 2 - 145, 490, 290, 48).collidepoint(mouse_pos):
                    self.mode = "personnel"

            elif self.mode == "ability_mods":
                for i in range(len(CHARACTER_IDS)):
                    tab = pygame.Rect(42 + i * 255, 132, 244, 82)
                    if tab.collidepoint(mouse_pos):
                        self.mods_character_index = i
                        self.mods_selection = 0
                        break
                else:
                    if pygame.Rect(150, 300, 800, 88).collidepoint(mouse_pos):
                        self.mods_selection = 0
                        self.purchase_ability_mod(0)
                    elif pygame.Rect(150, 405, 800, 88).collidepoint(mouse_pos):
                        self.mods_selection = 1
                        self.purchase_ability_mod(1)
                    elif pygame.Rect(WIDTH // 2 - 170, 525, 340, 44).collidepoint(mouse_pos):
                        self.mode = "safehouse"

            elif self.mode == "achievements":
                if pygame.Rect(WIDTH // 2 - 145, 545, 290, 48).collidepoint(mouse_pos):
                    self.mode = "menu"

            elif self.mode == "store":
                if pygame.Rect(WIDTH // 2 - 250, 250, 500, 92).collidepoint(mouse_pos):
                    self.purchase_store_item(0)
                elif pygame.Rect(WIDTH // 2 - 250, 362, 500, 92).collidepoint(mouse_pos):
                    self.purchase_store_item(1)
                elif pygame.Rect(WIDTH // 2 - 150, 480, 300, 52).collidepoint(mouse_pos):
                    self.mode = "personnel"

            elif self.mode == "rankings":
                if pygame.Rect(WIDTH // 2 - 145, 545, 290, 48).collidepoint(mouse_pos):
                    self.mode = "menu"

            elif self.mode == "level_result":
                if pygame.Rect(WIDTH // 2 - 145, 530, 290, 52).collidepoint(mouse_pos):
                    self.continue_from_level_result()

            elif self.mode == "paused":
                if pygame.Rect(WIDTH // 2 - 145, 300, 290, 44).collidepoint(mouse_pos):
                    self.mode = "playing"
                elif pygame.Rect(WIDTH // 2 - 145, 352, 290, 44).collidepoint(mouse_pos):
                    self.restart_level()
                elif pygame.Rect(WIDTH // 2 - 145, 404, 290, 44).collidepoint(mouse_pos):
                    self.mode = "menu"
                    self.menu_selection = 0

            elif self.mode in ("gameover", "victory"):
                if pygame.Rect(WIDTH // 2 - 145, 410, 290, 58).collidepoint(mouse_pos):
                    self.start_arena_mode() if self.is_arena_mode else self.start_game()

    def update(self, dt: float) -> None:
        self.time += dt
        self.shake = max(0.0, self.shake - dt)
        self.notice_timer = max(0.0, self.notice_timer - dt)
        self.menu_notice_timer = max(0.0, self.menu_notice_timer - dt)
        self.achievement_popup_timer = max(0.0, self.achievement_popup_timer - dt)
        if self.mode == "playing":
            self.coin_multiplier_timer = max(0.0, self.coin_multiplier_timer - dt)

        mobile_fire = False
        mobile_dash = False
        mobile_jump = False
        mobile_jump_held = False
        mobile_menu = False
        try:
            import platform as browser_platform
            mobile_axis = float(browser_platform.window.oxygen_touch_axis or 0.0)
            # Jump/menu are queued in JavaScript until this frame consumes them,
            # so a quick tap cannot disappear between two game frames.
            mobile_jump = bool(browser_platform.window.oxygen_touch_jump)
            mobile_jump_held = bool(browser_platform.window.oxygen_touch_jump_held)
            mobile_menu = bool(browser_platform.window.oxygen_touch_menu)
            if mobile_jump:
                browser_platform.window.oxygen_touch_jump = False
            if mobile_menu:
                browser_platform.window.oxygen_touch_menu = False
            mobile_fire = bool(browser_platform.window.oxygen_touch_fire)
            mobile_dash = bool(browser_platform.window.oxygen_touch_dash)
            if mobile_dash:
                browser_platform.window.oxygen_touch_dash = False
            controls = browser_platform.window.document.getElementById("mobile-controls")
            controls.style.display = "flex" if self.mode in ("playing", "safehouse", "paused") else "none"
            # Show only the character's actual special-action button.
            action = browser_platform.window.document.getElementById("mobile-fire")
            if self.player.character_id == "runner":
                action.innerText = "DASH"
                action.style.display = "block"
                action.setAttribute("data-action", "dash")
            elif self.player.character_id == "jumper":
                action.style.display = "none"
            else:
                action.innerText = "FIRE"
                action.style.display = "block"
                action.setAttribute("data-action", "fire")
        except Exception:
            mobile_axis = 0.0
            mobile_jump = False
            mobile_jump_held = False
            mobile_menu = False
            mobile_dash = False
        self.player.mobile_axis = max(-1.0, min(1.0, mobile_axis))
        self.player.mobile_jump = mobile_jump
        self.player.mobile_jump_held = mobile_jump_held
        self.mobile_fire = mobile_fire
        if mobile_dash and self.mode == "playing" and self.player.character_id == "runner":
            self.process_dash_event()
        # A tap is a one-shot jump request; no key-up event is required.
        if mobile_jump and self.mode in ("playing", "safehouse"):
            # A touch tap can begin and end between two WASM frames. Keep the
            # jump held briefly so the variable-height impulse is not cut off.
            self.player.mobile_jump_hold_timer = max(self.player.mobile_jump_hold_timer, 0.20)
            if self.player.character_id == "flyer" and not self.player.on_ground:
                self.player.flight_requested = True
            else:
                self.player.jump_buffer = 0.16
        self.mobile_jump_was_down = False
        if (mobile_menu and self.mode in ("playing", "safehouse", "paused")
                and not self.safehouse_event_active):
            self.mode = "menu"
            self.menu_selection = 0
        self.update_music_scene(dt)
        if self.mode == "safehouse":
            self.update_safehouse(dt)
            return
        if self.mode != "playing":
            return
        self.level_elapsed += dt

        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        shoot_held = (keys[pygame.K_j] or keys[pygame.K_c] or mobile_fire
                      or (len(mouse_buttons) > 0 and mouse_buttons[0]))
        if self.player.character_id in ("shooter", "flyer") and shoot_held:
            self.fire_player_shot()
        riding = None
        player_rect_before = self.player.rect
        if self.player.on_ground:
            for moving in self.level.moving_platforms:
                moving_rect = moving.rect
                if (abs(player_rect_before.bottom - moving_rect.top) <= 4
                        and player_rect_before.right > moving_rect.left + 3
                        and player_rect_before.left < moving_rect.right - 3):
                    riding = moving
                    break
        self.level.update(dt, self.player.x + self.player.w / 2, self.player.y + self.player.h / 2)
        if riding is not None:
            # Carry riders in two collision-resolved steps. This prevents a
            # moving platform from pushing the player through a nearby wall or
            # ceiling when its direction changes.
            dx, dy = riding.delta_x, riding.delta_y
            self.player.x += dx
            carried = self.player.rect
            for solid in self.level.solids:
                if solid == riding.rect or not carried.colliderect(solid):
                    continue
                if dx > 0:
                    carried.right = solid.left
                elif dx < 0:
                    carried.left = solid.right
                self.player.x = float(carried.x)
                self.player.vx = 0.0
            self.player.y += dy
            carried = self.player.rect
            for solid in self.level.solids:
                if solid == riding.rect or not carried.colliderect(solid):
                    continue
                if dy < 0:
                    carried.top = solid.bottom
                    self.player.y = float(carried.y)
                    self.player.vy = max(0.0, self.player.vy)
                elif dy > 0:
                    carried.bottom = solid.top
                    self.player.y = float(carried.y)
                    self.player.vy = 0.0
                    self.player.on_ground = True
        self.player.wall_mastery = bool(self.save_data["skills"].get("wall_mastery", False))
        previous_wall_jumps = self.player.wall_jump_count
        previous_jump_count = self.player.jump_count
        previous_on_ground = self.player.on_ground
        self.footstep_timer = max(0.0, self.footstep_timer - dt)
        self.player.update(dt, keys, self.level, self.particles)
        if self.player.jump_count > previous_jump_count:
            self.play_sfx("jump")
        if not previous_on_ground and self.player.on_ground:
            self.play_sfx("landing")
        if (self.player.on_ground and abs(self.player.vx) > 115
                and self.player.dash_time <= 0 and self.footstep_timer <= 0):
            self.play_sfx("footstep")
            self.footstep_timer = 0.34
        if (self.player.character_id == "jumper" and previous_jump_count >= 1
                and self.player.jump_count > previous_jump_count):
            self.play_sfx("double_jump")
        if getattr(self.player, "is_flying", False):
            self.play_sfx("flight")
        else:
            self.stop_flight_sfx()
        if self.player.wall_jump_count > previous_wall_jumps:
            gained = self.player.wall_jump_count - previous_wall_jumps
            self.save_data["stats"]["wall_jumps"] += gained
            self.check_achievements()
        if self.level.boss is not None and not self.level.boss.active and not self.level.boss.defeated:
            activation_x = self.level.width - 760 if self.level_index == 9 else 3920
            if self.player.x > activation_x:
                self.level.boss.active = True
                self.start_boss_arena()
                self.notice = f"{self.level.boss.name} AWAKENS // BOSS PLATFORM LOCKED"
                self.notice_timer = 2.4
                self.shake = 0.18
        boss = self.level.boss
        # The cooldown advances during active campaign play, not while paused or
        # in menus. A crystal can only materialize during an active boss fight,
        # so reaching 30 minutes mid-campaign never drops one into a normal level.
        if not self.is_arena_mode:
            self.boss_crystal_timer += dt
        if boss is not None and boss.active and not boss.defeated and not self.is_arena_mode:
            self.boss_fight_elapsed += dt
            if (self.healing_crystal is None and self.boss_crystal_timer >= 1800.0
                    and self.boss_fight_elapsed >= self.boss_crystal_delay):
                self.spawn_healing_crystal()
                if self.healing_crystal is not None:
                    self.boss_crystal_timer = 0.0
                    self.boss_fight_elapsed = 0.0
                    self.boss_crystal_delay = random.uniform(25.0, 50.0)
            elif self.healing_crystal is not None:
                self.healing_crystal.update(dt)
        elif self.healing_crystal is not None:
            # A spawned crystal persists only for the boss arena in which it
            # appeared; it cannot be carried into another sector.
            self.healing_crystal = None
        self.level_banner = max(0.0, self.level_banner - dt)

        # Player energy bolts can destroy drones, hunters and the Core.
        for shot in self.projectiles:
            shot.update(dt)
            if not shot.alive:
                continue
            if any(shot.rect.colliderect(solid) for solid in self.level.solids):
                shot.alive = False
                continue
            hit_enemy = False
            enemy_groups = [
                ("drone", self.level.drones), ("seeker", self.level.seekers),
                ("spider", self.level.spiders), ("turret", self.level.turrets)
            ]
            for enemy_kind, group in enemy_groups:
                for enemy in group:
                    if enemy.alive and shot.rect.colliderect(enemy.rect):
                        if id(enemy) == shot.last_hit_target:
                            continue
                        enemy.hp = max(0, enemy.hp - shot.damage)
                        if shot.pierce > 0:
                            shot.pierce -= 1
                            shot.last_hit_target = id(enemy)
                        else:
                            shot.alive = False
                        enemy_color = (THEMES[self.level_index]["accent"] if enemy_kind in ("seeker", "spider")
                                       else THEMES[self.level_index]["accent2"])
                        if enemy.hp <= 0:
                            enemy.alive = False
                            self.score += 350 if enemy_kind in ("seeker", "spider") else 250
                            self.register_enemy_kill(enemy_kind)
                            self.play_sfx("kill")
                            self.make_burst(enemy.x, enemy.y, enemy_color, 20 if enemy_kind in ("seeker", "spider") else 18)
                        else:
                            self.make_burst(enemy.x, enemy.y, enemy_color, 6)
                        hit_enemy = True
                        break
                if hit_enemy:
                    break
            if hit_enemy:
                continue
            boss = self.level.boss
            if boss is not None and boss.active and not boss.defeated and shot.rect.colliderect(boss.rect):
                shot.alive = False
                boss_damage = 2 if self.player.character_id == "flyer" else 1
                if (self.player.character_id == "flyer" and
                        "starfall" in self.save_data.get("character_mods", {}).get("flyer", [])):
                    boss_damage = 4
                defeated_now = boss.take_hit(boss_damage)
                self.make_burst(boss.x, boss.y, (255, 86, 130), 12 if not defeated_now else 45)
                if defeated_now:
                    self.handle_boss_defeated(boss)
        self.projectiles = [shot for shot in self.projectiles
                            if shot.alive and -40 < shot.x < self.level.width + 40]

        # The x2 cache appears once in sectors 03, 06 and 09. It doubles all
        # coin rewards for twenty seconds and is recorded in the save file.
        if self.level.coin_doubler is not None and not self.level.coin_doubler.collected:
            self.level.coin_doubler.update(dt)
            if self.player.rect.colliderect(self.level.coin_doubler.rect):
                self.level.coin_doubler.collected = True
                self.coin_multiplier_timer = 20.0
                collected = self.save_data.setdefault("collected_doublers", [])
                if str(self.level_index) not in collected:
                    collected.append(str(self.level_index))
                self.notice = "COIN CACHE // DOUBLE COINS FOR 20 SECONDS"
                self.notice_timer = 3.0
                self.play_sfx("coin")
                self.save_progress()

        # Recover the sector's unique EXP cassette. This is a separate,
        # permanent collection from coins and survives level revisits.
        player_rect = self.player.rect
        for cassette in self.level.cassettes:
            if not cassette["collected"] and player_rect.colliderect(cassette["rect"]):
                cassette["collected"] = True
                cassette_id = str(cassette["id"])
                collected = self.save_data.setdefault("collected_cassettes", [])
                if cassette_id not in collected:
                    collected.append(cassette_id)
                    collected.sort(key=lambda value: int(value))
                    self.save_progress()
                    self.notice = f"EXP CASSETTE {int(cassette_id) + 1:02d}/10 // RECOVERED"
                    self.notice_timer = 3.0
                    self.make_burst(cassette["x"], cassette["y"],
                                    THEMES[self.level_index]["accent"], 22)
                    self.play_sfx("checkpoint")

        # Coins.
        coin_pickup_rect = player_rect.inflate(84, 84) if self.save_data["skills"].get("coin_echo") else player_rect
        for coin_index, coin in enumerate(self.level.coins):
            if not coin.collected and coin_pickup_rect.colliderect(
                    pygame.Rect(int(coin.x - 10), int(coin.y - 10), 20, 20)):
                coin.collected = True
                self.score += 100
                coin_key = f"{self.level_index}:{coin_index}"
                if coin_key not in self.collected_coin_keys:
                    self.collected_coin_keys.add(coin_key)
                    coin_value = 2 if self.coin_multiplier_timer > 0 else 1
                    self.total_coins += coin_value
                    self.level_coins += coin_value
                    self.save_data["stats"]["coins_collected"] += coin_value
                    self.save_progress()
                    self.check_achievements()
                self.make_burst(coin.x, coin.y, YELLOW, 11)
                self.play_sfx("coin")

        if self.healing_crystal is not None and self.player.rect.colliderect(self.healing_crystal.rect):
            if self.player.hp < self.player.max_hp:
                self.player.hp = min(self.player.max_hp, self.player.hp + 1)
                self.notice = "HEALING CRYSTAL // +1 HP"
            else:
                self.notice = "HEALING CRYSTAL // HEALTH FULL"
            self.notice_timer = 2.2
            self.make_burst(self.healing_crystal.x, self.healing_crystal.y, CYAN, 22)
            self.healing_crystal = None

        # Checkpoints.
        for cp in self.level.checkpoints:
            if not cp.active and player_rect.colliderect(cp.rect):
                cp.active = True
                self.level.checkpoint_spawn = (cp.x - 15, cp.y - self.player.h)
                self.notice = "CHECKPOINT // SAVED"
                self.notice_timer = 1.8
                self.make_burst(cp.x, cp.y - 45, THEMES[self.level_index]["accent"], 16)
                self.play_sfx("checkpoint")

        # Hidden alcoves reward exploration and progress secret-room quests.
        for secret_i, secret in enumerate(self.level.secret_rooms):
            if not secret["found"] and player_rect.colliderect(secret["rect"]):
                secret["found"] = True
                secret_key = f"{self.level_index}:{secret_i}"
                if secret_key not in self.save_data["found_secrets"]:
                    self.save_data["found_secrets"].append(secret_key)
                    self.level_secrets += 1
                    secret_reward = 5 * (2 if self.coin_multiplier_timer > 0 else 1)
                    self.total_coins += secret_reward
                    self.save_data["stats"]["coins_collected"] += secret_reward
                    self.save_progress()
                    self.check_achievements()
                    self.notice = f"SECRET ROOM // {secret['name']} // +{secret_reward} COINS"
                    self.notice_timer = 2.6
                    self.make_burst(secret["rect"].centerx, secret["rect"].centery,
                                    THEMES[self.level_index]["accent"], 24)

        # Drones, seekers, spiders and turrets can be defeated with a dash or stomp.
        enemies = [(enemy, "drone") for enemy in self.level.drones]
        enemies.extend((enemy, "seeker") for enemy in self.level.seekers)
        enemies.extend((enemy, "spider") for enemy in self.level.spiders)
        enemies.extend((enemy, "turret") for enemy in self.level.turrets)
        for enemy, enemy_kind in enemies:
            is_seeker = enemy_kind in ("seeker", "spider")
            if (not enemy.alive or not self.player.rect.colliderect(enemy.rect)
                    or self.player.stomp_grace > 0):
                continue
            enemy_color = THEMES[self.level_index]["accent"] if is_seeker else THEMES[self.level_index]["accent2"]
            if self.player.dash_time > 0:
                enemy.hp = max(0, enemy.hp - 3)
                if enemy.hp <= 0:
                    enemy.alive = False
                    self.score += 350 if is_seeker else 250
                    self.register_enemy_kill(enemy_kind)
                    self.play_sfx("kill")
                    self.make_burst(enemy.x, enemy.y, enemy_color, 20 if is_seeker else 18)
                else:
                    self.player.vx = -self.player.facing * 300
                    self.player.vy = -180
                    self.make_burst(enemy.x, enemy.y, enemy_color, 8)
            elif self.player.vy > 80 and self.player.y + self.player.h - 10 < enemy.y + 7:
                stomp_damage = 1 + self.save_data["strength_level"]
                if "shock_stomp" in self.save_data.get("character_mods", {}).get(self.player.character_id, []):
                    stomp_damage += 1
                enemy.hp = max(0, enemy.hp - stomp_damage)
                self.player.vy = -410 if is_seeker else -390
                self.player.jump_count = 0
                self.player.stomp_grace = 0.22
                if enemy.hp <= 0:
                    enemy.alive = False
                    self.score += 300 if is_seeker else 200
                    self.register_enemy_kill(enemy_kind)
                    self.play_sfx("kill")
                    self.make_burst(enemy.x, enemy.y, enemy_color, 18 if is_seeker else 16)
                else:
                    self.make_burst(enemy.x, enemy.y, enemy_color, 7)
            else:
                self.damage_player()
                break

        if self.mode != "playing":
            return

        # The Core can be damaged by a dash or a clean stomp. Its attacks are
        # telegraphed, so the player can jump over charges and dodge projectiles.
        boss = self.level.boss
        if boss is not None and boss.active and not boss.defeated:
            if self.player.rect.colliderect(boss.rect):
                if boss.invuln <= 0 and self.player.dash_time > 0:
                    dash_damage = 4 if "phase_burn" in self.save_data.get("character_mods", {}).get("runner", []) else 2
                    defeated_now = boss.take_hit(dash_damage)
                    self.player.vx = -self.player.facing * 260
                    self.make_burst(boss.x, boss.y, (255, 86, 130), 17)
                    if defeated_now:
                        self.handle_boss_defeated(boss)
                elif boss.invuln <= 0 and self.player.vy > 75 and self.player.rect.bottom < boss.rect.top + 42:
                    defeated_now = boss.take_hit(1)
                    self.player.vy = -475
                    self.player.jump_count = 0
                    self.make_burst(boss.x, boss.y, (255, 86, 130), 14)
                    if defeated_now:
                        self.handle_boss_defeated(boss)
                elif boss.invuln <= 0:
                    self.damage_player()
            for enemy_shot in boss.shots:
                if enemy_shot.alive and any(enemy_shot.rect.colliderect(solid)
                                            for solid in self.level.solids):
                    enemy_shot.alive = False
                elif enemy_shot.alive and enemy_shot.rect.colliderect(self.player.rect):
                    enemy_shot.alive = False
                    self.damage_player()
                    self.make_burst(enemy_shot.x, enemy_shot.y, enemy_shot.color, 8)

        if self.mode != "playing":
            return

        # Sentry bolts are separate from the Core's boss projectiles.
        for enemy_shot in self.level.enemy_shots:
            if not enemy_shot.alive:
                continue
            if any(enemy_shot.rect.colliderect(solid) for solid in self.level.solids):
                enemy_shot.alive = False
            elif enemy_shot.rect.colliderect(self.player.rect):
                enemy_shot.alive = False
                self.damage_player()

        if self.mode != "playing":
            return

        # Spikes and falling out of the world.
        if self.player.invuln <= 0:
            if any(spike_hits_player(self.player.rect, s) for s in self.level.spikes):
                self.damage_player()
            elif self.player.y > HEIGHT + 130:
                self.damage_player()

        # Exit gate.
        if self.mode == "playing" and self.player.rect.colliderect(self.level.exit_rect):
            if self.level.boss is not None and not self.level.boss.defeated:
                self.notice = f"DEFEAT {self.level.boss.name} // EXIT SEALED"
                self.notice_timer = max(self.notice_timer, 0.9)
            else:
                self.complete_current_level()

        # Smooth camera.
        target = self.player.x - WIDTH * 0.39
        target = max(0.0, min(target, self.level.width - WIDTH))
        self.camera_x += (target - self.camera_x) * min(1.0, dt * 6.5)

        self.particles = [p for p in self.particles if p.update(dt)]
        self.update_arena_progression(dt)

    def make_surface_grain(self) -> pygame.Surface:
        """Create a subtle fixed texture overlay for the dark neon materials."""
        texture = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        rng = random.Random(1672026)
        for _ in range(520):
            x = rng.randrange(WIDTH)
            y = rng.randrange(HEIGHT)
            alpha = rng.randrange(5, 15)
            color = rng.choice(((115, 152, 184), (60, 105, 133), (185, 204, 218)))
            texture.fill((*color, alpha), (x, y, rng.choice((1, 2)), 1))
        for y in range(0, HEIGHT, 5):
            pygame.draw.line(texture, (100, 150, 180, 5), (0, y), (WIDTH, y), 1)
        return texture

    def make_skyline(self, level_index: int) -> pygame.Surface:
        """Build a stable, softly lit skyline for one level.

        The whole city is one cached image: windows are part of their
        buildings rather than being animated or positioned independently.
        """
        tile_width = 210
        parallax_speed = 0.10
        max_camera = max(0, LEVELS[level_index]["width"] - WIDTH)
        layer_width = WIDTH + int(max_camera * parallax_speed) + tile_width * 2
        layer = pygame.Surface((layer_width, HEIGHT), pygame.SRCALPHA)
        rng = random.Random(167 + level_index * 7919)
        base = 458
        accent = THEMES[level_index]["accent"]

        # Muted window color: atmospheric detail, not bright UI-like dashes.
        window_color = tuple(max(15, int(channel * 0.30)) for channel in accent)
        highlight_color = tuple(max(20, int(channel * 0.46)) for channel in accent)

        tile_count = math.ceil(layer_width / tile_width) + 2
        for tile_index in range(-1, tile_count):
            bx = tile_index * tile_width
            h = 80 + ((tile_index * 47 + level_index * 23) % 120)
            bw = 90 + ((tile_index * 31) % 65)
            building = pygame.Rect(bx, base - h, bw, h)
            pygame.draw.rect(layer, (13, 20, 39), building)
            pygame.draw.line(layer, (31, 51, 73), building.topleft,
                             (building.right, building.top), 2)

            # Irregular, deterministic windows. A local RNG keeps every
            # window fixed in the same place for the entire play session.
            window_rng = random.Random(167 + level_index * 100003 + tile_index * 9176)
            slots = []
            for wy in range(building.top + 18, base - 14, 27):
                for wx in range(bx + 13, bx + bw - 10, 22):
                    slots.append((wx, wy))
            window_rng.shuffle(slots)
            lit_count = min(len(slots), window_rng.randint(2, 5))
            for window_number, (wx, wy) in enumerate(slots[:lit_count]):
                ww = window_rng.choice((3, 4, 5))
                wh = window_rng.choice((5, 7, 9))
                color = highlight_color if window_number == 0 else window_color
                pygame.draw.rect(layer, color, (wx, wy, ww, wh), border_radius=1)

        return layer

    def draw_background(self, theme, background_level_index: int | None = None) -> None:
        self.screen.blit(self.gradient, (0, 0))
        # Reuse static atmosphere surfaces: allocating two full-screen alpha
        # surfaces for every frame was a significant source of frame drops.
        wash_key = (tuple(theme["accent"]), tuple(theme["accent2"]))
        wash = _BACKGROUND_WASH_CACHE.get(wash_key)
        if wash is None:
            wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.ellipse(wash, (*theme["accent"], 15), (-120, 310, WIDTH + 250, 280))
            pygame.draw.ellipse(wash, (*theme["accent2"], 12), (WIDTH - 360, 170, 570, 440))
            _BACKGROUND_WASH_CACHE[wash_key] = wash
        self.screen.blit(wash, (0, 0))

        for sx, sy, speed, size, phase in self.stars:
            x = int((sx - self.camera_x * speed) % (WIDTH + 40))
            twinkle = 0.55 + 0.45 * math.sin(self.time * 2.2 + phase)
            col = (int(85 + 95 * twinkle), int(115 + 100 * twinkle),
                   int(155 + 95 * twinkle))
            pygame.draw.circle(self.screen, col, (x, sy), size)

        # One cached skyline layer, moved very slowly for subtle depth.
        # Since the lights are baked into this surface, they cannot slide
        # around inside a building when the camera follows the player.
        skyline_offset = int(self.camera_x * 0.10)
        skyline_index = self.level_index if background_level_index is None else background_level_index
        self.screen.blit(self.skyline_layers[skyline_index], (-skyline_offset, 0))

        # Horizon scan lines.
        for y in range(465, HEIGHT, 18):
            pygame.draw.line(self.screen, (20, 33, 55), (0, y), (WIDTH, y), 1)

    def draw_world(self) -> None:
        theme = THEMES[self.level_index]
        accent, accent2 = theme["accent"], theme["accent2"]
        self.draw_background(theme)

        # Background signal glyphs.
        for i in range(7):
            wx = i * 560 + 180
            x = int(wx - self.camera_x * 0.55)
            if -80 < x < WIDTH + 80:
                y = 100 + (i % 3) * 63
                pygame.draw.circle(self.screen, (25, 43, 67), (x, y), 23, 1)
                pygame.draw.line(self.screen, (26, 44, 70), (x - 31, y), (x + 31, y), 1)
                pygame.draw.line(self.screen, (26, 44, 70), (x, y - 31), (x, y + 31), 1)

        for platform in self.level.platforms:
            draw_platform(self.screen, platform, self.camera_x, accent)
        for pad in self.level.launch_pads:
            px = int(pad.x - self.camera_x)
            if -pad.w < px < WIDTH:
                pygame.draw.rect(self.screen, (9, 42, 54), (px, pad.y, pad.w, pad.h), border_radius=4)
                pygame.draw.rect(self.screen, (73, 237, 218), (px + 3, pad.y + 2, pad.w - 6, 3), border_radius=2)
                for stripe in range(px + 10, px + pad.w - 6, 16):
                    pygame.draw.line(self.screen, (38, 151, 158), (stripe, pad.y + 6),
                                     (stripe + 6, pad.y + 10), 2)
        for moving in self.level.moving_platforms:
            mx = int(moving.x - self.camera_x)
            my = int(moving.y)
            if -moving.w < mx < WIDTH:
                pygame.draw.line(self.screen, accent2, (mx + 8, my + 7),
                                 (mx + moving.w - 8, my + 7), 2)
                pygame.draw.polygon(self.screen, accent2,
                                    [(mx + moving.w // 2 - 5, my - 4),
                                     (mx + moving.w // 2 + 5, my - 4),
                                     (mx + moving.w // 2, my + 2)])
        for spike in self.level.spikes:
            draw_spikes(self.screen, spike, self.camera_x, accent2)
        for cp in self.level.checkpoints:
            draw_checkpoint(self.screen, cp, self.camera_x, accent, self.time)
        exit_color = accent
        if self.level.boss is not None and not self.level.boss.defeated:
            exit_color = (112, 65, 95)
        draw_exit(self.screen, self.level.exit_rect, self.camera_x, exit_color, self.time)
        for coin in self.level.coins:
            draw_coin(self.screen, coin, self.camera_x, self.time, accent)
        for cassette in self.level.cassettes:
            if not cassette["collected"]:
                self.draw_cassette_prop(
                    self.screen, int(cassette["x"] - self.camera_x), int(cassette["y"]),
                    accent, 0.72, self.time)
        if self.healing_crystal is not None:
            self.healing_crystal.draw(self.screen, self.camera_x)
        if self.level.coin_doubler is not None and not self.level.coin_doubler.collected:
            self.level.coin_doubler.draw(self.screen, self.camera_x)
        for drone in self.level.drones:
            draw_drone(self.screen, drone, self.camera_x, accent2)
        for seeker in self.level.seekers:
            draw_seeker(self.screen, seeker, self.camera_x, accent)
        for spider in self.level.spiders:
            draw_spider(self.screen, spider, self.camera_x, accent2)
        for turret in self.level.turrets:
            draw_turret(self.screen, turret, self.camera_x, accent)
        for enemy_shot in self.level.enemy_shots:
            draw_projectile(self.screen, enemy_shot, self.camera_x)
        for secret in self.level.secret_rooms:
            if abs(secret["rect"].centerx - self.player.x) < 180:
                draw_secret_marker(self.screen, secret, self.camera_x, self.time, accent2)
        if self.level.boss is not None:
            draw_boss(self.screen, self.level.boss, self.camera_x)
            for shot in self.level.boss.shots:
                draw_projectile(self.screen, shot, self.camera_x)
        for shot in self.projectiles:
            draw_projectile(self.screen, shot, self.camera_x)
        for particle in self.particles:
            particle.draw(self.screen, self.camera_x)
        self.player.draw(self.screen, self.camera_x)

        # Full-screen texture overlays are expensive in WebAssembly/mobile browsers.
        # Keep the richer desktop look, but skip these two full-canvas blits on web.
        if sys.platform != "emscripten":
            self.screen.blit(self.surface_grain, (0, 0))
            self.screen.blit(self.vignette, (0, 0))

    def draw_hud(self) -> None:
        theme = THEMES[self.level_index]
        # Top left label.
        pygame.draw.rect(self.screen, (7, 12, 27), (22, 18, 255, 76), border_radius=8)
        pygame.draw.rect(self.screen, (43, 71, 92), (22, 18, 255, 76), 1, border_radius=8)
        sector_label = f"SALVAGE ARENA // WAVE {self.arena_wave}" if self.is_arena_mode else f"SECTOR 0{self.level_index + 1}"
        level_label = "SCRAP YARD" if self.is_arena_mode else self.level.name
        draw_text(self.screen, self.font_xs, sector_label,
                  theme["accent"], (37, 29), shadow=False)
        draw_text(self.screen, self.font_s, level_label,
                  WHITE, (37, 51), shadow=False)
        draw_text(self.screen, self.font_xs, CHARACTERS[self.player.character_id]["name"],
                  CHARACTERS[self.player.character_id]["accent"], (WIDTH // 2, 76),
                  center=True, shadow=False)
        if self.level.wall_jump_enabled:
            draw_text(self.screen, self.font_xs, "WALL JUMP // PRESS SPACE BESIDE A WALL",
                      theme["accent2"], (WIDTH // 2, 96), center=True, shadow=False)

        # Energy count.
        pygame.draw.rect(self.screen, (7, 12, 27), (WIDTH - 235, 18, 213, 48), border_radius=8)
        pygame.draw.rect(self.screen, (43, 71, 92), (WIDTH - 235, 18, 213, 48), 1, border_radius=8)
        draw_glow(self.screen, WIDTH - 209, 42, YELLOW, 16)
        pygame.draw.polygon(self.screen, YELLOW,
                            [(WIDTH - 209, 32), (WIDTH - 199, 42),
                             (WIDTH - 209, 52), (WIDTH - 219, 42)])
        draw_text(self.screen, self.font_m, f"{self.total_coins:02d}",
                  WHITE, (WIDTH - 187, 28), shadow=False)
        draw_text(self.screen, self.font_xs, f"SCORE {self.score:06d}",
                  MUTED, (WIDTH - 110, 35), shadow=False)

        # Keep health above the bottom touch controls on phones.
        health_panel = pygame.Rect(22, 104, 190, 48)
        pygame.draw.rect(self.screen, (7, 12, 27), health_panel, border_radius=8)
        pygame.draw.rect(self.screen, (43, 71, 92), health_panel, 1, border_radius=8)
        draw_text(self.screen, self.font_xs, "LIVES", MUTED, (34, 119), shadow=False)
        for i in range(self.player.max_hp):
            x = 91 + i * 31
            color = PINK if i < self.player.hp else (53, 61, 83)
            pygame.draw.polygon(self.screen, color,
                                [(x, 130), (x + 9, 122), (x + 18, 130),
                                 (x + 9, 140)])

        if self.coin_multiplier_timer > 0:
            boost_label = self.font_xs.render(
                localize(f"COINS x2 // {self.coin_multiplier_timer:04.1f}S"), True, YELLOW)
            badge = pygame.Rect(WIDTH - 235, 76, 213, 25)
            pygame.draw.rect(self.screen, (36, 31, 22), badge, border_radius=6)
            pygame.draw.rect(self.screen, YELLOW, badge, 1, border_radius=6)
            self.screen.blit(boost_label, boost_label.get_rect(center=badge.center))

        # Character-specific ability status.
        cfg = CHARACTERS[self.player.character_id]
        if self.player.character_id == "runner":
            ability_ready = 1.0 - min(1.0, self.player.dash_cooldown / 0.72)
            ability_label = "DASH"
        elif self.player.character_id == "jumper":
            ability_ready = 1.0 if self.player.on_ground or self.player.jump_count < 2 else 0.0
            ability_label = "AIR JUMP"
        elif self.player.character_id == "shooter":
            ability_ready = 1.0 - min(1.0, self.player.shoot_cooldown / 1.3)
            ability_label = "PULSE"
        else:
            ability_ready = self.player.flight_fuel / self.player.flight_fuel_max
            ability_label = "FLIGHT"
        # Keep ability charge above the bottom-right mobile action buttons.
        ability_panel = pygame.Rect(WIDTH - 230, 104, 208, 48)
        pygame.draw.rect(self.screen, (7, 12, 27), ability_panel, border_radius=8)
        pygame.draw.rect(self.screen, (43, 71, 92), ability_panel, 1, border_radius=8)
        draw_text(self.screen, self.font_xs, ability_label, WHITE,
                  (WIDTH - 216, 111), shadow=False)
        charge_pct = int(max(0.0, min(1.0, ability_ready)) * 100)
        draw_text(self.screen, self.font_xs, f"{charge_pct}%", cfg["accent"],
                  (WIDTH - 36, 111), shadow=False)
        bar = pygame.Rect(WIDTH - 216, 132, 180, 9)
        pygame.draw.rect(self.screen, (29, 41, 62), bar, border_radius=5)
        if charge_pct > 0:
            pygame.draw.rect(self.screen, cfg["accent"],
                             (bar.x, bar.y, max(3, int(bar.w * ability_ready)), bar.h),
                             border_radius=5)

        boss = self.level.boss
        if boss is not None and boss.active and not boss.defeated:
            if boss.variant == "arena":
                boss_label = f"{boss.name} // WAVE {self.arena_wave}"
            elif self.player.character_id == "flyer" and boss.name == "THE CORE":
                boss_label = "THE CORE // 18 SHOTS"
            elif self.player.character_id == "shooter" and boss.name == "THE CORE":
                boss_label = "THE CORE // 36 SHOTS"
            else:
                boss_label = f"{boss.name} // {boss.hp:02d} HP"
            draw_text(self.screen, self.font_xs, boss_label, (255, 111, 139),
                      (WIDTH // 2, 12), center=True, shadow=False)
            boss_bar = pygame.Rect(WIDTH // 2 - 190, 29, 380, 13)
            pygame.draw.rect(self.screen, (29, 17, 35), boss_bar, border_radius=6)
            pygame.draw.rect(self.screen, (111, 48, 81), boss_bar, 1, border_radius=6)
            fill_w = int((boss_bar.w - 4) * (boss.hp / boss.max_hp))
            if fill_w > 0:
                pygame.draw.rect(self.screen, (255, 67, 119),
                                 (boss_bar.x + 2, boss_bar.y + 2, fill_w, boss_bar.h - 4),
                                 border_radius=5)
            draw_text(self.screen, self.font_xs, f"{boss.hp:02d} / {boss.max_hp:02d}",
                      WHITE, (WIDTH // 2, 48), center=True, shadow=False)

        if self.notice_timer > 0:
            alpha = min(255, int(255 * min(1.0, self.notice_timer * 2)))
            note = self.font_s.render(localize(self.notice), True, theme["accent"])
            note.set_alpha(alpha)
            self.screen.blit(note, note.get_rect(center=(WIDTH // 2, 110)))

        if self.level_banner > 0:
            k = min(1.0, self.level_banner / 0.6)
            self.level_banner_surface.fill((4, 8, 22, int(150 * k)))
            self.screen.blit(self.level_banner_surface, (0, 190))
            main = self.font_l.render(localize(self.level.name), True, WHITE)
            sub = self.font_xs.render(localize(self.level.subtitle), True, theme["accent"])
            main.set_alpha(int(255 * k))
            sub.set_alpha(int(255 * k))
            self.screen.blit(main, main.get_rect(center=(WIDTH // 2, 225)))
            self.screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 267)))

    def draw_button(self, text: str, y: int, selected: bool = False,
                    width: int = 290) -> None:
        rect = pygame.Rect(WIDTH // 2 - width // 2, y, width, 52)
        fill = (20, 48, 63) if selected else (11, 21, 40)
        border = CYAN if selected else (52, 75, 99)
        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, border, rect, 2 if selected else 1, border_radius=8)
        if selected:
            pygame.draw.line(self.screen, CYAN, (rect.x + 18, y + 26),
                             (rect.x + 29, y + 26), 3)
        draw_text(self.screen, self.font_m, text,
                  WHITE if selected else MUTED, (WIDTH // 2, y + 26), center=True, shadow=False)

    def draw_button_at(self, text: str, rect: pygame.Rect, selected: bool = False) -> None:
        fill = (20, 48, 63) if selected else (11, 21, 40)
        border = CYAN if selected else (52, 75, 99)
        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, border, rect, 2 if selected else 1, border_radius=8)
        draw_text(self.screen, self.font_s, text, WHITE if selected else MUTED,
                  rect.center, center=True, shadow=False)

    def draw_menu(self) -> None:
        self.draw_background(THEMES[0], 0)
        for r in (195, 150, 110):
            pygame.draw.circle(self.screen, (23, 65, 84), (WIDTH // 2, 145), r, 2)
        draw_text(self.screen, self.font_xs, "A SMALL GAME ABOUT A WORLD RUNNING OUT OF AIR",
                  CYAN, (WIDTH // 2, 42), center=True, shadow=False)
        language_rect = pygame.Rect(870, 23, 205, 38)
        pygame.draw.rect(self.screen, (9, 25, 42), language_rect, border_radius=7)
        pygame.draw.rect(self.screen, CYAN if self.language == "ru" else (52, 76, 98), language_rect, 1, border_radius=7)
        language_label = "ЯЗЫК: РУССКИЙ" if self.language == "ru" else "LANGUAGE: ENGLISH"
        draw_text(self.screen, self.font_xs, language_label, CYAN, language_rect.center, center=True, shadow=False)
        title = self.font_title.render("OXYGEN", True, WHITE)
        rect = title.get_rect(center=(WIDTH // 2, 125))
        # Keep a restrained one-pixel pink accent instead of a heavy doubled title.
        echo = self.font_title.render("OXYGEN", True, PINK)
        self.screen.blit(echo, (rect.x + 1, rect.y + 1))
        self.screen.blit(title, rect)
        draw_text(self.screen, self.font_s, "BREATHE. CLIMB. SURVIVE.",
                  MUTED, (WIDTH // 2, 188), center=True, shadow=False)
        draw_text(self.screen, self.font_m, f"COINS  {self.total_coins:04d}",
                  YELLOW, (WIDTH // 2, 230), center=True, shadow=False)
        buttons = ["START GAME", "SAFEHOUSE", "LEVEL SELECT", "SALVAGE ARENA",
                   "PERSONNEL", "ACHIEVEMENTS", "RANKINGS", "EXIT GAME"]
        for i, label in enumerate(buttons):
            col, row = i % 2, i // 2
            rect = pygame.Rect(95 + col * 460, 270 + row * 55, 450, 46)
            self.draw_button_at(label, rect, self.menu_selection == i)
        selected_cfg = CHARACTERS[self.character_id]
        draw_text(self.screen, self.font_xs,
                  f"CURRENT RUNNER: {selected_cfg['name']}  //  {selected_cfg['ability']}",
                  selected_cfg["accent"], (WIDTH // 2, 505), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "F11 FULLSCREEN   F3 FPS   ESC QUIT",
                  (80, 102, 130), (WIDTH // 2, 550), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "PLAYER UPGRADES // CREW CONTRACTS // 10 SECTORS",
                  (80, 102, 130), (WIDTH // 2, 576), center=True, shadow=False)

    def draw_character_select(self) -> None:
        self.draw_background(THEMES[1], 1)
        draw_text(self.screen, self.font_xs, "FOUR SIGNALS. FOUR WAYS TO SURVIVE.",
                  CYAN, (WIDTH // 2, 78), center=True, shadow=False)
        draw_text(self.screen, self.font_l, "CHOOSE YOUR RUNNER", WHITE,
                  (WIDTH // 2, 119), center=True)
        for i, character_id in enumerate(CHARACTER_IDS):
            cfg = CHARACTERS[character_id]
            rect = pygame.Rect(48 + i * 250, 160, 230, 350)
            selected = i == self.character_select_selection
            unlocked = self.character_is_unlocked(character_id)
            fill = (17, 35, 55) if selected else (9, 17, 34)
            pygame.draw.rect(self.screen, fill, rect, border_radius=14)
            pygame.draw.rect(self.screen, cfg["accent"] if unlocked else (65, 75, 91),
                             rect, 3 if selected else 1, border_radius=14)
            cx, cy = rect.centerx, 238
            if unlocked:
                draw_glow(self.screen, cx, cy, cfg["accent"], 42 if selected else 30)
            pygame.draw.ellipse(self.screen, (4, 9, 22), (cx - 25, cy - 30, 50, 63))
            pygame.draw.rect(self.screen, (20, 37, 57), (cx - 22, cy - 31, 44, 48), border_radius=13)
            pygame.draw.rect(self.screen, cfg["accent"] if unlocked else MUTED,
                             (cx - 22, cy - 31, 44, 48), 2, border_radius=13)
            pygame.draw.rect(self.screen, (4, 11, 25), (cx - 15, cy - 13, 30, 10), border_radius=4)
            pygame.draw.line(self.screen, cfg["accent2"], (cx - 9, cy - 8), (cx + 9, cy - 8), 3)
            if character_id == "jumper":
                pygame.draw.arc(self.screen, cfg["accent2"], (cx - 37, cy - 50, 74, 37), 0.2, 2.9, 3)
                pygame.draw.arc(self.screen, cfg["accent"], (cx - 37, cy - 50, 74, 37), 3.4, 6.0, 3)
            elif character_id in ("shooter", "flyer"):
                pygame.draw.rect(self.screen, (55, 65, 81), (cx + 13, cy + 5, 26, 9), border_radius=3)
                pygame.draw.rect(self.screen, cfg["accent"], (cx + 33, cy + 7, 7, 4))
                if character_id == "flyer":
                    pygame.draw.polygon(self.screen, cfg["accent2"],
                                        [(cx - 20, cy + 7), (cx - 54, cy - 18), (cx - 13, cy + 25)])
                    pygame.draw.polygon(self.screen, cfg["accent2"],
                                        [(cx + 20, cy + 7), (cx + 54, cy - 18), (cx + 13, cy + 25)])
            else:
                pygame.draw.polygon(self.screen, cfg["accent2"],
                                    [(cx - 17, cy + 16), (cx + 17, cy + 15),
                                     (cx + 31, cy + 29), (cx - 4, cy + 25)])
            draw_text(self.screen, self.font_m, cfg["name"], WHITE,
                      (cx, 313), center=True)
            draw_text(self.screen, self.font_xs, cfg["role"], cfg["accent"] if unlocked else MUTED,
                      (cx, 339), center=True, shadow=False)
            draw_text(self.screen, self.font_s, cfg["ability"], cfg["accent2"],
                      (cx, 374), center=True, shadow=False)
            descriptions = {
                "runner": ("Air dash through", "danger and enemies."),
                "jumper": ("Jump again while", "you are in the air."),
                "shooter": ("Two shots per mob.", "1.3 sec cooldown."),
                "flyer": ("Fly with Space.", "One-shot mobs, 0.5s."),
            }
            for line_i, line in enumerate(descriptions[character_id]):
                draw_text(self.screen, self.font_xs, line, MUTED,
                          (cx, 407 + line_i * 19), center=True, shadow=False)
            badge_text = ("EQUIPPED" if i == self.character_index else "AVAILABLE") if unlocked else "LOCKED // CLEAR 5 + BOSS"
            badge_color = cfg["accent"] if unlocked and (selected or i == self.character_index) else MUTED
            draw_text(self.screen, self.font_xs, badge_text, badge_color,
                      (cx, 475), center=True, shadow=False)
        self.draw_button("BACK TO PERSONNEL", 526, False, width=340)
        draw_text(self.screen, self.font_xs,
                  "LEFT / RIGHT TO PREVIEW   ENTER TO EQUIP   CLICK A CHARACTER",
                  MUTED, (WIDTH // 2, 590), center=True, shadow=False)

    def draw_level_select(self) -> None:
        safe_index = min(self.level_select_selection, len(THEMES) - 1)
        theme = THEMES[safe_index]
        self.draw_background(theme, safe_index)
        draw_text(self.screen, self.font_xs, "CLEAR A SECTOR TO OPEN THE NEXT",
                  theme["accent"], (WIDTH // 2, 78), center=True, shadow=False)
        draw_text(self.screen, self.font_l, "LEVEL SELECT", WHITE,
                  (WIDTH // 2, 118), center=True)
        for i, data in enumerate(LEVELS):
            unlocked = self.level_is_unlocked(i)
            col, row = i // 5, i % 5
            rect = pygame.Rect(190 + col * 390, 180 + row * 62, 350, 48)
            label = f"0{i + 1}  //  {data['name']}" if unlocked else f"LOCKED  //  0{i + 1}"
            self.draw_button_at(label, rect, self.level_select_selection == i)
        self.draw_button("BACK TO MENU", 510, False, width=290)
        if self.menu_notice_timer > 0:
            draw_text(self.screen, self.font_xs, self.menu_notice, YELLOW,
                      (WIDTH // 2, 568), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "UP / DOWN TO SELECT     ENTER TO DEPLOY     ESC TO RETURN",
                  MUTED, (WIDTH // 2, 594), center=True, shadow=False)

    def draw_skills(self) -> None:
        self.draw_background(THEMES[5], 5)
        draw_text(self.screen, self.font_xs, f"AVAILABLE CURRENCY  //  {self.total_coins:04d} COINS",
                  YELLOW, (WIDTH // 2, 85), center=True, shadow=False)
        draw_text(self.screen, self.font_l, "SKILL TREE", WHITE, (WIDTH // 2, 135), center=True)
        for i, (skill_id, title, cost, desc) in enumerate(SKILL_NODES):
            col, row = i % 2, i // 2
            rect = pygame.Rect(145 + col * 405, 210 + row * 125, 365, 105)
            owned = bool(self.save_data["skills"].get(skill_id))
            selected = self.skill_selection == i
            pygame.draw.rect(self.screen, (16, 32, 52) if selected else (8, 18, 34), rect, border_radius=10)
            pygame.draw.rect(self.screen, CYAN if selected else (52, 75, 99), rect, 2 if selected else 1, border_radius=10)
            draw_text(self.screen, self.font_m, title, WHITE, (rect.x + 18, rect.y + 13), shadow=False)
            draw_text(self.screen, self.font_xs, "UNLOCKED" if owned else f"COST  {cost} COINS",
                      CYAN if owned else YELLOW, (rect.x + 18, rect.y + 47), shadow=False)
            draw_text(self.screen, self.font_xs, desc, MUTED, (rect.x + 18, rect.y + 77), shadow=False)
        back = pygame.Rect(WIDTH // 2 - 145, 490, 290, 48)
        self.draw_button_at("BACK TO PERSONNEL", back, self.skill_selection == len(SKILL_NODES))
        if self.menu_notice_timer > 0:
            draw_text(self.screen, self.font_xs, self.menu_notice, YELLOW,
                      (WIDTH // 2, 558), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "UP / DOWN + ENTER TO UNLOCK  //  ESC TO PERSONNEL",
                  MUTED, (WIDTH // 2, 594), center=True, shadow=False)

    def draw_achievements(self) -> None:
        self.draw_background(THEMES[9], 9)
        unlocked = set(self.save_data["achievements"])
        draw_text(self.screen, self.font_l, "ACHIEVEMENTS", WHITE, (WIDTH // 2, 90), center=True)
        draw_text(self.screen, self.font_xs, f"UNLOCKED  //  {len(unlocked)} / {len(ACHIEVEMENTS)}",
                  THEMES[9]["accent"], (WIDTH // 2, 132), center=True, shadow=False)
        visible = ACHIEVEMENTS[self.achievement_scroll:self.achievement_scroll + 7]
        for i, (achievement_id, title, desc) in enumerate(visible):
            y = 166 + i * 48
            is_unlocked = achievement_id in unlocked
            rect = pygame.Rect(170, y, 760, 42)
            pygame.draw.rect(self.screen, (16, 38, 50) if is_unlocked else (8, 17, 32), rect, border_radius=7)
            pygame.draw.rect(self.screen, CYAN if is_unlocked else (43, 57, 78), rect, 1, border_radius=7)
            draw_text(self.screen, self.font_s, ("◆  " if is_unlocked else "◇  ") + title,
                      CYAN if is_unlocked else MUTED, (rect.x + 16, rect.y + 5), shadow=False)
            draw_text(self.screen, self.font_xs, desc, MUTED, (rect.x + 360, rect.y + 13), shadow=False)
            reward_state = "PAID" if achievement_id in self.save_data.get("achievement_rewards", []) else "+5 COINS"
            draw_text(self.screen, self.font_xs, reward_state, YELLOW if is_unlocked else MUTED,
                      (rect.right - 72, rect.y + 13), shadow=False)
        self.draw_button("BACK TO MENU", 545, False, width=290)
        draw_text(self.screen, self.font_xs, "MOUSE WHEEL / UP / DOWN TO SCROLL  //  ESC TO RETURN",
                  MUTED, (WIDTH // 2, 594), center=True, shadow=False)

    def draw_store(self) -> None:
        self.draw_background(THEMES[3], 3)
        draw_text(self.screen, self.font_xs, "PERSONNEL // PERMANENT RUNNER UPGRADES",
                  THEMES[3]["accent"], (WIDTH // 2, 105), center=True, shadow=False)
        draw_text(self.screen, self.font_l, "FIELD TRAINING", WHITE,
                  (WIDTH // 2, 145), center=True)
        draw_text(self.screen, self.font_m, f"WALLET  {self.total_coins:04d} COINS",
                  YELLOW, (WIDTH // 2, 195), center=True, shadow=False)
        speed_level = self.save_data["speed_level"]
        strength_level = self.save_data["strength_level"]
        speed_costs = (25, 40, 60)
        strength_costs = (30, 45)
        speed_text = f"MAX LEVEL" if speed_level >= 3 else f"COST  {speed_costs[speed_level]} COINS"
        power_text = f"MAX LEVEL" if strength_level >= 2 else f"COST  {strength_costs[strength_level]} COINS"
        cards = [
            (0, "RUN SPEED", f"LEVEL {speed_level} / 3", speed_text,
             "Move faster through every sector."),
            (1, "STOMP POWER", f"LEVEL {strength_level} / 2", power_text,
             "At max level, one stomp kills a mob."),
        ]
        for item_i, title, level_text, price_text, desc in cards:
            y = 250 + item_i * 112
            selected = self.store_selection == item_i
            rect = pygame.Rect(WIDTH // 2 - 250, y, 500, 92)
            pygame.draw.rect(self.screen, (17, 35, 52) if selected else (8, 18, 34), rect, border_radius=10)
            pygame.draw.rect(self.screen, CYAN if selected else (52, 75, 99), rect, 2 if selected else 1, border_radius=10)
            draw_text(self.screen, self.font_m, title, WHITE, (rect.x + 18, rect.y + 12), shadow=False)
            draw_text(self.screen, self.font_xs, level_text + "  //  " + price_text,
                      YELLOW if "MAX" not in price_text else MUTED,
                      (rect.x + 18, rect.y + 43), shadow=False)
            draw_text(self.screen, self.font_xs, desc, MUTED,
                      (rect.centerx, rect.y + 73), center=True, shadow=False)
        self.draw_button("BACK TO PERSONNEL", 480, self.store_selection == 2, width=340)
        if self.menu_notice_timer > 0:
            draw_text(self.screen, self.font_xs, self.menu_notice, YELLOW,
                      (WIDTH // 2, 555), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "UP / DOWN + ENTER TO BUY   //   ESC TO PERSONNEL",
                  MUTED, (WIDTH // 2, 590), center=True, shadow=False)

    def draw_hub_npc(self, x: int, y: int, color, name: str, role: str) -> None:
        """Distinct silhouettes for the three crew members who issue contracts."""
        draw_glow(self.screen, x, y - 45, color, 28)
        pygame.draw.ellipse(self.screen, (3, 7, 18), (x - 22, y - 5, 44, 10))
        if name == "RHEA":  # engineer: heavy work coat, goggles and tool belt
            pygame.draw.rect(self.screen, (30, 54, 67), (x - 18, y - 52, 36, 47), border_radius=8)
            pygame.draw.polygon(self.screen, (55, 92, 102), [(x-18,y-42),(x-29,y-8),(x-16,y-5),(x-8,y-34)])
            pygame.draw.polygon(self.screen, (55, 92, 102), [(x+18,y-42),(x+29,y-8),(x+16,y-5),(x+8,y-34)])
            pygame.draw.circle(self.screen, (184, 142, 104), (x, y-66), 15)
            pygame.draw.arc(self.screen, (230, 178, 95), (x-16,y-82,32,23), 3.1, 6.2, 5)
            pygame.draw.rect(self.screen, (11, 23, 35), (x-12,y-70,24,8), border_radius=3)
            pygame.draw.circle(self.screen, color, (x-6,y-66), 3)
            pygame.draw.circle(self.screen, color, (x+6,y-66), 3)
            pygame.draw.rect(self.screen, (232, 166, 74), (x-14,y-17,28,7), border_radius=2)
            pygame.draw.line(self.screen, (222, 233, 233), (x+12,y-26), (x+23,y-42), 3)
        elif name == "MARA":  # electrician: insulated coat and a glowing power tool
            pygame.draw.rect(self.screen, (42, 57, 55), (x - 18, y - 52, 36, 47), border_radius=8)
            pygame.draw.polygon(self.screen, (70, 91, 77),
                                [(x - 18, y - 43), (x - 27, y - 8), (x - 13, y - 5), (x - 7, y - 34)])
            pygame.draw.polygon(self.screen, (70, 91, 77),
                                [(x + 18, y - 43), (x + 27, y - 8), (x + 13, y - 5), (x + 7, y - 34)])
            pygame.draw.circle(self.screen, (190, 153, 119), (x, y - 66), 15)
            pygame.draw.rect(self.screen, (17, 27, 34), (x - 14, y - 72, 28, 8), border_radius=3)
            pygame.draw.line(self.screen, color, (x - 10, y - 66), (x + 10, y - 66), 3)
            pygame.draw.rect(self.screen, (35, 47, 49), (x + 17, y - 29, 12, 22), border_radius=3)
            pygame.draw.circle(self.screen, color, (x + 23, y - 32), 4)
        elif name == "NOX":  # quartermaster: hood, mask and supply harness
            pygame.draw.polygon(self.screen, (35, 36, 70), [(x-24,y-43),(x-17,y-73),(x,y-84),(x+18,y-72),(x+24,y-43),(x+18,y-6),(x-18,y-6)])
            pygame.draw.circle(self.screen, (161, 132, 116), (x, y-65), 14)
            pygame.draw.rect(self.screen, (11, 18, 35), (x-14,y-70,28,10), border_radius=4)
            pygame.draw.rect(self.screen, color, (x-12,y-57,24,8), border_radius=3)
            pygame.draw.line(self.screen, (119, 105, 160), (x-18,y-42), (x+18,y-11), 4)
            pygame.draw.line(self.screen, (119, 105, 160), (x+18,y-42), (x-18,y-11), 4)
            pygame.draw.rect(self.screen, (20, 28, 47), (x-23,y-24,11,16), border_radius=3)
            pygame.draw.rect(self.screen, (20, 28, 47), (x+12,y-24,11,16), border_radius=3)
        else:  # Drifter: long scarf, asymmetrical hood and scout visor
            pygame.draw.rect(self.screen, (28, 48, 50), (x-17,y-51,34,46), border_radius=9)
            pygame.draw.polygon(self.screen, (38, 65, 66), [(x-18,y-53),(x-22,y-77),(x,y-87),(x+22,y-70),(x+17,y-50)])
            pygame.draw.circle(self.screen, (177, 145, 117), (x, y-65), 14)
            pygame.draw.rect(self.screen, (5, 16, 26), (x-14,y-70,28,9), border_radius=4)
            pygame.draw.line(self.screen, color, (x-13,y-65), (x+13,y-65), 3)
            pygame.draw.polygon(self.screen, color, [(x-14,y-31),(x+12,y-28),(x+31,y-14),(x+12,y-20),(x-18,y-21)])
            pygame.draw.rect(self.screen, (18, 30, 43), (x+8,y-18,15,11), border_radius=3)
        pygame.draw.rect(self.screen, (38, 57, 76), (x-14,y-5,10,8), border_radius=3)
        pygame.draw.rect(self.screen, (38, 57, 76), (x+4,y-5,10,8), border_radius=3)
        draw_text(self.screen, self.font_xs, name, WHITE, (x, y + 12), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, role, color, (x, y + 31), center=True, shadow=False)

    def draw_safehouse(self) -> None:
        theme = THEMES[5]
        self.draw_background(theme, 5)
        pygame.draw.rect(self.screen, (6, 15, 29), (25, 72, 1050, 465), border_radius=20)
        pygame.draw.rect(self.screen, (47, 89, 116), (25, 72, 1050, 465), 2, border_radius=20)
        pygame.draw.rect(self.screen, (13, 29, 47), (40, 500, 1020, 38), border_radius=6)
        pygame.draw.line(self.screen, (54, 119, 144), (40, 500), (1060, 500), 3)
        # Compact maintenance lift route: all steps stay left of the MOD BAY.
        for platform in self.safehouse_world.solids[3:7]:
            r = platform.copy()
            pygame.draw.rect(self.screen, (13, 34, 54), r, border_radius=4)
            pygame.draw.line(self.screen, CYAN_DARK, (r.left + 4, r.top), (r.right - 4, r.top), 3)
            for bolt_x in range(r.left + 12, r.right - 8, 34):
                pygame.draw.circle(self.screen, (71, 125, 148), (bolt_x, r.top + 7), 2)
        for x in (120, 400, 690, 970):
            pygame.draw.line(self.screen, (30, 69, 94), (x, 125), (x, 458), 2)
            pygame.draw.circle(self.screen, (58, 160, 173), (x, 130), 5)
        # Purifier is mounted high on its own service deck, with a clear walkable landing.
        pygame.draw.rect(self.screen, (12, 31, 49), (462, 82, 166, 105), border_radius=14)
        pygame.draw.rect(self.screen, CYAN_DARK, (462, 82, 166, 105), 2, border_radius=14)
        draw_glow(self.screen, 545, 128, CYAN, 42)
        pygame.draw.circle(self.screen, (10, 36, 56), (545, 128), 37)
        pygame.draw.circle(self.screen, CYAN, (545, 128), 30, 3)
        pygame.draw.arc(self.screen, WHITE, (519, 102, 52, 52), self.time * 0.7, self.time * 0.7 + 4.2, 3)
        pygame.draw.rect(self.screen, (6, 19, 34), (492, 166, 106, 12), border_radius=5)
        charge = int(self.save_data.get("filter_charge", 0))
        pygame.draw.rect(self.screen, (34, 58, 76), (499, 169, 92, 6), border_radius=3)
        if charge:
            pygame.draw.rect(self.screen, CYAN, (499, 169, int(92 * charge / 100), 6), border_radius=3)
        filter_status = "BUFFER READY // +1 HP NEXT RUN" if self.save_data.get("filter_boost") else f"CHARGE {charge}% // 8 COINS = +25%"
        draw_text(self.screen, self.font_xs, "OXYGEN FILTER", CYAN,
                  (545, 202), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, filter_status, MUTED,
                  (545, 218), center=True, shadow=False)
        # Airlock on the left; crew members are the actual quest-givers.
        gate_x = self.hub_gate_x
        draw_glow(self.screen, gate_x, 450, CYAN, 38)
        pygame.draw.rect(self.screen, (8, 23, 39), (gate_x - 33, 365, 66, 135), border_radius=10)
        pygame.draw.rect(self.screen, CYAN_DARK, (gate_x - 33, 365, 66, 135), 2, border_radius=10)
        pygame.draw.rect(self.screen, (14, 50, 67), (gate_x - 22, 382, 44, 118), border_radius=7)
        pygame.draw.line(self.screen, CYAN, (gate_x - 14, 402), (gate_x + 14, 402), 2)
        draw_text(self.screen, self.font_xs, "AIRLOCK", CYAN, (gate_x, 480), center=True, shadow=False)
        self.draw_hub_npc(self.hub_npc_positions[0], 500, (85, 231, 210), "RHEA", "ENGINEER")
        self.draw_hub_npc(self.hub_npc_positions[1], 500, (176, 132, 255), "NOX", "SUPPLY KEEPER")
        self.draw_hub_npc(self.hub_npc_positions[2], 500, (255, 170, 91), "DRIFTER", "SCOUT")
        if len(set(self.save_data.get("completed_levels", []))) >= 3:
            self.draw_hub_npc(self.hub_npc_positions[3], 500, (255, 220, 126),
                              "MARA", "ELECTRICIAN")
        # Overhead power conduit and three soft-flickering utility lamps.
        pygame.draw.line(self.screen, (28, 66, 89), (72, 144), (1028, 144), 5)
        pygame.draw.line(self.screen, (65, 111, 129), (72, 149), (1028, 149), 1)
        lights_restored = self.save_data.get("safehouse_lighting_upgraded", False)
        lamp_positions = (185, 735, 930, 350, 845) if lights_restored else (185, 735, 930)
        for lamp_index, lamp_x in enumerate(lamp_positions):
            pulse = 0.72 + 0.28 * math.sin(self.time * 1.7 + lamp_index * 1.9)
            brightness = 1.28 if lights_restored else 1.0
            lamp_color = (min(255, int((66 + 38 * pulse) * brightness)),
                          min(255, int((148 + 70 * pulse) * brightness)),
                          min(255, int((166 + 60 * pulse) * brightness)))
            draw_glow(self.screen, lamp_x, 168, lamp_color, int((18 + 9 * pulse) * brightness))
            pygame.draw.line(self.screen, (62, 93, 112), (lamp_x, 145), (lamp_x, 158), 3)
            pygame.draw.rect(self.screen, (28, 59, 75), (lamp_x - 10, 157, 20, 8), border_radius=3)
            pygame.draw.circle(self.screen, lamp_color, (lamp_x, 166), 4)
        # Ventilation fan slowly turns above the crew's living area.
        pygame.draw.circle(self.screen, (30, 61, 79), (330, 205), 24, 4)
        for blade in range(4):
            angle = self.time * 1.15 + blade * math.pi / 2
            end = (330 + int(math.cos(angle) * 19), 205 + int(math.sin(angle) * 19))
            pygame.draw.line(self.screen, (83, 133, 151), (330, 205), end, 5)
        pygame.draw.circle(self.screen, CYAN_DARK, (330, 205), 5)
        # Bunk and lockers: the shelter should look inhabited, not like a lobby.
        pygame.draw.rect(self.screen, (16, 34, 51), (145, 425, 100, 63), border_radius=7)
        pygame.draw.rect(self.screen, (71, 104, 122), (145, 425, 100, 63), 2, border_radius=7)
        pygame.draw.rect(self.screen, (81, 114, 129), (153, 432, 83, 14), border_radius=5)
        pygame.draw.rect(self.screen, (31, 55, 72), (152, 450, 85, 31), border_radius=4)
        pygame.draw.line(self.screen, (91, 132, 146), (153, 484), (239, 484), 4)
        for locker_x in (300, 345):
            pygame.draw.rect(self.screen, (15, 31, 49), (locker_x, 410, 34, 88), border_radius=4)
            pygame.draw.rect(self.screen, (53, 92, 113), (locker_x, 410, 34, 88), 1, border_radius=4)
            pygame.draw.line(self.screen, (84, 130, 145), (locker_x + 7, 436), (locker_x + 27, 436), 2)
            pygame.draw.circle(self.screen, YELLOW, (locker_x + 27, 450), 2)
        # Radio receiver scans for a carrier in the background.
        radio_pulse = 0.5 + 0.5 * math.sin(self.time * 3.1)
        pygame.draw.rect(self.screen, (7, 19, 32), (805, 286, 112, 70), border_radius=7)
        pygame.draw.rect(self.screen, (57, 100, 122), (805, 286, 112, 70), 2, border_radius=7)
        pygame.draw.rect(self.screen, (2, 10, 20), (816, 298, 70, 34), border_radius=3)
        for bar in range(7):
            h = 4 + int((3 + 5 * radio_pulse) * abs(math.sin(self.time * 2.0 + bar)))
            pygame.draw.line(self.screen, CYAN, (823 + bar * 8, 325), (823 + bar * 8, 325 - h), 2)
        pygame.draw.circle(self.screen, (int(70 + radio_pulse * 120), 220, 180), (899, 307), 4)
        draw_text(self.screen, self.font_xs, "RADIO // SCAN", MUTED, (861, 365), center=True, shadow=False)
        # 167 access panel, sealed until the end-of-campaign transmission.
        pygame.draw.rect(self.screen, (5, 17, 31), (378, 365, 64, 135), border_radius=8)
        door_color = (92, 220, 199) if self.save_data.get("secret_167_unlocked", False) else (73, 92, 111)
        pygame.draw.rect(self.screen, door_color, (378, 365, 64, 135), 2, border_radius=8)
        pygame.draw.rect(self.screen, (14, 39, 54), (387, 377, 46, 123), border_radius=5)
        pygame.draw.circle(self.screen, door_color, (427, 438), 3)
        draw_text(self.screen, self.font_xs,
                  "167 // OPEN" if self.save_data.get("secret_167_unlocked", False) else "167 // SEALED",
                  door_color, (410, 480), center=True, shadow=False)
        # Trophy shelf grows with major campaign milestones.
        trophies = []
        if self.save_data.get("boss_cleared"):
            trophies.append(("CORE", (255, 188, 91)))
        if len(set(self.save_data.get("completed_levels", []))) >= 3:
            trophies.append(("SECTOR", (91, 220, 190)))
        if self.save_data.get("postgame_event_seen"):
            trophies.append(("167", (166, 139, 255)))
        if trophies:
            pygame.draw.rect(self.screen, (10, 25, 39), (718, 410, 94, 90), border_radius=6)
            pygame.draw.rect(self.screen, (60, 100, 117), (718, 410, 94, 90), 1, border_radius=6)
            for trophy_i, (label, tint) in enumerate(trophies[:3]):
                tx = 735 + trophy_i * 27
                draw_glow(self.screen, tx, 444, tint, 13)
                pygame.draw.polygon(self.screen, tint, [(tx, 427), (tx + 9, 436), (tx + 6, 451), (tx - 6, 451), (tx - 9, 436)])
                pygame.draw.rect(self.screen, (112, 126, 133), (tx - 5, 452, 10, 5))
                draw_text(self.screen, self.font_xs, label, tint, (tx, 470), center=True, shadow=False)
            draw_text(self.screen, self.font_xs, "FIELD RELICS", MUTED, (765, 493), center=True, shadow=False)
        # Physical EXP cassette deck. Its transport controls are real; sound is added later.
        pygame.draw.rect(self.screen, (10, 24, 39), (610, 422, 92, 78), border_radius=8)
        pygame.draw.rect(self.screen, (59, 105, 125), (610, 422, 92, 78), 2, border_radius=8)
        pygame.draw.rect(self.screen, (2, 10, 20), (620, 431, 72, 34), border_radius=4)
        pygame.draw.circle(self.screen, CYAN, (629, 448), 3)
        pygame.draw.circle(self.screen, YELLOW if self.cassette_playing else MUTED, (684, 448), 3)
        pygame.draw.line(self.screen, (72, 120, 140), (625, 472), (687, 472), 2)
        draw_text(self.screen, self.font_xs, "EXP TAPE DECK", CYAN, (656, 487), center=True, shadow=False)
        # Small dust motes in the utility lights; no per-frame random allocation.
        for mote in range(18):
            mx = 55 + int((mote * 67 + self.time * (9 + mote % 4)) % 980)
            my = 235 + int((mote * 43 + math.sin(self.time * 0.55 + mote) * 12) % 220)
            pygame.draw.circle(self.screen, (66, 101, 121), (mx, my), 1)
        # Ability module station remains on the far right.
        draw_glow(self.screen, self.hub_armory_x, 447, (255, 190, 90), 34)
        pygame.draw.rect(self.screen, (14, 28, 45), (self.hub_armory_x - 38, 395, 76, 103), border_radius=9)
        pygame.draw.rect(self.screen, (255, 190, 90), (self.hub_armory_x - 38, 395, 76, 103), 2, border_radius=9)
        pygame.draw.rect(self.screen, (4, 14, 27), (self.hub_armory_x - 27, 410, 54, 48), border_radius=4)
        pygame.draw.line(self.screen, (255, 190, 90), (self.hub_armory_x - 17, 425), (self.hub_armory_x + 17, 425), 3)
        pygame.draw.line(self.screen, (255, 190, 90), (self.hub_armory_x - 17, 438), (self.hub_armory_x + 17, 438), 3)
        draw_text(self.screen, self.font_xs, "MOD BAY", YELLOW, (self.hub_armory_x, 480), center=True, shadow=False)
        self.player.draw(self.screen, 0)
        for shot in self.projectiles:
            draw_projectile(self.screen, shot, 0)
        for particle in self.particles:
            particle.draw(self.screen, 0)
        draw_text(self.screen, self.font_l, "OXYGEN // SAFEHOUSE", WHITE, (WIDTH // 2, 48), center=True)
        draw_text(self.screen, self.font_xs, "MOVE  //  JUMP  //  CHARACTER ABILITIES WORK HERE  //  E TO INTERACT",
                  CYAN, (WIDTH // 2, 92), center=True, shadow=False)
        if self.safehouse_interaction_hint:
            draw_text(self.screen, self.font_s, self.safehouse_interaction_hint, YELLOW,
                      (self.player.x + self.player.w // 2, max(145, self.player.y - 24)), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, f"WALLET  {self.total_coins:04d} COINS",
                  YELLOW, (WIDTH - 130, 585), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "AIRLOCK // DEPLOY", MUTED,
                  (95, 585), center=True, shadow=False)
        draw_text(self.screen, self.font_xs,
                  f"EXP ARCHIVE  //  {len(self.collected_cassette_ids())}/10",
                  THEMES[5]["accent"], (WIDTH // 2, 585), center=True, shadow=False)
        if self.menu_notice_timer > 0:
            draw_text(self.screen, self.font_xs, self.menu_notice, YELLOW,
                      (WIDTH // 2, 552), center=True, shadow=False)

    def draw_cassette_prop(self, surface: pygame.Surface, x: int, y: int,
                           accent: tuple[int, int, int], scale: float = 1.0,
                           animation_time: float = 0.0) -> None:
        width, height = max(18, int(48 * scale)), max(14, int(32 * scale))
        left, top = x - width // 2, y - height // 2
        radius = max(2, int(5 * scale))
        pygame.draw.rect(surface, (1, 7, 15),
                         (left - 2, top - 2, width + 4, height + 4), border_radius=radius)
        pygame.draw.rect(surface, (29, 43, 57), (left, top, width, height), border_radius=radius)
        pygame.draw.rect(surface, (93, 118, 133), (left, top, width, height), 1, border_radius=radius)
        pygame.draw.rect(surface, accent,
                         (left + int(5 * scale), top + int(4 * scale),
                          max(4, width - int(10 * scale)), max(3, int(6 * scale))),
                         border_radius=2)
        reel_y = top + int(height * 0.66)
        reel_radius = max(3, int(6 * scale))
        for reel_x in (left + int(width * 0.31), left + int(width * 0.69)):
            pygame.draw.circle(surface, (4, 12, 21), (reel_x, reel_y), reel_radius)
            pygame.draw.circle(surface, (122, 145, 156), (reel_x, reel_y), max(2, reel_radius - 2), 1)
            angle = animation_time * (5.0 if self.cassette_playing else 0.45)
            spoke_x = reel_x + int(math.cos(angle) * max(1, reel_radius - 2))
            spoke_y = reel_y + int(math.sin(angle) * max(1, reel_radius - 2))
            pygame.draw.line(surface, accent, (reel_x, reel_y), (spoke_x, spoke_y), 1)
        pygame.draw.line(surface, (151, 169, 177),
                         (left + int(width * 0.37), top + int(height * 0.69)),
                         (left + int(width * 0.63), top + int(height * 0.69)), 1)

    def draw_cassette_deck(self) -> None:
        self.draw_background(THEMES[5], 5)
        self.screen.fill((4, 9, 20), special_flags=pygame.BLEND_RGBA_MULT)
        tapes = self.collected_cassette_ids()
        selected_id = tapes[self.cassette_selection] if tapes else None
        draw_text(self.screen, self.font_l, "EXP // CASSETTE ARCHIVE", WHITE,
                  (WIDTH // 2, 58), center=True)
        draw_text(self.screen, self.font_xs, "RECOVERED MEDIA // PERSONAL ARCHIVE NODE",
                  CYAN, (WIDTH // 2, 101), center=True, shadow=False)
        for index in range(10):
            col, row = index % 5, index // 5
            rect = pygame.Rect(65 + col * 198, 145 + row * 112, 184, 94)
            collected = str(index) in tapes
            selected = str(index) == selected_id
            pygame.draw.rect(self.screen, (20, 43, 59) if selected else (9, 22, 39),
                             rect, border_radius=8)
            pygame.draw.rect(self.screen, CYAN if selected else (52, 82, 104),
                             rect, 2 if selected else 1, border_radius=8)
            if collected:
                self.draw_cassette_prop(self.screen, rect.x + 42, rect.centery,
                                        THEMES[index]["accent"], 0.76, self.time)
                title, state, color = f"EXP // {index + 1:02d}", "RECOVERED", WHITE
            else:
                pygame.draw.rect(self.screen, (22, 31, 43),
                                 (rect.x + 17, rect.y + 24, 50, 42), border_radius=5)
                pygame.draw.line(self.screen, (57, 67, 83), (rect.x + 23, rect.y + 36),
                                 (rect.x + 61, rect.y + 36), 2)
                title, state, color = f"EXP // {index + 1:02d}", "NO SIGNAL", MUTED
            draw_text(self.screen, self.font_s, title, color, (rect.x + 78, rect.y + 23), shadow=False)
            draw_text(self.screen, self.font_xs, state, CYAN if collected else MUTED,
                      (rect.x + 78, rect.y + 54), shadow=False)
        deck = pygame.Rect(250, 386, 600, 150)
        pygame.draw.rect(self.screen, (7, 18, 31), deck, border_radius=12)
        pygame.draw.rect(self.screen, (67, 111, 132), deck, 2, border_radius=12)
        pygame.draw.rect(self.screen, (2, 8, 16), (deck.x + 22, deck.y + 20, 238, 110), border_radius=8)
        if selected_id is not None:
            self.draw_cassette_prop(self.screen, deck.x + 141, deck.y + 75,
                                    THEMES[int(selected_id)]["accent"], 2.45, self.time)
            draw_text(self.screen, self.font_m, f"EXP // {int(selected_id) + 1:02d}",
                      WHITE, (deck.x + 320, deck.y + 44), shadow=False)
            status = ("DECK MOTOR RUNNING // AUDIO NOT INSTALLED"
                      if self.cassette_playing else "CASSETTE READY // SELECT PLAY")
            draw_text(self.screen, self.font_xs, status,
                      CYAN if self.cassette_playing else MUTED,
                      (deck.x + 320, deck.y + 83), shadow=False)
            draw_text(self.screen, self.font_s,
                      "STOP DECK" if self.cassette_playing else "START DECK",
                      YELLOW, (deck.x + 320, deck.y + 108), shadow=False)
        else:
            draw_text(self.screen, self.font_m, "NO EXP TAPES FOUND", WHITE,
                      (deck.x + 300, deck.y + 55), center=True)
            draw_text(self.screen, self.font_xs, "SEARCH THE TEN CAMPAIGN SECTORS",
                      MUTED, (deck.x + 300, deck.y + 88), center=True, shadow=False)
        draw_text(self.screen, self.font_xs,
                  f"ARCHIVE // {len(tapes):02d} OF 10 RECOVERED",
                  CYAN, (WIDTH // 2, 563), center=True, shadow=False)
        draw_text(self.screen, self.font_xs,
                  "LEFT / RIGHT: SELECT TAPE  //  ENTER: START / STOP  //  ESC: SAFEHOUSE",
                  MUTED, (WIDTH // 2, 595), center=True, shadow=False)

    def draw_secret_room_167(self) -> None:
        self.screen.fill((2, 5, 15))
        for x in range(45, WIDTH, 85):
            pygame.draw.line(self.screen, (13, 29, 43), (x, 40), (x, HEIGHT - 42), 1)
        for y in range(50, HEIGHT, 54):
            pygame.draw.line(self.screen, (10, 24, 38), (35, y), (WIDTH - 35, y), 1)
        for rack_x in (72, 150, 872, 950):
            pygame.draw.rect(self.screen, (8, 19, 32), (rack_x, 124, 52, 374), border_radius=5)
            pygame.draw.rect(self.screen, (44, 83, 103), (rack_x, 124, 52, 374), 1, border_radius=5)
            for shelf_y in range(145, 475, 42):
                pygame.draw.line(self.screen, (41, 77, 96), (rack_x + 8, shelf_y),
                                 (rack_x + 44, shelf_y), 2)
                led = (80, 218, 190) if (shelf_y // 42 + rack_x) % 3 else (255, 176, 84)
                pygame.draw.circle(self.screen, led, (rack_x + 14, shelf_y - 8), 2)
        draw_glow(self.screen, WIDTH // 2, 244, (58, 202, 190), 85)
        pygame.draw.rect(self.screen, (5, 15, 28), (260, 120, 580, 290), border_radius=12)
        pygame.draw.rect(self.screen, (65, 137, 151), (260, 120, 580, 290), 2, border_radius=12)
        pygame.draw.rect(self.screen, (1, 8, 16), (286, 148, 528, 218), border_radius=7)
        pulse = 0.72 + 0.28 * math.sin(self.time * 2.4)
        signal_color = (int(45 + 40 * pulse), int(220 + 28 * pulse), int(182 + 35 * pulse))
        pygame.draw.rect(self.screen, (12, 42, 50), (310, 170, 480, 174), 1, border_radius=4)
        draw_text(self.screen, self.font_l, "ROOM 167", signal_color, (WIDTH // 2, 203), center=True)
        logs = (
            "LOG 01 // THE SIGNAL ARRIVED 167 SECONDS BEFORE THE FIRST FAILURE.",
            "LOG 02 // THE SHELTER WAS BUILT AROUND THIS ROOM.",
            "LOG 03 // IF YOU FOUND THIS, THE ARCHIVE FOUND YOU FIRST.",
        )
        draw_text(self.screen, self.font_s, logs[self.secret_167_page], WHITE,
                  (WIDTH // 2, 277), center=True, shadow=False)
        found = self.collected_cassette_ids()
        for index in range(10):
            col, row = index % 5, index // 5
            self.draw_cassette_prop(
                self.screen, 330 + col * 88, 390 + row * 42,
                THEMES[index]["accent"] if str(index) in found else (42, 54, 69),
                0.52, self.time)
        draw_text(self.screen, self.font_xs, f"ARCHIVE FRAGMENTS // {len(found)}/10",
                  CYAN, (WIDTH // 2, 490), center=True, shadow=False)
        draw_text(self.screen, self.font_xs,
                  "LEFT / RIGHT OR ENTER: CYCLE LOG  //  E / ESC: RETURN TO SAFEHOUSE",
                  MUTED, (WIDTH // 2, 585), center=True, shadow=False)

    def draw_167_signal_event(self) -> None:
        elapsed = self.safehouse_event_elapsed
        self.screen.fill((1, 3, 10))
        if elapsed < 1.35:
            draw_text(self.screen, self.font_l, "POWER FAILURE", (174, 194, 207),
                      (WIDTH // 2, HEIGHT // 2), center=True)
            draw_text(self.screen, self.font_xs, "SAFEHOUSE GRID // OFFLINE",
                      MUTED, (WIDTH // 2, HEIGHT // 2 + 44), center=True, shadow=False)
        elif elapsed < 3.7:
            draw_text(self.screen, self.font_m, "RADIO // UNKNOWN CARRIER",
                      (156, 220, 205), (WIDTH // 2, 238), center=True)
            wave_y = 315
            for index in range(49):
                wave_x = 250 + index * 12
                wave_h = int(7 + 22 * abs(math.sin(index * 0.57 + elapsed * 7.0))
                             * (0.45 + 0.55 * abs(math.sin(index * 0.13 + elapsed))))
                pygame.draw.line(self.screen, CYAN, (wave_x, wave_y - wave_h),
                                 (wave_x, wave_y + wave_h), 2)
            draw_text(self.screen, self.font_xs, "UNKNOWN RECORDING // 00:00:17",
                      WHITE, (WIDTH // 2, 368), center=True, shadow=False)
        else:
            flicker = int(32 * abs(math.sin(elapsed * 23.0)))
            signal = (max(25, 54 + flicker), min(255, 220 + flicker), min(255, 195 + flicker))
            pygame.draw.rect(self.screen, (1, 12, 21), (220, 165, 660, 270), border_radius=12)
            pygame.draw.rect(self.screen, signal, (220, 165, 660, 270), 2, border_radius=12)
            pygame.draw.rect(self.screen, (4, 25, 34), (246, 190, 608, 220), border_radius=7)
            for scan_y in range(198, 405, 8):
                pygame.draw.line(self.screen, (13, 47, 55), (253, scan_y), (847, scan_y), 1)
            draw_text(self.screen, self.font_s, "INCOMING TRANSMISSION // NODE 167",
                      signal, (WIDTH // 2, 244), center=True, shadow=False)
            draw_text(self.screen, self.font_l, "167 SIGNAL DETECTED",
                      WHITE, (WIDTH // 2, 302), center=True)
            draw_text(self.screen, self.font_xs, "ARCHIVE LOCK // RELEASED",
                      CYAN, (WIDTH // 2, 365), center=True, shadow=False)

    def draw_safehouse_dialog(self) -> None:
        if self.safehouse_dialog_npc is None:
            return
        quest = QUESTS[self.safehouse_dialog_npc]
        idx = self.safehouse_dialog_npc
        lines = [
            "The perimeter sentries are still active. If we leave them running, they will find this place.",
            "Power cells are scattered through the ruins. Every charge buys us another hour of clean air.",
            "There are rooms hidden behind the walls. Most people walk past them. I don't.",
        ]
        claimed = quest["id"] in self.save_data.get("quest_claimed", [])
        active = quest["id"] in self.save_data.get("quest_active", [])
        progress = self.quest_progress(quest)
        if claimed:
            action_label = "CONTRACT COMPLETE"
        elif not active:
            action_label = "ACCEPT CONTRACT"
        elif progress >= quest["target"]:
            action_label = f"CLAIM REWARD  //  +{quest['reward']} COINS"
        else:
            action_label = "CONTRACT ACTIVE  //  KEEP WORKING"
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((1, 4, 13, 175))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(150, 310, 800, 245)
        pygame.draw.rect(self.screen, (8, 20, 37), panel, border_radius=14)
        pygame.draw.rect(self.screen, THEMES[5]["accent"], panel, 2, border_radius=14)
        draw_text(self.screen, self.font_l, quest["npc"], WHITE, (panel.x + 28, panel.y + 35), shadow=False)
        draw_text(self.screen, self.font_xs, quest["role"], CYAN, (panel.x + 30, panel.y + 73), shadow=False)
        draw_text(self.screen, self.font_s, lines[idx], (205, 218, 232),
                  (panel.x + 30, panel.y + 112), shadow=False)
        status = (f"{quest['title']}  //  {progress}/{quest['target']}  //  REWARD {quest['reward']} COINS"
                  if not claimed else "THIS CONTRACT HAS ALREADY BEEN COMPLETED")
        draw_text(self.screen, self.font_xs, status, YELLOW, (panel.x + 30, panel.y + 150), shadow=False)
        action_rect = pygame.Rect(panel.x + 30, panel.bottom - 58, 440, 42)
        close_rect = pygame.Rect(panel.right - 190, panel.bottom - 58, 160, 42)
        self.draw_button_at(action_label, action_rect, self.safehouse_dialog_selection == 0)
        self.draw_button_at("LEAVE", close_rect, self.safehouse_dialog_selection == 1)
        draw_text(self.screen, self.font_xs, "LEFT / RIGHT TO SELECT  //  ENTER TO CONFIRM  //  ESC CLOSE",
                  MUTED, (WIDTH // 2, 588), center=True, shadow=False)

    def draw_ability_mods(self) -> None:
        self.draw_background(THEMES[2], 2)
        draw_text(self.screen, self.font_l, "ABILITY MODS", WHITE, (WIDTH // 2, 68), center=True)
        draw_text(self.screen, self.font_xs, "CHOOSE AN OPERATIVE // REVIEW THEIR INSTALLED MODULES",
                  THEMES[2]["accent"], (WIDTH // 2, 108), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, f"WALLET  //  {self.total_coins:04d} COINS",
                  YELLOW, (WIDTH // 2, 584), center=True, shadow=False)
        for i, cid in enumerate(CHARACTER_IDS):
            cfg = CHARACTERS[cid]
            owned = set(self.save_data.get("character_mods", {}).get(cid, []))
            unlocked = self.character_is_unlocked(cid)
            rect = pygame.Rect(42 + i * 255, 132, 244, 82)
            selected = i == self.mods_character_index
            pygame.draw.rect(self.screen, (16, 38, 55) if selected else (7, 17, 33), rect, border_radius=9)
            pygame.draw.rect(self.screen, cfg["accent"] if selected else (45, 68, 91), rect,
                             2 if selected else 1, border_radius=9)
            pygame.draw.circle(self.screen, cfg["accent"] if unlocked else MUTED,
                               (rect.x + 29, rect.centery), 12, 3)
            draw_text(self.screen, self.font_s, cfg["name"], WHITE if unlocked else MUTED,
                      (rect.x + 52, rect.y + 12), shadow=False)
            draw_text(self.screen, self.font_xs,
                      f"{len(owned)} / {len(ABILITY_MODS[cid])} MODULES" if unlocked else "LOCKED",
                      cfg["accent"] if unlocked else MUTED, (rect.x + 52, rect.y + 43), shadow=False)
        cid = CHARACTER_IDS[self.mods_character_index]
        cfg = CHARACTERS[cid]
        mods = ABILITY_MODS[cid]
        owned = set(self.save_data.get("character_mods", {}).get(cid, []))
        draw_text(self.screen, self.font_m, f"{cfg['name']}  //  {cfg['ability']}", cfg["accent"],
                  (WIDTH // 2, 250), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, cfg["description"], MUTED,
                  (WIDTH // 2, 277), center=True, shadow=False)
        for i, (mod_id, title, cost, desc) in enumerate(mods):
            y = 300 + i * 105
            rect = pygame.Rect(150, y, 800, 88)
            selected = self.mods_selection == i
            unlocked = mod_id in owned
            pygame.draw.rect(self.screen, (17, 39, 56) if selected else (8, 18, 34), rect, border_radius=10)
            pygame.draw.rect(self.screen, cfg["accent"] if selected else (53, 76, 99), rect,
                             2 if selected else 1, border_radius=10)
            pygame.draw.circle(self.screen, cfg["accent"] if unlocked else (67, 82, 101),
                               (rect.x + 34, rect.centery), 13, 3)
            if unlocked:
                pygame.draw.circle(self.screen, cfg["accent"], (rect.x + 34, rect.centery), 6)
            draw_text(self.screen, self.font_m, title, WHITE, (rect.x + 63, rect.y + 12), shadow=False)
            draw_text(self.screen, self.font_xs, desc, MUTED, (rect.x + 63, rect.y + 49), shadow=False)
            status = "INSTALLED" if unlocked else (f"COST  {cost} COINS" if self.character_is_unlocked(cid) else "LOCKED // CLEAR SECTOR 05")
            draw_text(self.screen, self.font_xs, status, CYAN if unlocked else YELLOW,
                      (rect.right - 170, rect.y + 35), shadow=False)
        back_rect = pygame.Rect(WIDTH // 2 - 170, 525, 340, 44)
        self.draw_button_at("BACK TO SAFEHOUSE", back_rect, self.mods_selection == 2)
        if self.menu_notice_timer > 0:
            draw_text(self.screen, self.font_xs, self.menu_notice, YELLOW,
                      (WIDTH // 2, 490), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "LEFT / RIGHT: OPERATIVE  //  UP / DOWN: MODULE  //  ENTER: INSTALL",
                  MUTED, (WIDTH // 2, 610), center=True, shadow=False)

    def draw_rankings(self) -> None:
        self.draw_background(THEMES[8], 8)
        ratings = self.save_data.get("level_ratings", {})
        draw_text(self.screen, self.font_l, "SECTOR RECORDS", WHITE, (WIDTH // 2, 78), center=True)
        draw_text(self.screen, self.font_xs, "BEST CLEAR RATING  //  TIME  //  DEATHS  //  SECRETS",
                  THEMES[8]["accent"], (WIDTH // 2, 122), center=True, shadow=False)
        for i in range(10):
            row_index = i + self.ranking_scroll
            if row_index >= len(LEVELS):
                break
            data = LEVELS[row_index]
            result = ratings.get(str(row_index))
            y = 155 + i * 37
            rect = pygame.Rect(150, y, 800, 31)
            pygame.draw.rect(self.screen, (9, 20, 37), rect, border_radius=5)
            if result:
                grade = result.get("grade", "-")
                info = f"{grade}   {float(result.get('time', 0)):.1f}s   DEATHS {result.get('deaths', 0)}   SECRETS {result.get('secrets', 0)}"
                color = CYAN if grade in ("S", "A") else YELLOW if grade == "B" else MUTED
            else:
                info, color = "NOT CLEARED", MUTED
            draw_text(self.screen, self.font_xs, f"{row_index + 1:02d}  //  {data['name']}",
                      WHITE, (rect.x + 12, rect.y + 7), shadow=False)
            draw_text(self.screen, self.font_xs, info, color, (rect.right - 255, rect.y + 7),
                      shadow=False)
        self.draw_button("BACK TO MENU", 545, False, width=290)
        draw_text(self.screen, self.font_xs, "S = PERFECT  //  A = CLEAN  //  B = SURVIVED  //  C = ROUGH",
                  MUTED, (WIDTH // 2, 594), center=True, shadow=False)

    def draw_level_result(self) -> None:
        self.draw_background(THEMES[self.level_index], self.level_index)
        grade = self.last_rating.get("grade", "B")
        grade_color = {"S": YELLOW, "A": CYAN, "B": (180, 190, 210), "C": PINK}.get(grade, WHITE)
        draw_text(self.screen, self.font_l, "SECTOR CLEARED", WHITE, (WIDTH // 2, 105), center=True)
        draw_glow(self.screen, WIDTH // 2, 260, grade_color, 95)
        draw_text(self.screen, self.font_xl, grade, grade_color, (WIDTH // 2, 250), center=True)
        draw_text(self.screen, self.font_m, self.level.name, WHITE, (WIDTH // 2, 335), center=True)
        info = [
            f"TIME  {self.last_rating.get('time', 0):.1f}s",
            f"DEATHS  {self.last_rating.get('deaths', 0)}",
            f"COINS  {self.last_rating.get('coins', 0)}",
            f"SECRETS  {self.last_rating.get('secrets', 0)}",
        ]
        for i, text in enumerate(info):
            draw_text(self.screen, self.font_s, text, MUTED,
                      (WIDTH // 2, 385 + i * 25), center=True, shadow=False)
        next_text = (f"NEXT  //  {LEVELS[self.pending_next_level]['name']}"
                     if self.pending_next_level is not None else "CAMPAIGN COMPLETE  //  RETURN TO MAIN MENU")
        draw_text(self.screen, self.font_xs, next_text, CYAN,
                  (WIDTH // 2, 500), center=True, shadow=False)
        self.draw_button("CONTINUE", 530, True, width=290)
        draw_text(self.screen, self.font_xs, "ENTER TO CONTINUE DIRECTLY TO NEXT SECTOR",
                  MUTED, (WIDTH // 2, 594), center=True, shadow=False)

    def draw_pause(self) -> None:
        self.screen.blit(self.pause_overlay, (0, 0))
        draw_text(self.screen, self.font_l, "PAUSED", WHITE,
                  (WIDTH // 2, 190), center=True)
        self.draw_button_at("CONTINUE", pygame.Rect(WIDTH // 2 - 145, 300, 290, 44),
                            self.pause_selection == 0)
        self.draw_button_at("RESTART SECTOR", pygame.Rect(WIDTH // 2 - 145, 352, 290, 44),
                            self.pause_selection == 1)
        self.draw_button_at("MAIN MENU", pygame.Rect(WIDTH // 2 - 145, 404, 290, 44),
                            self.pause_selection == 2)
        for label, value, y, selected in (
            ("MUSIC", self.music_volume, 462, self.pause_selection == 3),
            ("SFX", self.sfx_volume, 520, self.pause_selection == 4),
        ):
            draw_text(self.screen, self.font_xs, label, CYAN if selected else MUTED,
                      (WIDTH // 2 - 310, y + 7), shadow=False)
            track = pygame.Rect(430, y, 290, 12)
            pygame.draw.rect(self.screen, (24, 43, 61), track, border_radius=6)
            fill = pygame.Rect(track.x, track.y, int(track.w * value), track.h)
            if fill.w:
                pygame.draw.rect(self.screen, CYAN if selected else CYAN_DARK,
                                 fill, border_radius=6)
            knob_x = track.x + int(track.w * value)
            pygame.draw.circle(self.screen, WHITE if selected else CYAN,
                               (knob_x, track.centery), 9 if selected else 7)
            draw_text(self.screen, self.font_xs, f"{round(value * 100)}%",
                      WHITE, (track.right + 42, y + 7), center=True, shadow=False)
        draw_text(self.screen, self.font_xs, "ESC // MAIN MENU     ARROWS // ADJUST VOLUME",
                  MUTED, (WIDTH // 2, 590), center=True, shadow=False)

    def draw_end_screen(self, victory: bool) -> None:
        self.draw_background(THEMES[2] if victory else THEMES[0], 2 if victory else 0)
        title = "SIGNAL RESTORED" if victory else "SIGNAL LOST"
        color = CYAN if victory else PINK
        draw_glow(self.screen, WIDTH // 2, 205, color, 150)
        draw_text(self.screen, self.font_xl, title, WHITE,
                  (WIDTH // 2, 205), center=True)
        if victory:
            message = "YOU MADE IT THROUGH THE RUINS. THE LIGHT IS YOURS."
        else:
            message = "THE CITY WENT QUIET. BUT YOU CAN TRY AGAIN."
        draw_text(self.screen, self.font_xs, message, MUTED,
                  (WIDTH // 2, 280), center=True, shadow=False)
        draw_text(self.screen, self.font_m, f"FINAL SCORE  {self.score:06d}",
                  color, (WIDTH // 2, 335), center=True)
        self.draw_button("PLAY AGAIN", 410, True)
        draw_text(self.screen, self.font_xs, "PRESS ENTER", MUTED,
                  (WIDTH // 2, 490), center=True, shadow=False)

    def draw(self) -> None:
        if self.mode == "menu":
            self.draw_menu()
        elif self.mode == "personnel":
            self.draw_personnel()
        elif self.mode == "level_select":
            self.draw_level_select()
        elif self.mode == "character_select":
            self.draw_character_select()
        elif self.mode == "store":
            self.draw_store()
        elif self.mode == "safehouse":
            self.draw_safehouse()
            if self.safehouse_event_active:
                self.draw_167_signal_event()
        elif self.mode == "cassette_deck":
            self.draw_cassette_deck()
        elif self.mode == "secret_room_167":
            self.draw_secret_room_167()
        elif self.mode == "safehouse_dialog":
            self.draw_safehouse()
            self.draw_safehouse_dialog()
        elif self.mode == "ability_mods":
            self.draw_ability_mods()
        elif self.mode == "rankings":
            self.draw_rankings()
        elif self.mode == "level_result":
            self.draw_level_result()
        elif self.mode == "skills":
            self.draw_skills()
        elif self.mode == "achievements":
            self.draw_achievements()
        elif self.mode in ("playing", "paused"):
            self.draw_world()
            self.draw_hud()
            if self.mode == "paused":
                self.draw_pause()
        elif self.mode == "gameover":
            self.draw_end_screen(False)
        elif self.mode == "victory":
            self.draw_end_screen(True)

        if self.shake > 0 and self.mode == "playing":
            offset = random.randint(-3, 3)
            copy = self.screen.copy()
            self.screen.fill((0, 0, 0))
            self.screen.blit(copy, (offset, 0))

        if self.achievement_popup_timer > 0:
            alpha = min(255, int(255 * min(1.0, self.achievement_popup_timer * 1.8)))
            toast = pygame.Surface((390, 72), pygame.SRCALPHA)
            toast.fill((5, 20, 34, int(alpha * 0.92)))
            pygame.draw.rect(toast, (255, 211, 111, alpha), toast.get_rect(), 2, border_radius=10)
            pygame.draw.circle(toast, (255, 211, 111, alpha), (34, 36), 13, 3)
            pygame.draw.line(toast, (255, 211, 111, alpha), (28, 36), (33, 42), 3)
            pygame.draw.line(toast, (255, 211, 111, alpha), (33, 42), (42, 28), 3)
            head = self.font_xs.render(localize("ACHIEVEMENT UNLOCKED"), True, (255, 218, 128))
            body = self.font_s.render(localize(self.achievement_popup_title), True, WHITE)
            if body.get_width() > 315:
                body = pygame.transform.smoothscale(body, (315, max(1, int(body.get_height() * 315 / body.get_width()))))
            toast.blit(head, (60, 12))
            toast.blit(body, (60, 34))
            toast.set_alpha(alpha)
            self.screen.blit(toast, (WIDTH - 410, 18))

        if self.show_fps:
            fps_value = self.clock.get_fps()
            fps_color = CYAN if fps_value >= 150 else YELLOW if fps_value >= 90 else RED
            fps_label = self.font_xs.render(
                f"{fps_value:5.1f} FPS  |  CAP {TARGET_FPS}", True, fps_color)
            fps_bg = pygame.Surface((fps_label.get_width() + 14, 25), pygame.SRCALPHA)
            fps_bg.fill((4, 9, 22, 190))
            self.screen.blit(fps_bg, (WIDTH // 2 - fps_bg.get_width() // 2, 12))
            self.screen.blit(fps_label, fps_label.get_rect(midtop=(WIDTH // 2, 17)))
        self.present_display()

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(TARGET_FPS) / 1000.0, 0.033)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
        self.save_progress()
        try:
            pygame.mixer.music.fadeout(300)
            self.stop_flight_sfx()
        except pygame.error:
            pass
        pygame.quit()


async def main() -> None:
    """Cooperative Pygame loop required by Pygbag/WebAssembly."""
    game = None
    try:
        game = Game()
        while game.running:
            dt = min(game.clock.tick(TARGET_FPS) / 1000.0, 0.033)
            for event in pygame.event.get():
                game.handle_event(event)
            game.update(dt)
            game.draw()
            # Yield to the browser event loop so rendering/input stay responsive.
            await asyncio.sleep(0)
        game.save_progress()
        try:
            pygame.mixer.music.fadeout(250)
            game.stop_flight_sfx()
        except pygame.error:
            pass
    except Exception as exc:
        print("OXYGEN WEB crashed:", exc, file=sys.stderr)
        raise
    finally:
        pygame.quit()


def desktop_main() -> None:
    try:
        Game().run()
    except Exception as exc:
        pygame.quit()
        print("OXYGEN crashed:", exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    if sys.platform == "emscripten":
        asyncio.run(main())
    else:
        desktop_main()
