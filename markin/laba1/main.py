import sys
import random
import json
import socket
import threading
import time
import argparse
from dataclasses import dataclass

import pygame
import traceback
import os


# Window settings
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 600
FPS = 60

# Colors
COLOR_BG = (20, 20, 24)
COLOR_WALL = (90, 90, 110)
COLOR_TANK_1 = (56, 150, 201)
COLOR_TANK_2 = (220, 95, 95)
COLOR_BULLET_1 = (120, 200, 255)
COLOR_BULLET_2 = (255, 150, 150)
COLOR_TEXT = (230, 230, 240)
COLOR_GRID = (28, 28, 34)
COLOR_SHADOW = (0, 0, 0, 70)
COLOR_MINIMAP_BG = (16, 16, 20)
COLOR_MINIMAP_BORDER = (60, 60, 70)

# Gameplay
TANK_SIZE = (38, 38)
TANK_SPEED = 3.0
TANK_ROTATE_SPEED = 4.0  # degrees per frame, unused with 4-dir tank

BULLET_SPEED = 8.0
BULLET_RADIUS = 4
BULLET_COOLDOWN_FRAMES = 18
BULLET_MAX_ALIVE_FRAMES = FPS * 3

WALL_MIN_COUNT = 6
WALL_MAX_COUNT = 10
WALL_SPACING = 10  # минимальный зазор между блоками стен

WIN_SCORE = 5


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def make_vignette(surface_size: tuple[int, int]) -> pygame.Surface:
    w, h = surface_size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w / 2, h / 2
    max_d = (cx ** 2 + cy ** 2) ** 0.5
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            dx = x - cx
            dy = y - cy
            d = (dx * dx + dy * dy) ** 0.5
            a = int(140 * (d / max_d) ** 1.6)
            if a > 0:
                surf.fill((0, 0, 0, a), pygame.Rect(x, y, 2, 2))
    return surf


@dataclass
class Controls:
    up: int
    down: int
    left: int
    right: int
    fire: int


class Wall:
    def __init__(self, rect: pygame.Rect, hp: int = 3):
        self.rect = rect
        self.max_hp = hp
        self.hp = hp

    def draw(self, surface: pygame.Surface, ox: int = 0, oy: int = 0) -> None:
        r = self.rect.move(ox, oy)

        # Building base color with subtle variation by position
        rng = (r.x * 73856093 ^ r.y * 19349663) & 0xFF
        base = (80 + rng % 30, 80 + (rng // 2) % 25, 95 + (rng // 3) % 30)
        outline = (40, 40, 58)
        roof_dark = (base[0] - 20 if base[0] > 20 else 0, base[1] - 20 if base[1] > 20 else 0, base[2] - 25 if base[2] > 25 else 0)
        roof_light = (min(base[0] + 20, 255), min(base[1] + 20, 255), min(base[2] + 30, 255))

        # Damage tint: the lower the hp, the darker
        if self.hp < self.max_hp:
            factor = 0.7 + 0.3 * (self.hp / max(1, self.max_hp))
            base = (int(base[0] * factor), int(base[1] * factor), int(base[2] * factor))

        # Body with subtle pattern
        body = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
        body.fill((*base, 255))
        for i in range(0, r.height, 6):
            pygame.draw.line(body, (base[0]-8 if base[0]>8 else 0, base[1]-8 if base[1]>8 else 0, base[2]-10 if base[2]>10 else 0), (6, i), (r.width-6, i))
        pygame.draw.rect(body, (0,0,0,0), body.get_rect(), width=0, border_radius=6)
        surface.blit(body, r.topleft)
        pygame.draw.rect(surface, outline, r, width=2, border_radius=6)

        # Roof strip and subtle gradient
        roof_h = max(10, r.height // 8)
        roof_rect = pygame.Rect(r.x, r.y, r.width, roof_h)
        pygame.draw.rect(surface, roof_dark, roof_rect, border_top_left_radius=6, border_top_right_radius=6)
        grad = pygame.Surface((r.width, roof_h), pygame.SRCALPHA)
        for i in range(roof_h):
            a = int(90 * (1 - i / roof_h))
            pygame.draw.line(grad, (*roof_light, a), (0, i), (r.width, i))
        surface.blit(grad, roof_rect.topleft)

        # Windows grid
        margin_x = 8
        margin_y = roof_h + 8
        win_w, win_h = 12, 16
        gap_x, gap_y = 8, 8
        cols = max(1, (r.width - margin_x * 2 + gap_x) // (win_w + gap_x))
        rows = max(1, (r.height - margin_y - 8 + gap_y) // (win_h + gap_y))
        start_x = r.x + (r.width - (cols * win_w + (cols - 1) * gap_x)) // 2
        start_y = r.y + margin_y
        window_on = (230, 225, 160)
        window_off = (105, 110, 120)
        for cy in range(rows):
            for cx in range(cols):
                wx = start_x + cx * (win_w + gap_x)
                wy = start_y + cy * (win_h + gap_y)
                # Twinkle pattern (deterministic subtlety)
                tw = ((wx + wy + (pygame.time.get_ticks() // 700)) // 13) % 7
                color = window_on if tw in (0, 1) else window_off
                rect = pygame.Rect(wx, wy, win_w, win_h)
                pygame.draw.rect(surface, color, rect, border_radius=3)
                pygame.draw.rect(surface, (70, 70, 82), rect, width=1, border_radius=3)
        
        # Vertical accents (pilasters)
        pilasters = max(2, cols - 1)
        for i in range(1, pilasters + 1):
            px = r.x + i * r.width // (pilasters + 1)
            pygame.draw.line(surface, (base[0] - 10 if base[0] > 10 else 0, base[1] - 10 if base[1] > 10 else 0, base[2] - 15 if base[2] > 15 else 0), (px, r.y + roof_h), (px, r.bottom - 6), width=2)


class Bullet:
    def __init__(self, x: float, y: float, dx: int, dy: int, color: tuple[int, int, int]):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.color = color
        self.frames_alive = 0
        self.is_active = True
        self.trail: list[tuple[float, float]] = []
        self.bounces_left = 0  # disable ricochets by default

    def update(self, walls: list[Wall]) -> None:
        if not self.is_active:
            return
        # Add to trail
        self.trail.append((self.x, self.y))
        if len(self.trail) > 8:
            self.trail.pop(0)

        prev_x, prev_y = self.x, self.y
        self.x += self.dx * BULLET_SPEED
        self.y += self.dy * BULLET_SPEED
        self.frames_alive += 1

        # Deactivate on lifetime end or out of bounds
        if (
            self.frames_alive > BULLET_MAX_ALIVE_FRAMES
            or self.x < 0
            or self.x > WINDOW_WIDTH
            or self.y < 0
            or self.y > WINDOW_HEIGHT
        ):
            self.is_active = False
            return

        # Collide with walls (no ricochet: destroy on hit) and damage
        bullet_rect = pygame.Rect(int(self.x - BULLET_RADIUS), int(self.y - BULLET_RADIUS), BULLET_RADIUS * 2, BULLET_RADIUS * 2)
        for wall in list(walls):
            if bullet_rect.colliderect(wall.rect):
                # Damage the wall
                wall.hp -= 1
                # Remove wall if destroyed
                if wall.hp <= 0:
                    try:
                        walls.remove(wall)
                    except ValueError:
                        pass
                self.is_active = False
                break

    def draw(self, surface: pygame.Surface, ox: int = 0, oy: int = 0) -> None:
        if not self.is_active:
            return
        # Glow
        glow_surface = pygame.Surface((BULLET_RADIUS * 8, BULLET_RADIUS * 8), pygame.SRCALPHA)
        gx = BULLET_RADIUS * 4
        gy = BULLET_RADIUS * 4
        for i, alpha in enumerate([40, 30, 18]):
            pygame.draw.circle(glow_surface, (*self.color, alpha), (gx, gy), BULLET_RADIUS + 6 - i * 2)
        surface.blit(glow_surface, (int(self.x - gx + ox), int(self.y - gy + oy)))
        # Trail
        for i, (tx, ty) in enumerate(self.trail[:-1]):
            a = max(30 - i * 4, 0)
            pygame.draw.circle(surface, (*self.color, a), (int(tx + ox), int(ty + oy)), max(BULLET_RADIUS - 1, 2))
        # Core
        pygame.draw.circle(surface, self.color, (int(self.x + ox), int(self.y + oy)), BULLET_RADIUS)

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - BULLET_RADIUS), int(self.y - BULLET_RADIUS), BULLET_RADIUS * 2, BULLET_RADIUS * 2)


class Tank:
    def __init__(
        self,
        x: int,
        y: int,
        color: tuple[int, int, int],
        bullet_color: tuple[int, int, int],
        controls: Controls,
    ):
        self.rect = pygame.Rect(x, y, TANK_SIZE[0], TANK_SIZE[1])
        self.color = color
        self.bullet_color = bullet_color
        self.controls = controls
        self.cooldown_frames_left = 0
        self.last_move_direction = pygame.Vector2(1, 0)
        self.score = 0

    def reset_position(self, x: int, y: int) -> None:
        self.rect.topleft = (x, y)
        self.last_move_direction.update(1, 0)
        self.cooldown_frames_left = 0

    def update(self, pressed: pygame.key.ScancodeWrapper, walls: list[Wall]) -> None:
        dx = 0
        dy = 0
        if pressed[self.controls.up]:
            dy -= 1
        if pressed[self.controls.down]:
            dy += 1
        if pressed[self.controls.left]:
            dx -= 1
        if pressed[self.controls.right]:
            dx += 1

        # Speed buff
        speed = TANK_SPEED * (1.35 if tank_has_buff(self, "buff_speed_until") else 1.0)

        movement = pygame.Vector2(dx, dy)
        if movement.length_squared() > 0:
            movement = movement.normalize() * speed
            self.last_move_direction.update(0 if dx == 0 else (1 if dx > 0 else -1), 0 if dy == 0 else (1 if dy > 0 else -1))

        # Move with simple AABB collision resolution against walls
        self._move_and_collide(movement, walls)

        if self.cooldown_frames_left > 0:
            self.cooldown_frames_left -= 1

    def _move_and_collide(self, movement: pygame.Vector2, walls: list[Wall]) -> None:
        # Horizontal
        self.rect.x += int(movement.x)
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if movement.x > 0:
                    self.rect.right = wall.rect.left
                elif movement.x < 0:
                    self.rect.left = wall.rect.right

        # Vertical
        self.rect.y += int(movement.y)
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if movement.y > 0:
                    self.rect.bottom = wall.rect.top
                elif movement.y < 0:
                    self.rect.top = wall.rect.bottom

        # Clamp to screen
        self.rect.x = int(clamp(self.rect.x, 0, WINDOW_WIDTH - self.rect.width))
        self.rect.y = int(clamp(self.rect.y, 0, WINDOW_HEIGHT - self.rect.height))

    def can_fire(self) -> bool:
        return self.cooldown_frames_left == 0

    def fire(self) -> Bullet | None:
        # Rapid fire buff reduces cooldown
        if not self.can_fire():
            return None

        direction = self.last_move_direction
        dx = 0
        dy = 0
        # Snap to 4 directions based on last movement
        if abs(direction.x) >= abs(direction.y):
            dx = 1 if direction.x >= 0 else -1
            dy = 0
        else:
            dy = 1 if direction.y >= 0 else -1
            dx = 0

        if dx == 0 and dy == 0:
            dx = 1  # default shoot right

        # Start bullet from tank center
        cx = self.rect.centerx + dx * (self.rect.width // 2)
        cy = self.rect.centery + dy * (self.rect.height // 2)
        bullet = Bullet(cx, cy, dx, dy, self.bullet_color)
        cooldown = int(BULLET_COOLDOWN_FRAMES * (0.55 if tank_has_buff(self, "buff_rapid_until") else 1.0))
        self.cooldown_frames_left = max(1, cooldown)
        return bullet

    def draw(self, surface: pygame.Surface, ox: int = 0, oy: int = 0) -> None:
        # Shadow
        shadow_surface = pygame.Surface((self.rect.width + 6, self.rect.height + 6), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surface, COLOR_SHADOW, shadow_surface.get_rect(), border_radius=10)
        surface.blit(shadow_surface, (self.rect.x + 3 + ox, self.rect.y + 3 + oy))

        # Body
        body_rect = self.rect.move(ox, oy)
        pygame.draw.rect(surface, self.color, body_rect, border_radius=8)
        pygame.draw.rect(surface, (30, 30, 34), body_rect, width=2, border_radius=8)

        # Turret
        cx, cy = body_rect.centerx, body_rect.centery
        dirx, diry = int(self.last_move_direction.x), int(self.last_move_direction.y)
        if dirx == 0 and diry == 0:
            dirx = 1
        barrel_len = 22
        barrel_w = 8
        endx = cx + dirx * barrel_len
        endy = cy + diry * barrel_len
        if dirx != 0:
            # Horizontal barrel
            rect = pygame.Rect(min(cx, endx), cy - barrel_w // 2, abs(endx - cx), barrel_w)
        else:
            # Vertical barrel
            rect = pygame.Rect(cx - barrel_w // 2, min(cy, endy), barrel_w, abs(endy - cy))
        pygame.draw.rect(surface, (235, 235, 245), rect, border_radius=barrel_w // 2)
        # Turret ring with highlight
        pygame.draw.circle(surface, (210, 210, 225), (cx, cy), 7)
        pygame.draw.circle(surface, (150, 150, 165), (cx, cy), 7, width=2)
        pygame.draw.circle(surface, (255, 255, 255), (cx-2, cy-2), 2)


class Particle:
    def __init__(self, x: float, y: float, vx: float, vy: float, life: int, color: tuple[int, int, int]):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color

    def update(self) -> None:
        if self.life <= 0:
            return
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.96
        self.vy = self.vy * 0.96 + 0.12  # slight gravity
        self.life -= 1

    def draw(self, surface: pygame.Surface, ox: int = 0, oy: int = 0) -> None:
        if self.life <= 0:
            return
        alpha = int(200 * (self.life / self.max_life))
        pygame.draw.circle(surface, (*self.color, alpha), (int(self.x + ox), int(self.y + oy)), 3)


class Game:
    _instance: "Game | None" = None

    def __init__(self, net_role: str | None = None, net: "NetManager | None" = None) -> None:
        pygame.init()
        pygame.display.set_caption("Tanki 2D")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 22)
        self.small_font = pygame.font.SysFont("consolas", 14)

        self.walls: list[Wall] = []
        self.bullets: list[Bullet] = []
        self.particles: list[Particle] = []
        self.shake_frames = 0
        self.shake_strength = 0
        self.explosions: list[Explosion] = []  # defined below
        self.round_end_timer = 0
        self.tank1_destroyed = False
        self.tank2_destroyed = False
        self.powerups: list[PowerUp] = []
        self.powerup_spawn_cooldown = int(FPS * 4)
        self.music_enabled = True
        # Audio/SFX
        self.sfx: dict[str, pygame.mixer.Sound] | None = None
        self.engine_ch1: pygame.mixer.Channel | None = None
        self.engine_ch2: pygame.mixer.Channel | None = None
        # UX and audio defaults must be set before audio init
        self.is_paused = False
        self.music_volume = 0.04
        self.sfx_volume = 0.30

        try:
            self._init_music()
            self._prepare_sfx()
        except Exception:
            # Safe fallbacks if audio init fails
            self.music_enabled = False
            self.sfx = {}
        Game._instance = self

        # Networking
        self.net_role = net_role  # 'host', 'client', or None
        self.net = net
        self.remote_input = {"up": False, "down": False, "left": False, "right": False, "fire": False}
        self._remote_last_ms = 0

        # UX and polish (rest)
        self.countdown_frames = 0
        self.tread_decals: list[tuple[int, int, int, int]] = []  # x, y, life, alpha
        self.toast_text = ""
        self.toast_ms_until = 0

        self.tank1 = Tank(
            60,
            WINDOW_HEIGHT // 2 - TANK_SIZE[1] // 2,
            COLOR_TANK_1,
            COLOR_BULLET_1,
            Controls(up=pygame.K_w, down=pygame.K_s, left=pygame.K_a, right=pygame.K_d, fire=pygame.K_SPACE),
        )
        self.tank2 = Tank(
            WINDOW_WIDTH - 60 - TANK_SIZE[0],
            WINDOW_HEIGHT // 2 - TANK_SIZE[1] // 2,
            COLOR_TANK_2,
            COLOR_BULLET_2,
            Controls(up=pygame.K_UP, down=pygame.K_DOWN, left=pygame.K_LEFT, right=pygame.K_RIGHT, fire=pygame.K_RCTRL),
        )

        self.reset_round(generate_new_map=True)
        # Precompute vignette and background gradient
        self._vignette = make_vignette((WINDOW_WIDTH, WINDOW_HEIGHT))
        self._bg_grad = self._make_bg_gradient()

    def reset_round(self, generate_new_map: bool) -> None:
        if generate_new_map:
            self._generate_walls()
        # Place tanks at opposite sides
        self.tank1.reset_position(60, WINDOW_HEIGHT // 2 - TANK_SIZE[1] // 2)
        self.tank2.reset_position(WINDOW_WIDTH - 60 - TANK_SIZE[0], WINDOW_HEIGHT // 2 - TANK_SIZE[1] // 2)
        self.bullets.clear()
        # Keep particles to allow impact effects to linger across rounds
        self.explosions.clear()
        self.round_end_timer = 0
        self.tank1_destroyed = False
        self.tank2_destroyed = False
        self.powerups.clear()
        self.powerup_spawn_cooldown = int(FPS * 2)
        # Immediately push a fresh state to client after reset
        if self.net_role == 'host' and self.net:
            self.net.broadcast_state(self._build_state_snapshot())
        # Round start countdown
        self.countdown_frames = int(2 * FPS)

    def _generate_walls(self) -> None:
        random.seed()
        self.walls.clear()

        # Outer border gaps
        margin = 40
        # Middle maze-like blocks without overlaps
        count = random.randint(WALL_MIN_COUNT, WALL_MAX_COUNT)
        spawn_left = pygame.Rect(20, WINDOW_HEIGHT // 2 - 80, 140, 160)
        spawn_right = pygame.Rect(WINDOW_WIDTH - 160, WINDOW_HEIGHT // 2 - 80, 140, 160)

        max_attempts = count * 60
        attempts = 0
        while len(self.walls) < count and attempts < max_attempts:
            attempts += 1
            w = random.randint(80, 160)
            h = random.randint(20, 120)
            x = random.randint(margin, WINDOW_WIDTH - margin - w)
            y = random.randint(margin, WINDOW_HEIGHT - margin - h)
            rect = pygame.Rect(x, y, w, h)

            # Check spawn zones and spacing against existing walls
            inflated = rect.inflate(WALL_SPACING * 2, WALL_SPACING * 2)
            if inflated.colliderect(spawn_left) or inflated.colliderect(spawn_right):
                continue

            overlaps = False
            for existing in self.walls:
                if inflated.colliderect(existing.rect):
                    overlaps = True
                    break
            if overlaps:
                continue

            self.walls.append(Wall(rect))

    def handle_bullet_collisions(self) -> None:
        # Remove inactive bullets
        self.bullets = [b for b in self.bullets if b.is_active]

        # Tank collisions
        for bullet in list(self.bullets):
            if not bullet.is_active:
                continue
            bullet_rect = bullet.get_rect()
            if self.round_end_timer == 0 and bullet_rect.colliderect(self.tank1.rect) and bullet.color == COLOR_BULLET_2:
                hit_x, hit_y = self.tank1.rect.centerx, self.tank1.rect.centery
                bullet.is_active = False
                # Shield blocks one hit
                if tank_has_buff(self.tank1, "buff_shield_until"):
                    setattr(self.tank1, "buff_shield_until", 0)
                    self._spawn_hit_effect(hit_x, hit_y, (120, 200, 255))
                    self._shake(6, 10)
                else:
                    self._spawn_tank_explosion(hit_x, hit_y)
                    self._spawn_hit_effect(hit_x, hit_y, self.tank2.color)
                    self._shake(10, 14)
                    self.tank2.score += 1
                    self.tank1_destroyed = True
                    self.round_end_timer = int(FPS * 1.0)
                break
            if self.round_end_timer == 0 and bullet_rect.colliderect(self.tank2.rect) and bullet.color == COLOR_BULLET_1:
                hit_x, hit_y = self.tank2.rect.centerx, self.tank2.rect.centery
                bullet.is_active = False
                if tank_has_buff(self.tank2, "buff_shield_until"):
                    setattr(self.tank2, "buff_shield_until", 0)
                    self._spawn_hit_effect(hit_x, hit_y, (120, 200, 255))
                    self._shake(6, 10)
                else:
                    self._spawn_tank_explosion(hit_x, hit_y)
                    self._spawn_hit_effect(hit_x, hit_y, self.tank1.color)
                    self._shake(10, 14)
                    self.tank1.score += 1
                    self.tank2_destroyed = True
                    self.round_end_timer = int(FPS * 1.0)
                break

    def _spawn_hit_effect(self, x: float, y: float, color: tuple[int, int, int]) -> None:
        for _ in range(18):
            ang = random.uniform(0, 3.14159 * 2)
            speed = random.uniform(1.5, 4.0)
            vx = speed * pygame.math.Vector2(1, 0).rotate_rad(ang).x
            vy = speed * pygame.math.Vector2(1, 0).rotate_rad(ang).y
            self.particles.append(Particle(x, y, vx, vy, life=random.randint(18, 32), color=color))
        # Scorch decal
        s = pygame.Surface((22, 22), pygame.SRCALPHA)
        pygame.draw.circle(s, (20, 20, 22, 90), (11, 11), 11)
        pygame.draw.circle(s, (0, 0, 0, 0), (11, 11), 7)
        self.screen.blit(s, (int(x - 11), int(y - 11)))

    def _shake(self, frames: int, strength: int) -> None:
        self.shake_frames = max(self.shake_frames, frames)
        self.shake_strength = max(self.shake_strength, strength)

    def _spawn_tank_explosion(self, x: float, y: float) -> None:
        # Big burst of particles + an expanding shockwave
        for _ in range(40):
            ang = random.uniform(0, 3.14159 * 2)
            speed = random.uniform(1.0, 5.0)
            v = pygame.math.Vector2(speed, 0).rotate_rad(ang)
            col = random.choice([(250, 220, 120), (250, 170, 80), (255, 120, 80), (240, 240, 240)])
            self.particles.append(Particle(x, y, v.x, v.y, life=random.randint(24, 40), color=col))
        self.explosions.append(Explosion(x, y, max_radius=90, life=int(FPS * 0.6)))
        # Explosion SFX
        try:
            if self.sfx and "explosion" in self.sfx:
                self.sfx["explosion"].play()
        except Exception:
            pass

    def draw_hud(self) -> None:
        score_text = f"P1: {self.tank1.score}   P2: {self.tank2.score}"
        text_surface = self.font.render(score_text, True, COLOR_TEXT)
        self.screen.blit(text_surface, (WINDOW_WIDTH // 2 - text_surface.get_width() // 2, 8))

        # Buff icons with remaining time bars
        now = pygame.time.get_ticks()
        def draw_buff(x: int, y: int, active: bool, color: tuple[int, int, int], remain_ms: int) -> int:
            box = pygame.Rect(x, y, 70, 16)
            pygame.draw.rect(self.screen, (35, 35, 45), box, border_radius=6)
            pygame.draw.rect(self.screen, color, (box.x + 3, box.y + 3, max(1, int((box.width - 6) * remain_ms / 5000)), box.height - 6), border_radius=4)
            return box.right + 8

        # Tank1 buffs
        bx = 12
        by = 10
        if tank_has_buff(self.tank1, "buff_shield_until"):
            draw_buff(bx, by, True, (120, 200, 255), getattr(self.tank1, "buff_shield_until") - now)
        if tank_has_buff(self.tank1, "buff_rapid_until"):
            draw_buff(bx, by + 20, True, (255, 200, 120), getattr(self.tank1, "buff_rapid_until") - now)
        if tank_has_buff(self.tank1, "buff_speed_until"):
            draw_buff(bx, by + 40, True, (160, 255, 160), getattr(self.tank1, "buff_speed_until") - now)

        # Tank2 buffs
        bx = WINDOW_WIDTH - 82
        if tank_has_buff(self.tank2, "buff_shield_until"):
            draw_buff(bx, by, True, (120, 200, 255), getattr(self.tank2, "buff_shield_until") - now)
        if tank_has_buff(self.tank2, "buff_rapid_until"):
            draw_buff(bx, by + 20, True, (255, 200, 120), getattr(self.tank2, "buff_rapid_until") - now)
        if tank_has_buff(self.tank2, "buff_speed_until"):
            draw_buff(bx, by + 40, True, (160, 255, 160), getattr(self.tank2, "buff_speed_until") - now)

        help_text = "WASD+Space | Arrows+RightCtrl | P: pause | M: music"
        small_font = pygame.font.SysFont("consolas", 16)
        help_surface = small_font.render(help_text, True, (180, 180, 195))
        self.screen.blit(help_surface, (WINDOW_WIDTH // 2 - help_surface.get_width() // 2, WINDOW_HEIGHT - 24))

    def maybe_show_win_screen(self) -> bool:
        if self.tank1.score >= WIN_SCORE or self.tank2.score >= WIN_SCORE:
            winner_text = "Player 1 wins!" if self.tank1.score >= WIN_SCORE else "Player 2 wins!"
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))
            big_font = pygame.font.SysFont("consolas", 48, bold=True)
            title = big_font.render(winner_text, True, COLOR_TEXT)
            self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, WINDOW_HEIGHT // 2 - 80))

            small_font = pygame.font.SysFont("consolas", 22)
            tip = small_font.render("Press R to play again or Esc to quit", True, COLOR_TEXT)
            self.screen.blit(tip, (WINDOW_WIDTH // 2 - tip.get_width() // 2, WINDOW_HEIGHT // 2 - 20))
            pygame.display.flip()

            # Pause until R or Esc
            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit(0)
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            pygame.quit()
                            sys.exit(0)
                        if event.key == pygame.K_r:
                            self.tank1.score = 0
                            self.tank2.score = 0
                            self.reset_round(generate_new_map=True)
                            waiting = False
                self.clock.tick(30)
            return True
        return False

    def run(self) -> None:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit(0)
                    if event.key == pygame.K_p:
                        self.is_paused = not self.is_paused
                        self._update_music_volume()
                    if event.key == pygame.K_r:
                        self.tank1.score = 0
                        self.tank2.score = 0
                        self.reset_round(generate_new_map=True)
                    if event.key == pygame.K_m:
                        self.toggle_music()
                    if event.key == self.tank1.controls.fire and (self.net_role != 'client'):
                        bullet = self.tank1.fire()
                        if bullet:
                            self.bullets.append(bullet)
                            self._play_shot_sfx()
                    if event.key == self.tank2.controls.fire and (self.net_role != 'host'):
                        bullet = self.tank2.fire()
                        if bullet:
                            self.bullets.append(bullet)
                            self._play_shot_sfx()

            pressed = pygame.key.get_pressed()
            if self.is_paused:
                self._draw_background()
                self._draw_pause_overlay()
                pygame.display.flip()
                self.clock.tick(30)
                continue
            # Freeze movement and firing during end animation
            if self.round_end_timer == 0:
                if self.net_role == 'client':
                    # Client: don't simulate; host will send state
                    pass
                else:
                    # Host or local: update Player 1 locally
                    if self.countdown_frames == 0:
                        self.tank1.update(pressed, self.walls)
                    if self.net_role == 'host':
                        # Update latest remote input snapshot from network
                        self._net_poll_input()
                        # Update tank2 from remote input
                        if self.countdown_frames == 0:
                            self._apply_remote_input_to_tank(self.tank2)
                    else:
                        # Local two-players
                        if self.countdown_frames == 0:
                            self.tank2.update(pressed, self.walls)
            # Client receives new state frequently and rebuilds scene
            if self.net_role == 'client':
                # Send input heartbeat every frame (even without movement)
                self._net_send_input(pressed)
                self._net_apply_state_if_any()
            # Engine SFX state
            moving1 = self.round_end_timer == 0 and not self.tank1_destroyed and (
                pressed[self.tank1.controls.up] or pressed[self.tank1.controls.down] or pressed[self.tank1.controls.left] or pressed[self.tank1.controls.right]
            )
            moving2 = self.round_end_timer == 0 and not self.tank2_destroyed and (
                pressed[self.tank2.controls.up] or pressed[self.tank2.controls.down] or pressed[self.tank2.controls.left] or pressed[self.tank2.controls.right]
            )
            self._update_engine_sfx(moving1, moving2)

            # Update bullets
            prev_states = {id(b): b.is_active for b in self.bullets}
            for bullet in self.bullets:
                if self.round_end_timer == 0 and self.net_role != 'client' and self.countdown_frames == 0:
                    pre_active = bullet.is_active
                    bullet.update(self.walls)
                    # Impact with wall: deactivation = hit
                    if pre_active and not bullet.is_active:
                        self._spawn_hit_effect(bullet.x, bullet.y, (240, 200, 120))
                        self._shake(3, 5)

            if self.net_role != 'client' and self.countdown_frames == 0:
                self.handle_bullet_collisions()

            # Draw
            self._draw_background()

            # Screen shake offset
            ox, oy = 0, 0
            if self.shake_frames > 0:
                ox = random.randint(-self.shake_strength, self.shake_strength)
                oy = random.randint(-self.shake_strength, self.shake_strength)
                self.shake_frames -= 1
                self.shake_strength = max(self.shake_strength - 1, 0)

            for wall in self.walls:
                wall.draw(self.screen, ox, oy)
            if not self.tank1_destroyed:
                self.tank1.draw(self.screen, ox, oy)
            if not self.tank2_destroyed:
                self.tank2.draw(self.screen, ox, oy)
            for bullet in self.bullets:
                bullet.draw(self.screen, ox, oy)
            # (tread decals removed by request)
            # Particles
            for p in list(self.particles):
                p.update()
                p.draw(self.screen, ox, oy)
            self.particles = [p for p in self.particles if p.life > 0]
            # Explosions
            for e in list(self.explosions):
                e.update()
                e.draw(self.screen, ox, oy)
            self.explosions = [e for e in self.explosions if e.life > 0]
            # PowerUps
            self._maybe_spawn_powerup()
            for pu in list(self.powerups):
                pu.update()
                pu.draw(self.screen, ox, oy)
                # Pickups
                for tank in (self.tank1, self.tank2):
                    if not (self.tank1_destroyed and tank is self.tank1) and not (self.tank2_destroyed and tank is self.tank2):
                        if pu.rect.colliderect(tank.rect):
                            pu.apply(tank)
                            try:
                                self.powerups.remove(pu)
                            except ValueError:
                                pass

            self.draw_hud()
            self._draw_minimap()
            if self.countdown_frames > 0:
                self._draw_countdown()

            # End-of-round timing
            if self.net_role != 'client':
                if self.round_end_timer > 0:
                    self.round_end_timer -= 1
                    if self.round_end_timer == 0:
                        self.reset_round(generate_new_map=True)
                if self.countdown_frames > 0:
                    self.countdown_frames -= 1

            # Networking: host sends state snapshots
            if self.net_role == 'host':
                self._net_broadcast_state_throttled()

            if self.maybe_show_win_screen():
                # Win screen handles its own loop; after it returns, continue fresh frame
                continue

            pygame.display.flip()
            self.clock.tick(FPS)

    def _update_music_volume(self) -> None:
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(0.0 if self.is_paused else self.music_volume)
        except Exception:
            pass

    def _draw_pause_overlay(self) -> None:
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        title = self.font.render("Paused", True, (240, 240, 250))
        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, WINDOW_HEIGHT // 2 - 80))
        tip = self.small_font.render("P: resume", True, (200, 205, 215))
        self.screen.blit(tip, (WINDOW_WIDTH // 2 - tip.get_width() // 2, WINDOW_HEIGHT // 2 - 40))

    def _draw_countdown(self) -> None:
        if self.countdown_frames <= 0:
            return
        secs = max(1, (self.countdown_frames // FPS) + 1)
        txt = str(secs) if secs > 1 else "GO!"
        big = pygame.font.SysFont("consolas", 64, bold=True)
        s = big.render(txt, True, (250, 240, 180))
        self.screen.blit(s, (WINDOW_WIDTH // 2 - s.get_width() // 2, WINDOW_HEIGHT // 2 - s.get_height() // 2))

    def _net_poll_input(self) -> None:
        if not self.net:
            return
        msg = self.net.get_latest_input()
        now = pygame.time.get_ticks()
        if msg:
            self.remote_input = {
                'up': bool(msg.get('up', False)),
                'down': bool(msg.get('down', False)),
                'left': bool(msg.get('left', False)),
                'right': bool(msg.get('right', False)),
                'fire': bool(msg.get('fire', False)),
            }
            self._remote_last_ms = now
        # If stale, treat as no input
        if now - self._remote_last_ms > 500:
            self.remote_input = {'up': False, 'down': False, 'left': False, 'right': False, 'fire': False}

    def _apply_remote_input_to_tank(self, tank: "Tank") -> None:
        # Build a pseudo pressed object for this tank from last network input
        class P:
            def __getitem__(self_inner, key: int) -> bool:
                mapping = {
                    tank.controls.up: self.remote_input.get('up', False),
                    tank.controls.down: self.remote_input.get('down', False),
                    tank.controls.left: self.remote_input.get('left', False),
                    tank.controls.right: self.remote_input.get('right', False),
                }
                return mapping.get(key, False)

        tank.update(P(), self.walls)
        # Fire edge detection
        now_fire = self.remote_input.get('fire', False)
        prev_fire = getattr(self, '_prev_remote_fire', False)
        if now_fire and not prev_fire:
            bullet = tank.fire()
            if bullet:
                self.bullets.append(bullet)
                self._play_shot_sfx()
        self._prev_remote_fire = now_fire

    def _net_send_input(self, pressed: pygame.key.ScancodeWrapper) -> None:
        if not self.net:
            return
        payload = {
            'type': 'input',
            'up': bool(pressed[self.tank2.controls.up]),
            'down': bool(pressed[self.tank2.controls.down]),
            'left': bool(pressed[self.tank2.controls.left]),
            'right': bool(pressed[self.tank2.controls.right]),
            'fire': bool(pressed[self.tank2.controls.fire]),
            'time': pygame.time.get_ticks(),
        }
        self.net.send_input(payload)

    def _net_broadcast_state_throttled(self) -> None:
        if not self.net:
            return
        now = pygame.time.get_ticks()
        last = getattr(self, '_last_broadcast_ms', 0)
        if now - last < 50:  # 20 Hz
            return
        self._last_broadcast_ms = now
        state = self._build_state_snapshot()
        self.net.broadcast_state(state)

    def _build_state_snapshot(self) -> dict:
        return {
            'type': 'state',
            't': pygame.time.get_ticks(),
            'scores': [self.tank1.score, self.tank2.score],
            'tanks': [
                {'x': self.tank1.rect.x, 'y': self.tank1.rect.y, 'alive': not self.tank1_destroyed},
                {'x': self.tank2.rect.x, 'y': self.tank2.rect.y, 'alive': not self.tank2_destroyed},
            ],
            'bullets': [{'x': b.x, 'y': b.y, 'dx': b.dx, 'dy': b.dy, 'c': (1 if b.color == COLOR_BULLET_1 else 2)} for b in self.bullets if b.is_active],
            'walls': [[w.rect.x, w.rect.y, w.rect.width, w.rect.height, w.hp] for w in self.walls],
            'powerups': [[pu.rect.x, pu.rect.y, pu.rect.width, pu.rect.height, pu.kind] for pu in self.powerups],
        }

    def _net_apply_state_if_any(self) -> None:
        if not self.net:
            return
        state = self.net.get_latest_state()
        if not state:
            return
        # Apply scores and tanks
        self.tank1.score, self.tank2.score = state.get('scores', [0, 0])
        tks = state.get('tanks', [{}, {}])
        self.tank1.rect.topleft = (tks[0].get('x', self.tank1.rect.x), tks[0].get('y', self.tank1.rect.y))
        self.tank2.rect.topleft = (tks[1].get('x', self.tank2.rect.x), tks[1].get('y', self.tank2.rect.y))
        self.tank1_destroyed = not tks[0].get('alive', True)
        self.tank2_destroyed = not tks[1].get('alive', True)
        # Walls rebuild
        self.walls = [Wall(pygame.Rect(x, y, w, h), hp=hp) for (x, y, w, h, hp) in state.get('walls', [])]
        # Powerups rebuild
        self.powerups = []
        for (x, y, w, h, kind) in state.get('powerups', []):
            self.powerups.append(PowerUp(pygame.Rect(x, y, w, h), kind))
        # Bullets rebuild (visual only)
        self.bullets = []
        for b in state.get('bullets', []):
            color = COLOR_BULLET_1 if b.get('c', 1) == 1 else COLOR_BULLET_2
            nb = Bullet(b['x'], b['y'], b.get('dx', 0), b.get('dy', 0), color)
            self.bullets.append(nb)

    def _init_music(self) -> None:
        try:
            pygame.mixer.init()
            # Generate a simple background tone sequence on the fly
            self._prepare_music()
            # Volume will be applied in _prepare_music for whichever backend is active
        except Exception:
            self.music_enabled = False

    def toggle_music(self) -> None:
        if not pygame.mixer.get_init():
            return
        self.music_enabled = not self.music_enabled
        # If using music module
        if getattr(self, "_music_loaded", False):
            try:
                if self.music_enabled:
                    pygame.mixer.music.play(-1)
                    pygame.mixer.music.set_volume(self.music_volume)
                else:
                    pygame.mixer.music.stop()
            except Exception:
                pass
        # If using fallback channel
        ch: pygame.mixer.Channel | None = getattr(self, "_music_fallback_ch", None)
        snd: pygame.mixer.Sound | None = getattr(self, "_music_fallback_sound", None)
        if ch and snd:
            try:
                if self.music_enabled and not ch.get_busy():
                    ch.play(snd, loops=-1)
                    ch.set_volume(self.music_volume)
                elif not self.music_enabled and ch.get_busy():
                    ch.stop()
            except Exception:
                pass

    def _prepare_music(self) -> None:
        # Create a tiny WAV-like buffer with simple melody using pygame.sndarray
        try:
            import numpy as np
            import pygame.sndarray as snd
        except Exception:
            # Fallback: no music
            return

        sample_rate = 22050
        seconds = 8
        t = np.linspace(0, seconds, int(sample_rate * seconds), endpoint=False)
        # Chord progression with simple sine mix
        notes = [261.63, 329.63, 392.00, 523.25]  # C E G C
        envelope = (np.exp(-3 * (t % 1.0)) * 0.6).astype(np.float32)
        wave = np.zeros_like(t, dtype=np.float32)
        for i in range(seconds):
            base = notes[i % len(notes)]
            segment = (np.sin(2 * np.pi * (base) * t) + 0.5 * np.sin(2 * np.pi * (base * 2) * t)) * envelope
            wave += segment
        wave *= 0.2
        # Convert to 16-bit signed
        audio = (wave * 32767).astype(np.int16)
        stereo = np.column_stack((audio, audio))
        self._music_loaded = False
        try:
            # Save to a Sound; some pygame versions can't load Sound via music.load
            snd_obj = pygame.mixer.Sound(buffer=stereo.tobytes())
            # Try direct music.load from a Sound; if not supported, this will raise
            pygame.mixer.music.load(snd_obj)
            pygame.mixer.music.set_volume(self.music_volume)
            if self.music_enabled:
                pygame.mixer.music.play(-1)
            self._music_loaded = True
        except Exception:
            # Fallback: use a dedicated channel to loop the Sound
            try:
                self._music_fallback_sound = pygame.mixer.Sound(buffer=stereo.tobytes())
                self._music_fallback_ch = pygame.mixer.Channel(5)
                self._music_fallback_ch.set_volume(self.music_volume)
                if self.music_enabled:
                    self._music_fallback_ch.play(self._music_fallback_sound, loops=-1)
            except Exception:
                pass

    def _prepare_sfx(self) -> None:
        # Procedurally generate simple engine, shot and explosion sounds
        try:
            import numpy as np
        except Exception:
            self.sfx = {}
            return
        sr = 22050
        def make_engine(freq=90.0, dur=0.8):
            t = np.linspace(0, dur, int(sr * dur), endpoint=False)
            base = np.sin(2 * np.pi * freq * t)
            harm = 0.5 * np.sin(2 * np.pi * freq * 2 * t)
            noise = 0.15 * (np.random.rand(t.size) * 2 - 1)
            env = np.minimum(1.0, t * 6) * 0.6
            w = (base + harm + noise) * env * 0.35
            a = (w * 32767).astype(np.int16)
            stereo = np.column_stack((a, a))
            return pygame.mixer.Sound(buffer=stereo.tobytes())
        def make_shot():
            dur = 0.18
            t = np.linspace(0, dur, int(sr * dur), endpoint=False)
            noise = (np.random.rand(t.size) * 2 - 1)
            env = np.exp(-18 * t)
            w = noise * env * 0.8
            a = (w * 32767).astype(np.int16)
            stereo = np.column_stack((a, a))
            s = pygame.mixer.Sound(buffer=stereo.tobytes())
            s.set_volume(self.sfx_volume)
            return s
        def make_explosion():
            dur = 0.6
            t = np.linspace(0, dur, int(sr * dur), endpoint=False)
            noise = (np.random.rand(t.size) * 2 - 1)
            lowpass = np.cumsum(noise)
            lowpass /= np.max(np.abs(lowpass) + 1e-6)
            env = np.exp(-4.0 * t)
            w = lowpass * env * 0.9
            a = (w * 32767).astype(np.int16)
            stereo = np.column_stack((a, a))
            s = pygame.mixer.Sound(buffer=stereo.tobytes())
            s.set_volume(self.sfx_volume)
            return s
        self.sfx = {
            "engine": make_engine(),
            "shot": make_shot(),
            "explosion": make_explosion(),
        }
        # Allocate channels
        self.engine_ch1 = pygame.mixer.Channel(1)
        self.engine_ch2 = pygame.mixer.Channel(2)

    def _update_engine_sfx(self, moving1: bool, moving2: bool) -> None:
        if not self.sfx:
            return
        try:
            if moving1:
                if not self.engine_ch1.get_busy():
                    self.engine_ch1.play(self.sfx["engine"], loops=-1, fade_ms=120)
                self.engine_ch1.set_volume(0.22)
            else:
                if self.engine_ch1.get_busy():
                    self.engine_ch1.fadeout(180)
            if moving2:
                if not self.engine_ch2.get_busy():
                    self.engine_ch2.play(self.sfx["engine"], loops=-1, fade_ms=120)
                self.engine_ch2.set_volume(0.22)
            else:
                if self.engine_ch2.get_busy():
                    self.engine_ch2.fadeout(180)
        except Exception:
            pass

    def _play_shot_sfx(self) -> None:
        if self.sfx and "shot" in self.sfx:
            try:
                s = self.sfx["shot"]
                s.set_volume(self.sfx_volume)
                s.play()
            except Exception:
                pass

    def _draw_background(self) -> None:
        # Gradient
        self.screen.blit(self._bg_grad, (0, 0))
        # Subtle grid
        spacing = 40
        for x in range(0, WINDOW_WIDTH, spacing):
            pygame.draw.line(self.screen, (26, 26, 30), (x, 0), (x, WINDOW_HEIGHT))
        for y in range(0, WINDOW_HEIGHT, spacing):
            pygame.draw.line(self.screen, (26, 26, 30), (0, y), (WINDOW_WIDTH, y))
        # Vignette
        self.screen.blit(self._vignette, (0, 0))

    def _make_bg_gradient(self) -> pygame.Surface:
        grad = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        top = pygame.Color(18, 22, 28)
        bottom = pygame.Color(14, 16, 20)
        for y in range(WINDOW_HEIGHT):
            t = y / max(1, WINDOW_HEIGHT - 1)
            c = (
                int(top.r * (1 - t) + bottom.r * t),
                int(top.g * (1 - t) + bottom.g * t),
                int(top.b * (1 - t) + bottom.b * t),
            )
            pygame.draw.line(grad, c, (0, y), (WINDOW_WIDTH, y))
        return grad

    def _draw_minimap(self) -> None:
        # Minimap constants
        map_w, map_h = 200, 130
        padding = 10
        x0 = WINDOW_WIDTH - map_w - padding
        y0 = WINDOW_HEIGHT - map_h - padding - 28
        # Background
        bg = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
        bg.fill((*COLOR_MINIMAP_BG, 200))
        self.screen.blit(bg, (x0, y0))
        pygame.draw.rect(self.screen, COLOR_MINIMAP_BORDER, (x0, y0, map_w, map_h), width=2, border_radius=6)

        # Scale factors
        sx = map_w / WINDOW_WIDTH
        sy = map_h / WINDOW_HEIGHT

        # Draw walls
        for w in self.walls:
            rx = int(x0 + w.rect.x * sx)
            ry = int(y0 + w.rect.y * sy)
            rw = max(1, int(w.rect.width * sx))
            rh = max(1, int(w.rect.height * sy))
            pygame.draw.rect(self.screen, (90, 100, 120), (rx, ry, rw, rh))

        # Draw powerups
        for pu in self.powerups:
            rx = int(x0 + pu.rect.centerx * sx)
            ry = int(y0 + pu.rect.centery * sy)
            pygame.draw.circle(self.screen, (180, 220, 120), (rx, ry), 3)

        # Tanks
        def draw_tank_dot(tank: Tank, color: tuple[int, int, int]):
            rx = int(x0 + tank.rect.centerx * sx)
            ry = int(y0 + tank.rect.centery * sy)
            pygame.draw.circle(self.screen, color, (rx, ry), 4)

        if not self.tank1_destroyed:
            draw_tank_dot(self.tank1, COLOR_TANK_1)
        if not self.tank2_destroyed:
            draw_tank_dot(self.tank2, COLOR_TANK_2)

        # Bullets
        for b in self.bullets:
            rx = int(x0 + b.x * sx)
            ry = int(y0 + b.y * sy)
            pygame.draw.circle(self.screen, (220, 220, 230), (rx, ry), 2)

        # Label
        label = self.small_font.render("Minimap (M: music)", True, (180, 180, 190))
        self.screen.blit(label, (x0 + 6, y0 - 18))

    @staticmethod
    def emit_tread_and_dust(tank: Tank) -> None:
        game_ref = Game._instance
        if not game_ref:
            return
        # Treads: drop faint rectangles behind the tank
        tx = tank.rect.x + tank.rect.width // 2 - 3
        ty = tank.rect.y + tank.rect.height // 2 - 5
        game_ref.tread_decals.append((tx, ty, 220, 160))
        if len(game_ref.tread_decals) > 120:
            game_ref.tread_decals.pop(0)
        # Dust
        for _ in range(1):
            dx = random.uniform(-0.6, 0.6)
            dy = random.uniform(-0.6, 0.6)
            game_ref.particles.append(Particle(tx, ty, dx, dy, life=random.randint(10, 18), color=(120, 120, 120)))

    def _maybe_spawn_powerup(self) -> None:
        if self.round_end_timer > 0:
            return
        if self.powerup_spawn_cooldown > 0:
            self.powerup_spawn_cooldown -= 1
            return
        # Try to spawn not overlapping walls/spawns
        margin = 40
        w, h = 26, 26
        for _ in range(30):
            x = random.randint(margin, WINDOW_WIDTH - margin - w)
            y = random.randint(margin, WINDOW_HEIGHT - margin - h)
            rect = pygame.Rect(x, y, w, h)
            if rect.colliderect(self.tank1.rect.inflate(80, 80)) or rect.colliderect(self.tank2.rect.inflate(80, 80)):
                continue
            blocked = False
            for wall in self.walls:
                if rect.colliderect(wall.rect.inflate(12, 12)):
                    blocked = True
                    break
            if blocked:
                continue
            kind = random.choice(PowerUp.TYPES)
            self.powerups.append(PowerUp(rect, kind))
            self.powerup_spawn_cooldown = int(FPS * random.uniform(5, 10))
            break


class PowerUp:
    TYPES = ("shield", "rapid", "speed")

    def __init__(self, rect: pygame.Rect, kind: str):
        self.rect = rect
        self.kind = kind
        self.life = int(FPS * 12)

    def update(self) -> None:
        if self.life > 0:
            self.life -= 1

    def draw(self, surface: pygame.Surface, ox: int = 0, oy: int = 0) -> None:
        r = self.rect.move(ox, oy)
        colors = {
            "shield": (120, 200, 255),
            "rapid": (255, 200, 120),
            "speed": (160, 255, 160),
        }
        c = colors.get(self.kind, (200, 200, 200))
        pygame.draw.rect(surface, c, r, border_radius=6)
        pygame.draw.rect(surface, (40, 40, 50), r, width=2, border_radius=6)

    def apply(self, tank: Tank) -> None:
        # Attach simple timed buffs to tank
        now = pygame.time.get_ticks()
        duration = 5000
        if self.kind == "shield":
            setattr(tank, "buff_shield_until", now + duration)
        elif self.kind == "rapid":
            setattr(tank, "buff_rapid_until", now + duration)
        elif self.kind == "speed":
            setattr(tank, "buff_speed_until", now + duration)


def tank_has_buff(tank: Tank, name: str) -> bool:
    return getattr(tank, name, 0) > pygame.time.get_ticks()


class Explosion:
    def __init__(self, x: float, y: float, max_radius: int, life: int) -> None:
        self.x = x
        self.y = y
        self.max_radius = max_radius
        self.life = life
        self.max_life = life

    def update(self) -> None:
        if self.life > 0:
            self.life -= 1

    def draw(self, surface: pygame.Surface, ox: int = 0, oy: int = 0) -> None:
        t = 1 - (self.life / self.max_life) if self.max_life > 0 else 1
        radius = int(self.max_radius * t)
        alpha_outer = int(120 * (1 - t))
        alpha_inner = int(200 * (1 - t))
        if radius <= 0:
            return
        # Shockwave ring
        ring_surface = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(ring_surface, (255, 200, 120, alpha_outer), (radius + 4, radius + 4), radius)
        pygame.draw.circle(ring_surface, (0, 0, 0, 0), (radius + 4, radius + 4), max(radius - 6, 1))
        surface.blit(ring_surface, (int(self.x - radius - 4 + ox), int(self.y - radius - 4 + oy)))
        # Core flash
        core_r = max(1, radius // 4)
        core_surface = pygame.Surface((core_r * 2 + 2, core_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(core_surface, (255, 240, 200, alpha_inner), (core_r + 1, core_r + 1), core_r)
        surface.blit(core_surface, (int(self.x - core_r + ox), int(self.y - core_r + oy)))


class NetManager:
    def __init__(self, role: str, port: int, host_ip: str | None = None) -> None:
        self.role = role
        self.port = port
        self.host_ip = host_ip
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        if role == 'host':
            self.sock.bind(('0.0.0.0', port))
        self.running = True
        self._latest_state: dict | None = None
        self._client_addr: tuple[str, int] | None = None
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._thread.start()

    def _rx_loop(self) -> None:
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
            except (BlockingIOError, OSError):
                time.sleep(0.005)
                continue
            except Exception:
                break
            try:
                msg = json.loads(data.decode('utf-8'))
            except Exception:
                continue
            if self.role == 'host':
                # Record client and update last input
                if msg.get('type') == 'input':
                    with self._lock:
                        self._client_addr = addr
                        self._latest_input = msg
            else:
                if msg.get('type') == 'state':
                    with self._lock:
                        self._latest_state = msg

    def send_input(self, payload: dict) -> None:
        if self.role != 'client':
            return
        if not self.host_ip:
            return
        try:
            self.sock.sendto(json.dumps(payload).encode('utf-8'), (self.host_ip, self.port))
        except Exception:
            pass

    def broadcast_state(self, state: dict) -> None:
        if self.role != 'host':
            return
        with self._lock:
            addr = self._client_addr
        if not addr:
            return
        try:
            self.sock.sendto(json.dumps(state).encode('utf-8'), addr)
        except Exception:
            pass

    def get_latest_state(self) -> dict | None:
        if self.role != 'client':
            return None
        with self._lock:
            return self._latest_state

    def get_latest_input(self) -> dict | None:
        if self.role != 'host':
            return None
        with self._lock:
            return getattr(self, '_latest_input', None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tanki 2D")
    parser.add_argument("--host", action="store_true", help="Run as host (server)")
    parser.add_argument("--join", type=str, default="", help="Join host at IP (e.g., 192.168.1.10)")
    parser.add_argument("--port", type=int, default=50555, help="UDP port")
    parser.add_argument("--menu", action="store_true", help="Force show main menu on start")
    parser.add_argument("--safe", action="store_true", help="Safe mode: disable audio/network features")
    args = parser.parse_args()

    # Global crash protection: log unhandled exceptions
    def excepthook(exctype, value, tb):
        try:
            os.makedirs("logs", exist_ok=True)
            with open(os.path.join("logs", "crash.log"), "a", encoding="utf-8") as f:
                f.write("\n=== Crash ===\n")
                f.write("".join(traceback.format_exception(exctype, value, tb)))
        except Exception:
            pass
        # Also print for console runs
        traceback.print_exception(exctype, value, tb)
        # Show minimal pygame fatal overlay if possible
        try:
            pygame.init()
            screen = pygame.display.set_mode((640, 200))
            font = pygame.font.SysFont("consolas", 18)
            screen.fill((20, 20, 24))
            t1 = font.render("Unexpected error. See logs/crash.log", True, (230,230,240))
            screen.blit(t1, (20, 80))
            pygame.display.flip()
            pygame.time.wait(2200)
        except Exception:
            pass
        sys.exit(1)

    sys.excepthook = excepthook

    # If explicit role via CLI — skip menu
    if args.host or args.join:
        net_role = None
        net = None
        if args.host:
            net_role = 'host'
            net = None if args.safe else NetManager(role='host', port=args.port)
        elif args.join:
            net_role = 'client'
            net = None if args.safe else NetManager(role='client', port=args.port, host_ip=args.join)
        Game(net_role=net_role, net=net).run()
        return

    # Otherwise show main menu
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Tanki 2D – Menu")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 32, bold=True)
    sfont = pygame.font.SysFont("consolas", 20)

    menu_items = [
        ("Local: Two players on one PC", "local"),
        ("Host: Create LAN game", "host"),
        ("Join: Connect to LAN host", "join"),
        ("Quit", "quit"),
    ]
    selected = 0
    input_ip = ""
    entering_ip = False
    port = 50555

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if entering_ip:
                    if event.key == pygame.K_ESCAPE:
                        entering_ip = False
                        input_ip = ""
                    elif event.key == pygame.K_RETURN:
                        # Start client with given IP
                        net = None if args.safe else NetManager(role='client', port=port, host_ip=input_ip or '127.0.0.1')
                        Game(net_role='client', net=net).run()
                        return
                    elif event.key == pygame.K_BACKSPACE:
                        input_ip = input_ip[:-1]
                    else:
                        ch = event.unicode
                        if ch.isdigit() or ch == '.' or ch == ':':
                            input_ip += ch
                else:
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % len(menu_items)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(menu_items)
                    elif event.key == pygame.K_RETURN:
                        action = menu_items[selected][1]
                        if action == 'local':
                            Game().run()
                            return
                        if action == 'host':
                            net = None if args.safe else NetManager(role='host', port=port)
                            Game(net_role='host', net=net).run()
                            return
                        if action == 'join':
                            entering_ip = True
                        if action == 'quit':
                            pygame.quit()
                            sys.exit(0)

        # Draw menu
        screen.fill((15, 17, 20))
        title = font.render("Tanki 2D", True, (230, 230, 240))
        screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 80))

        for idx, (label, _) in enumerate(menu_items):
            color = (240, 220, 120) if idx == selected and not entering_ip else (200, 205, 215)
            item = sfont.render(label, True, color)
            screen.blit(item, (WINDOW_WIDTH // 2 - 220, 200 + idx * 40))

        tip = sfont.render("Arrows: navigate, Enter: select, Esc: quit", True, (150, 155, 165))
        screen.blit(tip, (WINDOW_WIDTH // 2 - tip.get_width() // 2, WINDOW_HEIGHT - 50))

        if entering_ip:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))
            prompt = sfont.render("Enter host IP (e.g., 192.168.1.10) and press Enter", True, (230, 230, 240))
            screen.blit(prompt, (WINDOW_WIDTH // 2 - prompt.get_width() // 2, WINDOW_HEIGHT // 2 - 40))
            box_w = 360
            pygame.draw.rect(screen, (60, 60, 72), (WINDOW_WIDTH // 2 - box_w // 2, WINDOW_HEIGHT // 2, box_w, 36), border_radius=6)
            text = sfont.render(input_ip, True, (240, 240, 240))
            screen.blit(text, (WINDOW_WIDTH // 2 - box_w // 2 + 8, WINDOW_HEIGHT // 2 + 6))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()


