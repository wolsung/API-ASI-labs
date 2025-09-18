import math
import random
import sys
import os
import pygame

# --- Settings ---
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 640
FPS = 60

PLAYER_SPEED = 300.0
PLAYER_COOLDOWN_MS = 250
PLAYER_LIVES = 3

BULLET_SPEED = 600.0
ENEMY_SPEED_MIN = 80.0
ENEMY_SPEED_MAX = 180.0
ENEMY_SPAWN_EVERY_MS = 800
WAVE_TIME_MS = 15000
MAX_ENEMIES_ON_SCREEN = 10

STAR_COUNT = 80

# Магазин/перезарядка
MAG_SIZE = 10
RELOAD_MS = 2000

# Upgrades
UPGRADE_DROP_CHANCE = 0.25
UPGRADE_SPEED = 120.0

FIRERATE_MULTIPLIER = 0.5
FIRERATE_DURATION_MS = 7000
SHIELD_DURATION_MS = 5000
MAG_BONUS_AMOUNT = 10
MAG_DURATION_MS = 8000
RELOAD_MULTIPLIER = 0.6
RELOAD_DURATION_MS = 8000

# Boss (с учётом сложности)
BOSS_TRIGGER_EVERY = 3
BOSS_BASE_HP = 140
BOSS_SPEED_Y = 60.0
BOSS_SPEED_X = 80.0
BOSS_WIDTH = 120
BOSS_HEIGHT = 60
BOSS_CONTACT_DAMAGE = True
BOSS_REWARD_AMMO = 15
BOSS_REWARD_FIRERATE_FACTOR = 1.01
BOSS_BULLET_SPEED = 240.0
BOSS_FIRE_COOLDOWN_P1 = 900
BOSS_FIRE_COOLDOWN_P2 = 700
BOSS_FIRE_COOLDOWN_P3 = 650
BOSS_BURST_COUNT_P3 = 2
BOSS_BURST_GAP_P3 = 200
BOSS_MAG_INCREASE = 5

# Вертикальное перемещение игрока и авто-щит после попадания
PLAYER_Y_MIN = SCREEN_HEIGHT - 170
PLAYER_Y_MAX = SCREEN_HEIGHT - 20
HIT_SHIELD_MS = 3000

# Меню
MENU_ITEMS = ["Играть", "Статистика", "Настройки", "Выход"]
MENU_SPACING = 36

# Ульта (ядерный взрыв)
ULT_KILLS_REQUIRED = 10
NUKE_BOSS_DAMAGE_FRAC = 0.30
NUKE_FLASH_MS = 550

# Сложность боссов
DIFFICULTY_NAMES = ["Легко", "Норма", "Сложно", "Безумие"]
DIFFICULTY_PROFILE = {
	"Легко":   {"hp_mult": 0.8, "bullet_speed_mult": 0.9, "cooldown_mult": 0.9},
	"Норма":   {"hp_mult": 1.0, "bullet_speed_mult": 1.0, "cooldown_mult": 1.0},
	"Сложно":  {"hp_mult": 1.25, "bullet_speed_mult": 1.15, "cooldown_mult": 1.15},
	"Безумие": {"hp_mult": 1.6, "bullet_speed_mult": 1.3, "cooldown_mult": 1.3},
}

# Оружия
WEAPON_DURATION_MS = 10000  # длительность временного оружия
WEAPON_TYPES = ["single", "double", "spread", "heavy", "rapid"]  # single — дефолт
WEAPON_NAMES = {
	"single": "Single",
	"double": "Twin",
	"spread": "Spread-3",
	"heavy": "Heavy",
	"rapid": "Rapid",
}

# Цвета
COLOR_BG = (8, 10, 20)
COLOR_WHITE = (235, 235, 235)
COLOR_GREEN = (90, 220, 120)
COLOR_RED = (240, 70, 70)
COLOR_YELLOW = (250, 210, 90)
COLOR_DIM = (160, 160, 160)
COLOR_BLUE = (90, 150, 255)
COLOR_ORANGE = (255, 170, 80)
COLOR_PURPLE = (170, 120, 255)
COLOR_CYAN = (120, 230, 230)


def clamp(value: float, low: float, high: float) -> float:
	return max(low, min(high, value))


def resource_path(*parts: str) -> str:
	base = os.path.dirname(os.path.abspath(__file__))
	return os.path.join(base, *parts)


class Star:
	def __init__(self, x: float, y: float, speed: float, size: int):
		self.x = x
		self.y = y
		self.speed = speed
		self.size = size

	def update(self, dt: float):
		self.y += self.speed * dt
		if self.y > SCREEN_HEIGHT + 2:
			self.y = -2
			self.x = random.uniform(0, SCREEN_WIDTH)

	def draw(self, surface: pygame.Surface):
		shade = int(clamp(120 + self.speed * 0.4, 120, 220))
		color = (shade, shade, shade)
		surface.fill(color, (int(self.x), int(self.y), self.size, self.size))


class Player(pygame.sprite.Sprite):
	def __init__(self, x: float, y: float):
		super().__init__()
		self.image = self._make_ship_surface()
		self.rect = self.image.get_rect(center=(x, y))
		self.mask = pygame.mask.from_surface(self.image)
		self.speed = PLAYER_SPEED
		self.cooldown_ms = PLAYER_COOLDOWN_MS
		self.last_shot_time = 0

		self.mag_size = MAG_SIZE
		self.reload_ms = RELOAD_MS
		self.ammo = self.mag_size
		self.is_reloading = False
		self.reload_end_time = 0

		self.cooldown_multiplier = 1.0
		self.firerate_until = 0
		self.shield_until = 0
		self.mag_bonus = 0
		self.mag_until = 0
		self.reload_multiplier = 1.0
		self.reload_until = 0

		self.permanent_firerate_multiplier = 1.0

		# Оружие
		self.weapon_type = "single"
		self.weapon_until = 0  # 0 — бесконечно (single), иначе таймер

	def _make_ship_surface(self) -> pygame.Surface:
		surf = pygame.Surface((40, 28), pygame.SRCALPHA)
		pygame.draw.polygon(surf, COLOR_GREEN, [(20, 0), (0, 26), (40, 26)])
		pygame.draw.polygon(surf, (120, 240, 160), [(20, 4), (8, 22), (32, 22)])
		pygame.draw.polygon(surf, (40, 120, 70), [(20, 0), (0, 26), (40, 26)], width=2)
		return surf

	def update(self, dt: float, keys: pygame.key.ScancodeWrapper):
		# движение — делается выше на основе кастомных биндингов (через Game), здесь резерв
		now = pygame.time.get_ticks()

		# завершение перезарядки
		if self.is_reloading and now >= self.reload_end_time:
			self.is_reloading = False
			self.ammo = self.effective_mag_size()

		# завершение апгрейдов
		if self.firerate_until and now >= self.firerate_until:
			self.cooldown_multiplier = 1.0
			self.firerate_until = 0
		if self.shield_until and now >= self.shield_until:
			self.shield_until = 0
		if self.mag_until and now >= self.mag_until:
			self.mag_bonus = 0
			self.mag_until = 0
			self.ammo = min(self.ammo, self.effective_mag_size())
		if self.reload_until and now >= self.reload_until:
			self.reload_multiplier = 1.0
			self.reload_until = 0

		# завершение временного оружия
		if self.weapon_type != "single" and self.weapon_until and now >= self.weapon_until:
			self.weapon_type = "single"
			self.weapon_until = 0

	def move(self, dt: float, move_left: bool, move_right: bool, move_up: bool, move_down: bool):
		dx = (-1.0 if move_left else 0.0) + (1.0 if move_right else 0.0)
		dy = (-1.0 if move_up else 0.0) + (1.0 if move_down else 0.0)
		self.rect.x += dx * self.speed * dt
		self.rect.y += dy * self.speed * dt
		self.rect.x = int(clamp(self.rect.x, 0, SCREEN_WIDTH - self.rect.width))
		self.rect.y = int(clamp(self.rect.y, PLAYER_Y_MIN, PLAYER_Y_MAX))

	def effective_cooldown(self) -> int:
		base = self.cooldown_ms * self.cooldown_multiplier
		# модификатор от оружия
		if self.weapon_type == "rapid":
			base *= 0.6
		elif self.weapon_type == "heavy":
			base *= 1.5
		eff = base / max(1.0, self.permanent_firerate_multiplier)
		return int(eff)

	def effective_reload_ms(self) -> int:
		return int(self.reload_ms * self.reload_multiplier)

	def effective_mag_size(self) -> int:
		return int(self.mag_size + self.mag_bonus)

	def is_shield_active(self) -> bool:
		return self.shield_until and pygame.time.get_ticks() < self.shield_until

	def can_shoot(self) -> bool:
		now = pygame.time.get_ticks()
		return (not self.is_reloading) and self.ammo > 0 and (now - self.last_shot_time) >= self.effective_cooldown()

	def shoot(self):
		# возвращает список пуль
		self.last_shot_time = pygame.time.get_ticks()
		self.ammo -= 1
		if self.ammo <= 0:
			self.is_reloading = True
			self.reload_end_time = self.last_shot_time + self.effective_reload_ms()

		bullets = []
		cx, top = self.rect.centerx, self.rect.top - 2
		if self.weapon_type == "single":
			bullets.append(Bullet(cx, top, 0.0, -BULLET_SPEED, damage=1, size=(4, 12)))
		elif self.weapon_type == "double":
			bullets.append(Bullet(cx - 8, top, 0.0, -BULLET_SPEED, damage=1, size=(4, 12)))
			bullets.append(Bullet(cx + 8, top, 0.0, -BULLET_SPEED, damage=1, size=(4, 12)))
		elif self.weapon_type == "spread":
			for ang in [-0.22, 0.0, 0.22]:
				vx = math.sin(ang) * BULLET_SPEED
				vy = -math.cos(ang) * BULLET_SPEED
				bullets.append(Bullet(cx, top, vx, vy, damage=1, size=(4, 12)))
		elif self.weapon_type == "heavy":
			# медленная, толстая, урон 3
			bullets.append(Bullet(cx, top, 0.0, -BULLET_SPEED * 0.75, damage=3, size=(8, 18), color=(255, 180, 120)))
		elif self.weapon_type == "rapid":
			bullets.append(Bullet(cx, top, 0.0, -BULLET_SPEED, damage=1, size=(3, 10)))
		else:
			bullets.append(Bullet(cx, top, 0.0, -BULLET_SPEED, damage=1, size=(4, 12)))
		return bullets

	def apply_firerate(self, duration_ms: int, multiplier: float):
		self.cooldown_multiplier = multiplier
		self.firerate_until = pygame.time.get_ticks() + duration_ms

	def apply_shield(self, duration_ms: int):
		self.shield_until = pygame.time.get_ticks() + duration_ms

	def apply_mag_bonus(self, duration_ms: int, bonus_amount: int):
		self.mag_bonus = bonus_amount
		self.mag_until = pygame.time.get_ticks() + duration_ms

	def apply_reload_boost(self, duration_ms: int, multiplier: float):
		self.reload_multiplier = multiplier
		self.reload_until = pygame.time.get_ticks() + duration_ms
		if self.is_reloading:
			now = pygame.time.get_ticks()
			remaining = max(0, self.reload_end_time - now)
			new_remaining = int(remaining * multiplier)
			self.reload_end_time = now + new_remaining

	def grant_boss_reward(self, ammo_amount: int, firerate_factor: float):
		# Гарантированно дать минимум +10 патрон; если магазин полон — расширить бонусом
		add = max(10, ammo_amount)
		target = self.ammo + add
		cap = self.effective_mag_size()
		if target <= cap:
			self.ammo = target
		else:
			overflow = target - cap
			self.mag_bonus += overflow
			self.ammo = cap + overflow
		self.permanent_firerate_multiplier *= firerate_factor

	def set_weapon(self, weapon_type: str, duration_ms: int):
		self.weapon_type = weapon_type
		self.weapon_until = pygame.time.get_ticks() + duration_ms


class Bullet(pygame.sprite.Sprite):
	def __init__(self, x: float, y: float, vx: float, vy: float, damage: int = 1, size=(4, 12), color=COLOR_YELLOW):
		super().__init__()
		w, h = size
		self.image = pygame.Surface((w, h), pygame.SRCALPHA)
		pygame.draw.rect(self.image, color, (0, 0, w, h))
		self.rect = self.image.get_rect(center=(x, y))
		self.vx = vx
		self.vy = vy
		self.damage = damage

	def update(self, dt: float):
		self.rect.x += int(self.vx * dt)
		self.rect.y += int(self.vy * dt)
		if self.rect.bottom < 0 or self.rect.top > SCREEN_HEIGHT or self.rect.right < 0 or self.rect.left > SCREEN_WIDTH:
			self.kill()


class Enemy(pygame.sprite.Sprite):
	def __init__(self, x: float, y: float, speed: float, hp: int = 1):
		super().__init__()
		self.base_image = self._make_enemy_surface()
		self.image = self.base_image.copy()
		self.rect = self.image.get_rect(center=(x, y))
		self.mask = pygame.mask.from_surface(self.image)
		self.speed = speed
		self.hp = hp
		self.time = 0.0
		self.hit_flash_until = 0

	def _make_enemy_surface(self) -> pygame.Surface:
		surf = pygame.Surface((32, 24), pygame.SRCALPHA)
		pygame.draw.rect(surf, COLOR_RED, (2, 2, 28, 20), border_radius=6)
		pygame.draw.rect(surf, (140, 40, 40), (2, 2, 28, 20), width=2, border_radius=6)
		pygame.draw.rect(surf, (250, 230, 230), (12, 8, 8, 4))
		return surf

	def update(self, dt: float):
		self.time += dt
		sway = math.sin(self.time * 2.5) * 30.0
		self.rect.y += int(self.speed * dt)
		self.rect.x += int(sway * dt * 10.0)
		if self.rect.top > SCREEN_HEIGHT + 10:
			self.kill()

		if self.alive():
			if pygame.time.get_ticks() < self.hit_flash_until:
				self.image = self.base_image.copy()
				overlay = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
				overlay.fill((255, 255, 255, 120))
				self.image.blit(overlay, (0, 0))
			else:
				self.image = self.base_image

	def damage(self, amount: int = 1):
		self.hp -= amount
		if self.hp <= 0:
			self.kill()
		else:
			self.hit_flash_until = pygame.time.get_ticks() + 120
		self.mask = pygame.mask.from_surface(self.image)


class Upgrade(pygame.sprite.Sprite):
	# kind in {"firerate", "shield", "mag", "reload", "life", "weapon_*"}
	def __init__(self, x: float, y: float, kind: str):
		super().__init__()
		self.kind = kind
		self.image = self._make_surface(kind)
		self.rect = self.image.get_rect(center=(x, y))
		self.speed = UPGRADE_SPEED

	def _make_surface(self, kind: str) -> pygame.Surface:
		surf = pygame.Surface((24, 24), pygame.SRCALPHA)
		if kind == "firerate":
			pygame.draw.circle(surf, COLOR_ORANGE, (12, 12), 11)
			pygame.draw.polygon(surf, (255, 240, 200), [(7, 15), (12, 5), (17, 15)])
		elif kind == "shield":
			pygame.draw.circle(surf, COLOR_BLUE, (12, 12), 11)
			pygame.draw.polygon(surf, (220, 240, 255), [(12, 5), (19, 10), (16, 18), (8, 18), (5, 10)])
		elif kind == "mag":
			pygame.draw.circle(surf, COLOR_PURPLE, (12, 12), 11)
			pygame.draw.rect(surf, (245, 230, 255), (6, 8, 12, 8), border_radius=3)
			pygame.draw.rect(surf, COLOR_WHITE, (6, 8, 12, 8), 2, border_radius=3)
		elif kind == "reload":
			pygame.draw.circle(surf, COLOR_CYAN, (12, 12), 11)
			pygame.draw.arc(surf, COLOR_WHITE, (4, 4, 16, 16), 0.0, 3.8, 2)
			pygame.draw.polygon(surf, COLOR_WHITE, [(17, 7), (20, 12), (14, 12)])
		elif kind == "life":
			pygame.draw.circle(surf, (255, 90, 120), (12, 12), 11)
			pygame.draw.polygon(surf, (255, 220, 230), [(12, 7), (17, 10), (16, 16), (12, 19), (8, 16), (7, 10)])
		elif kind.startswith("weapon_"):
			pygame.draw.circle(surf, (220, 200, 100), (12, 12), 11)
			pygame.draw.rect(surf, (250, 250, 180), (7, 8, 10, 8), border_radius=2)
			pygame.draw.rect(surf, COLOR_WHITE, (7, 8, 10, 8), 2, border_radius=2)
		else:
			pygame.draw.circle(surf, COLOR_WHITE, (12, 12), 11)
		pygame.draw.circle(surf, COLOR_WHITE, (12, 12), 11, width=2)
		return surf

	def update(self, dt: float):
		self.rect.y += int(self.speed * dt)
		if self.rect.top > SCREEN_HEIGHT + 10:
			self.kill()


class BossBullet(pygame.sprite.Sprite):
	def __init__(self, x: float, y: float, vx: float, vy: float):
		super().__init__()
		self.image = pygame.Surface((6, 6), pygame.SRCALPHA)
		pygame.draw.circle(self.image, (255, 120, 120), (3, 3), 3)
		self.rect = self.image.get_rect(center=(x, y))
		self.vx = vx
		self.vy = vy

	def update(self, dt: float):
		self.rect.x += int(self.vx * dt)
		self.rect.y += int(self.vy * dt)
		if self.rect.top > SCREEN_HEIGHT + 8 or self.rect.bottom < -8 or self.rect.right < -8 or self.rect.left > SCREEN_WIDTH + 8:
			self.kill()


class Boss(pygame.sprite.Sprite):
	def __init__(self, base_hp: int, bullet_speed_mult: float, cooldown_mult: float):
		super().__init__()
		self.image = self._make_surface()
		self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, -BOSS_HEIGHT))
		self.mask = pygame.mask.from_surface(self.image)
		self.hp_max = base_hp
		self.hp = base_hp
		self.time = 0.0
		self.direction_x = 1
		self.last_fire_time = 0
		self.phase = 1
		self.burst_left = 0
		self.next_burst_time = 0
		self.bullet_speed_mult = bullet_speed_mult
		self.cooldown_mult = cooldown_mult

	def _make_surface(self) -> pygame.Surface:
		surf = pygame.Surface((BOSS_WIDTH, BOSS_HEIGHT), pygame.SRCALPHA)
		pygame.draw.rect(surf, (200, 60, 60), (0, 10, BOSS_WIDTH, BOSS_HEIGHT - 20), border_radius=12)
		pygame.draw.rect(surf, (255, 120, 120), (6, 16, BOSS_WIDTH - 12, BOSS_HEIGHT - 32), border_radius=10)
		for x in range(20, BOSS_WIDTH - 10, 20):
			pygame.draw.rect(surf, (255, 230, 230), (x, 22, 10, 8), border_radius=3)
		pygame.draw.rect(surf, (120, 20, 20), (0, 10, BOSS_WIDTH, BOSS_HEIGHT - 20), 3, border_radius=12)
		return surf

	def update(self, dt: float):
		self.time += dt
		if self.rect.top < 30:
			self.rect.y += int(BOSS_SPEED_Y * dt)
		else:
			self.rect.x += int(self.direction_x * BOSS_SPEED_X * dt)
			if self.rect.left < 10:
				self.rect.left = 10
				self.direction_x = 1
			if self.rect.right > SCREEN_WIDTH - 10:
				self.rect.right = SCREEN_WIDTH - 10
				self.direction_x = -1
		ratio = self.hp / self.hp_max
		self.phase = 1 if ratio > 0.66 else (2 if ratio > 0.33 else 3)

	def try_fire(self, bullets_group: pygame.sprite.Group, player_pos: pygame.Vector2) -> bool:
		fired = False
		now = pygame.time.get_ticks()
		if self.phase == 1:
			if now - self.last_fire_time >= int(BOSS_FIRE_COOLDOWN_P1 / self.cooldown_mult):
				self.last_fire_time = now
				cx, cy = self.rect.centerx, self.rect.bottom - 10
				vy = BOSS_BULLET_SPEED * self.bullet_speed_mult
				bullets_group.add(BossBullet(cx, cy, 0.0, vy))
				fired = True
		elif self.phase == 2:
			if now - self.last_fire_time >= int(BOSS_FIRE_COOLDOWN_P2 / self.cooldown_mult):
				self.last_fire_time = now
				cx, cy = self.rect.centerx, self.rect.bottom - 10
				for ang in [-0.35, 0.0, 0.35]:
					vx = math.sin(ang) * BOSS_BULLET_SPEED * self.bullet_speed_mult
					vy = math.cos(ang) * BOSS_BULLET_SPEED * self.bullet_speed_mult
					bullets_group.add(BossBullet(cx, cy, vx, vy))
				fired = True
		else:
			if self.burst_left > 0 and now >= self.next_burst_time:
				self.burst_left -= 1
				self.next_burst_time = now + int(BOSS_BURST_GAP_P3 / self.cooldown_mult)
				self._fire_aimed(bullets_group, player_pos)
				fired = True
			elif self.burst_left == 0 and now - self.last_fire_time >= int(BOSS_FIRE_COOLDOWN_P3 / self.cooldown_mult):
				self.last_fire_time = now
				self.burst_left = BOSS_BURST_COUNT_P3
				self.next_burst_time = now
			if random.random() < 0.01:
				self._fire_spread(bullets_group)
				fired = True
		return fired

	def _fire_aimed(self, bullets_group: pygame.sprite.Group, player_pos: pygame.Vector2):
		cx, cy = self.rect.centerx, self.rect.bottom - 10
		dx, dy = player_pos.x - cx, player_pos.y - cy
		l = math.hypot(dx, dy) or 1.0
		vx = dx / l * (BOSS_BULLET_SPEED * 1.05 * self.bullet_speed_mult)
		vy = dy / l * (BOSS_BULLET_SPEED * 1.05 * self.bullet_speed_mult)
		bullets_group.add(BossBullet(cx, cy, vx, vy))

	def _fire_spread(self, bullets_group: pygame.sprite.Group):
		cx, cy = self.rect.centerx, self.rect.bottom - 10
		for ang in [-0.35, 0.0, 0.35]:
			vx = math.sin(ang) * BOSS_BULLET_SPEED * self.bullet_speed_mult
			vy = math.cos(ang) * BOSS_BULLET_SPEED * self.bullet_speed_mult
			bullets_group.add(BossBullet(cx, cy, vx, vy))

	def damage(self, amount: int = 1):
		self.hp -= amount
		if self.hp <= 0:
			self.kill()


class EnemySpawner:
	def __init__(self):
		self.spawn_interval_ms = ENEMY_SPAWN_EVERY_MS
		self.last_spawn_time = 0
		self.enemy_speed_min = ENEMY_SPEED_MIN
		self.enemy_speed_max = ENEMY_SPEED_MAX
		self.enemy_hp = 1
		self.wave_started_at = pygame.time.get_ticks()
		self.wave = 1
		self.boss_spawned_at_wave = None

	def maybe_spawn(self, enemies_group: pygame.sprite.Group, boss_active: bool):
		if boss_active:
			return
		if len(enemies_group) >= MAX_ENEMIES_ON_SCREEN:
			return
		now = pygame.time.get_ticks()
		if now - self.last_spawn_time >= self.spawn_interval_ms:
			self.last_spawn_time = now
			x = random.uniform(20, SCREEN_WIDTH - 20)
			y = -20
			speed = random.uniform(self.enemy_speed_min, self.enemy_speed_max)
			enemy = Enemy(x, y, speed, hp=self.enemy_hp)
			enemies_group.add(enemy)

	def update_wave(self, boss_active: bool):
		if boss_active:
			return
		now = pygame.time.get_ticks()
		if now - self.wave_started_at >= WAVE_TIME_MS:
			self.wave_started_at = now
			self.wave += 1
			self.spawn_interval_ms = max(300, int(self.spawn_interval_ms * 0.9))
			self.enemy_speed_min *= 1.06
			self.enemy_speed_max *= 1.06
			if self.wave % 3 == 0:
				self.enemy_hp += 1


class Game:
	def __init__(self):
		pygame.mixer.pre_init(44100, -16, 1, 256)
		pygame.init()
		pygame.display.set_caption("Space Battle")
		self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
		self.clock = pygame.time.Clock()

		self.font_large = pygame.font.SysFont("consolas", 36)
		self.font_small = pygame.font.SysFont("consolas", 20)

		self.stars = self._make_stars()

		self.all_sprites = pygame.sprite.Group()
		self.bullets = pygame.sprite.Group()
		self.enemies = pygame.sprite.Group()
		self.upgrades = pygame.sprite.Group()
		self.boss_group = pygame.sprite.Group()
		self.boss_bullets = pygame.sprite.Group()

		self.player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
		self.all_sprites.add(self.player)

		self.spawner = EnemySpawner()

		self.score = 0
		self.lives = PLAYER_LIVES
		self.is_game_over = False

		# Звук/музыка
		self.snd_shoot = None
		self.snd_dead = None
		self.snd_dead_person = None
		self.snd_boss_gauss = None
		self.bg_title_music_loaded = False
		self.bg_game_music_loaded = False
		self.title_music_path = None
		self.game_music_path = None

		# Громкости
		self.vol_master = 0.8
		self.vol_music = 0.8
		self.vol_shoot = 0.15
		self.vol_dead = 0.18
		self.vol_dead_person = 0.22
		self.vol_boss_gauss = 0.18

		self._load_sounds()
		self._apply_volumes()

		# Управление (переназначаемые клавиши)
		self.controls = {
			"move_left": pygame.K_a,
			"move_right": pygame.K_d,
			"move_up": pygame.K_w,
			"move_down": pygame.K_s,
			"shoot": pygame.K_SPACE,
			"ult": pygame.K_e,
			"select": pygame.K_RETURN,
			"back": pygame.K_ESCAPE,
		}
		self.keybind_actions = ["move_left", "move_right", "move_up", "move_down", "shoot", "ult"]
		self.keybind_index = 0
		self.awaiting_key = False  # ждём нажатия новой клавиши

		# Состояние
		self.state = "menu"  # menu | playing | stats | settings | keybinds | game_over
		self.menu_index = 0

		# Статистика
		self.stats_games_played = 0
		self.stats_high_score = 0
		self.stats_bosses_defeated = 0

		# Настройки (ползунки + сложность босса)
		self.settings_items = [
			("Master", "vol_master"),
			("Music", "vol_music"),
			("Shoot", "vol_shoot"),
			("Enemy Death", "vol_dead"),
			("Player Hit", "vol_dead_person"),
			("Boss Gauss", "vol_boss_gauss"),
			("Boss Difficulty", "boss_difficulty_index"),
			("Keybinds...", "open_keybinds"),
		]
		self.settings_index = 0
		self.slider_step = 0.05
		self.boss_difficulty_index = 1  # 0..3

		# Музыка в меню
		if self.bg_title_music_loaded and self.state == "menu":
			try:
				pygame.mixer.music.load(self.title_music_path)
				pygame.mixer.music.set_volume(self.vol_master * self.vol_music)
				pygame.mixer.music.play(-1)
			except Exception:
				pass

		self.boss_active = False
		self.boss_defeated_count = 0

		# Ульта
		self.ult_kills = 0
		self.ult_ready = False
		self.nuke_flash_until = 0

	def _load_sounds(self):
		def generate_tone(frequency_hz: float, duration_ms: int, volume: float = 0.1) -> pygame.mixer.Sound:
			sample_rate = 44100
			num_samples = int(sample_rate * (duration_ms / 1000.0))
			amplitude = int(32767 * volume)
			samples = bytearray()
			period = sample_rate / frequency_hz
			if period < 2:
				period = 2
			for i in range(num_samples):
				v = amplitude if (i % int(period)) < (period / 2) else -amplitude
				samples += int(v).to_bytes(2, byteorder="little", signed=True)
			return pygame.mixer.Sound(buffer=bytes(samples))

		try:
			if not pygame.mixer.get_init():
				pygame.mixer.init()

			shoot_path = resource_path("assets", "shoot.wav")
			dead_path = resource_path("assets", "dead.wav")
			dead_person_path = resource_path("assets", "dead_person.wav")
			gauss_path = resource_path("assets", "gauss2.wav")
			title_path = resource_path("assets", "background.wav")
			game_path = resource_path("assets", "game_bg.wav")

			if os.path.exists(shoot_path):
				self.snd_shoot = pygame.mixer.Sound(shoot_path)
			else:
				self.snd_shoot = generate_tone(900, 70, 0.12)

			if os.path.exists(dead_path):
				self.snd_dead = pygame.mixer.Sound(dead_path)
			else:
				self.snd_dead = generate_tone(120, 180, 0.14)

			if os.path.exists(dead_person_path):
				self.snd_dead_person = pygame.mixer.Sound(dead_person_path)
			else:
				self.snd_dead_person = generate_tone(200, 500, 0.13)

			if os.path.exists(gauss_path):
				self.snd_boss_gauss = pygame.mixer.Sound(gauss_path)
			else:
				self.snd_boss_gauss = None

			if os.path.exists(title_path):
				self.title_music_path = title_path
				self.bg_title_music_loaded = True
			else:
				self.bg_title_music_loaded = False

			if os.path.exists(game_path):
				self.game_music_path = game_path
				self.bg_game_music_loaded = True
			else:
				self.bg_game_music_loaded = False

		except Exception:
			self.snd_shoot = generate_tone(900, 70, 0.12)
			self.snd_dead = generate_tone(120, 180, 0.14)
			self.snd_dead_person = generate_tone(200, 500, 0.13)
			self.snd_boss_gauss = None
			self.bg_title_music_loaded = False
			self.bg_game_music_loaded = False
			self.title_music_path = None
			self.game_music_path = None

	def _apply_volumes(self):
		if self.snd_shoot:
			self.snd_shoot.set_volume(self.vol_master * self.vol_shoot)
		if self.snd_dead:
			self.snd_dead.set_volume(self.vol_master * self.vol_dead)
		if self.snd_dead_person:
			self.snd_dead_person.set_volume(self.vol_master * self.vol_dead_person)
		if self.snd_boss_gauss:
			self.snd_boss_gauss.set_volume(self.vol_master * self.vol_boss_gauss)
		try:
			pygame.mixer.music.set_volume(self.vol_master * self.vol_music)
		except Exception:
			pass

	def _make_stars(self):
		stars = []
		for _ in range(STAR_COUNT):
			x = random.uniform(0, SCREEN_WIDTH)
			y = random.uniform(0, SCREEN_HEIGHT)
			speed = random.uniform(20.0, 120.0)
			size = random.choice([1, 1, 1, 2])
			stars.append(Star(x, y, speed, size))
		return stars

	# ---------- MENU HANDLERS ----------
	def start_game(self):
		try:
			pygame.mixer.music.stop()
		except Exception:
			pass
		if self.bg_game_music_loaded:
			try:
				pygame.mixer.music.load(self.game_music_path)
				pygame.mixer.music.set_volume(self.vol_master * self.vol_music)
				pygame.mixer.music.play(-1)
			except Exception:
				pass

		self.all_sprites.empty()
		self.bullets.empty()
		self.enemies.empty()
		self.upgrades.empty()
		self.boss_group.empty()
		self.boss_bullets.empty()
		self.player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)
		self.all_sprites.add(self.player)
		self.spawner = EnemySpawner()
		self.score = 0
		self.lives = PLAYER_LIVES
		self.is_game_over = False
		self.boss_active = False
		self.ult_kills = 0
		self.ult_ready = False
		self.nuke_flash_until = 0
		self.state = "playing"

	def open_menu(self):
		try:
			pygame.mixer.music.stop()
		except Exception:
			pass
		if self.bg_title_music_loaded:
			try:
				pygame.mixer.music.load(self.title_music_path)
				pygame.mixer.music.set_volume(self.vol_master * self.vol_music)
				pygame.mixer.music.play(-1)
			except Exception:
				pass
		self.state = "menu"
		self.menu_index = 0

	def open_stats(self):
		self.state = "stats"

	def open_settings(self):
		self.state = "settings"
		self.settings_index = 0

	def open_keybinds(self):
		self.state = "keybinds"
		self.keybind_index = 0
		self.awaiting_key = False

	def quit_game(self):
		pygame.quit()
		sys.exit(0)

	# ---------- GAMEPLAY ----------
	def maybe_spawn_boss(self):
		if self.boss_active:
			return
		if self.spawner.wave >= 3 and self.spawner.wave % BOSS_TRIGGER_EVERY == 0:
			if self.spawner.boss_spawned_at_wave != self.spawner.wave:
				for e in list(self.enemies):
					e.kill()
				diff_name = DIFFICULTY_NAMES[self.boss_difficulty_index]
				profile = DIFFICULTY_PROFILE[diff_name]
				base_hp = int(BOSS_BASE_HP * profile["hp_mult"] * (1.0 + 0.2 * self.boss_defeated_count))
				bullet_speed_mult = profile["bullet_speed_mult"]
				cooldown_mult = profile["cooldown_mult"]
				boss = Boss(base_hp, bullet_speed_mult, cooldown_mult)
				self.boss_group.add(boss)
				self.boss_active = True
				self.spawner.boss_spawned_at_wave = self.spawner.wave

	def handle_input(self):
		keys = pygame.key.get_pressed()
		return keys

	def trigger_nuke(self):
		self.nuke_flash_until = pygame.time.get_ticks() + NUKE_FLASH_MS
		for e in list(self.enemies):
			e.kill()
			self.score += 10
		for b in list(self.boss_bullets):
			b.kill()
		if self.boss_active and len(self.boss_group) > 0:
			boss = list(self.boss_group)[0]
			damage = max(1, int(boss.hp_max * NUKE_BOSS_DAMAGE_FRAC))
			boss.damage(damage)
			if not boss.alive():
				self.player.grant_boss_reward(BOSS_REWARD_AMMO, BOSS_REWARD_FIRERATE_FACTOR)
				# Постоянно увеличиваем размер магазина после каждого босса и перезаряжаем до нового максимума
				self.player.mag_size += BOSS_MAG_INCREASE
				self.player.ammo = self.player.effective_mag_size()
				self.score += 150
				self.boss_defeated_count += 1
				self.stats_bosses_defeated += 1
				self.boss_active = False
				self.spawner.wave_started_at = pygame.time.get_ticks()
		self.ult_kills = 0
		self.ult_ready = False

	def update_playing(self, dt: float):
		for star in self.stars:
			star.update(dt)

		if self.is_game_over:
			return

		keys = self.handle_input()

		# движение по кастомным клавишам
		move_left = keys[self.controls["move_left"]]
		move_right = keys[self.controls["move_right"]]
		move_up = keys[self.controls["move_up"]]
		move_down = keys[self.controls["move_down"]]
		self.player.move(dt, move_left, move_right, move_up, move_down)
		self.player.update(dt, keys)

		# ульта
		if keys[self.controls["ult"]] and self.ult_ready:
			self.trigger_nuke()

		# стрельба
		if keys[self.controls["shoot"]] and self.player.can_shoot():
			new_bullets = self.player.shoot()
			for b in new_bullets:
				self.all_sprites.add(b)
				self.bullets.add(b)
			if self.snd_shoot:
				self.snd_shoot.play()

		self.spawner.update_wave(self.boss_active)
		self.maybe_spawn_boss()
		self.spawner.maybe_spawn(self.enemies, self.boss_active)

		self.enemies.update(dt)
		self.bullets.update(dt)
		self.upgrades.update(dt)
		self.boss_group.update(dt)
		self.boss_bullets.update(dt)

		if not self.boss_active:
			# коллизии пули -> враги (учитываем урон пули)
			hits = pygame.sprite.groupcollide(self.enemies, self.bullets, False, False)
			for enemy, bullet_list in hits.items():
				total_damage = 0
				for b in bullet_list:
					total_damage += getattr(b, "damage", 1)
					b.kill()
				was_alive = enemy.alive()
				enemy.damage(amount=total_damage)
				if was_alive and not enemy.alive():
					self.score += 10
					self.ult_kills = min(ULT_KILLS_REQUIRED, self.ult_kills + 1)
					if self.ult_kills >= ULT_KILLS_REQUIRED:
						self.ult_ready = True
					if self.snd_dead:
						self.snd_dead.play()
					# шанс дропа: апгрейд или оружие
					if random.random() < UPGRADE_DROP_CHANCE:
						drop_kind = self._random_drop_kind()
						up = Upgrade(enemy.rect.centerx, enemy.rect.centery, drop_kind)
						self.upgrades.add(up)
		else:
			player_pos = pygame.Vector2(self.player.rect.centerx, self.player.rect.centery)
			for boss in self.boss_group:
				if boss.try_fire(self.boss_bullets, player_pos):
					if self.snd_boss_gauss:
						self.snd_boss_gauss.play()
			for boss in list(self.boss_group):
				boss_hits = pygame.sprite.spritecollide(boss, self.bullets, True, pygame.sprite.collide_mask)
				if boss_hits:
					total = sum(getattr(b, "damage", 1) for b in boss_hits)
					boss.damage(amount=total)
					if not boss.alive():
						self.player.grant_boss_reward(BOSS_REWARD_AMMO, BOSS_REWARD_FIRERATE_FACTOR)
						# Постоянно увеличиваем размер магазина после каждого босса и перезаряжаем до нового максимума
						self.player.mag_size += BOSS_MAG_INCREASE
						self.player.ammo = self.player.effective_mag_size()
						self.score += 150
						self.boss_defeated_count += 1
						self.stats_bosses_defeated += 1
						self.boss_active = False
						self.spawner.wave_started_at = pygame.time.get_ticks()

		# Подбор предметов
		picked = pygame.sprite.spritecollide(self.player, self.upgrades, True)
		for up in picked:
			if up.kind == "firerate":
				self.player.apply_firerate(FIRERATE_DURATION_MS, FIRERATE_MULTIPLIER)
			elif up.kind == "shield":
				self.player.apply_shield(SHIELD_DURATION_MS)
			elif up.kind == "mag":
				self.player.apply_mag_bonus(MAG_DURATION_MS, MAG_BONUS_AMOUNT)
			elif up.kind == "reload":
				self.player.apply_reload_boost(RELOAD_DURATION_MS, RELOAD_MULTIPLIER)
			elif up.kind == "life":
				self.lives += 1
			elif up.kind.startswith("weapon_"):
				weapon = up.kind.replace("weapon_", "")
				if weapon in WEAPON_TYPES:
					self.player.set_weapon(weapon, WEAPON_DURATION_MS)

		# Урон
		damage_taken = False
		if not self.player.is_shield_active():
			if pygame.sprite.spritecollide(self.player, self.enemies, True, pygame.sprite.collide_mask):
				damage_taken = True
			if self.boss_active and BOSS_CONTACT_DAMAGE:
				if pygame.sprite.spritecollide(self.player, self.boss_group, False, pygame.sprite.collide_mask):
					damage_taken = True
			if pygame.sprite.spritecollide(self.player, self.boss_bullets, True):
				damage_taken = True
		else:
			pygame.sprite.spritecollide(self.player, self.enemies, True, pygame.sprite.collide_mask)
			pygame.sprite.spritecollide(self.player, self.boss_bullets, True)

		if damage_taken and not self.is_game_over:
			if self.snd_dead_person:
				self.snd_dead_person.play()
			self.lives -= 1
			self.player.apply_shield(HIT_SHIELD_MS)
			if self.lives <= 0:
				try:
					pygame.mixer.music.stop()
				except Exception:
					pass
				self.is_game_over = True
				self.stats_games_played += 1
				self.stats_high_score = max(self.stats_high_score, self.score)
				self.state = "game_over"

	def _random_drop_kind(self) -> str:
		# 60% обычные апгрейды, 40% оружие
		if random.random() < 0.6:
			return random.choice(["firerate", "shield", "mag", "reload", "life"])
		weapon = random.choice([w for w in WEAPON_TYPES if w != "single"])
		return f"weapon_{weapon}"

	# ---------- DRAW ----------
	def draw_hud(self, surface: pygame.Surface):
		score_surf = self.font_small.render(f"Score: {self.score}", True, COLOR_WHITE)
		lives_surf = self.font_small.render(f"Lives: {self.lives}", True, COLOR_WHITE)
		ammo_text = f"Ammo: {self.player.ammo}/{self.player.effective_mag_size()}"
		if self.player.is_reloading:
			ammo_text += " (reloading)"
		ammo_surf = self.font_small.render(ammo_text, True, COLOR_WHITE)
		wave_label = "Boss" if self.boss_active else f"Wave: {self.spawner.wave}"
		wave_surf = self.font_small.render(wave_label, True, COLOR_WHITE)

		# Ульта
		if self.ult_ready:
			ult_text = "ULT READY (" + pygame.key.name(self.controls["ult"]).upper() + ")"
			ult_color = (255, 200, 120)
		else:
			ult_text = f"Ult: {self.ult_kills}/{ULT_KILLS_REQUIRED}"
			ult_color = COLOR_DIM
		ult_surf = self.font_small.render(ult_text, True, ult_color)

		# Текущее оружие
		wpn_name = WEAPON_NAMES.get(self.player.weapon_type, self.player.weapon_type)
		if self.player.weapon_type != "single" and self.player.weapon_until:
			remain = max(0, (self.player.weapon_until - pygame.time.get_ticks()) // 1000)
			wpn_text = f"Weapon: {wpn_name} [{remain}s]"
		else:
			wpn_text = f"Weapon: {wpn_name}"
		wpn_surf = self.font_small.render(wpn_text, True, COLOR_WHITE)

		now = pygame.time.get_ticks()
		buffs = []
		if self.player.firerate_until and now < self.player.firerate_until:
			secs = max(0, (self.player.firerate_until - now) // 1000)
			buffs.append(f"FireRate x2 [{secs}s]")
		if self.player.is_shield_active():
			secs = max(0, (self.player.shield_until - now) // 1000)
			buffs.append(f"Shield [{secs}s]")
		if self.player.mag_until and now < self.player.mag_until:
			secs = max(0, (self.player.mag_until - now) // 1000)
			buffs.append(f"Mag +{self.player.mag_bonus} [{secs}s]")
		if self.player.reload_until and now < self.player.reload_until:
			secs = max(0, (self.player.reload_until - now) // 1000)
			buffs.append(f"Reload x{RELOAD_MULTIPLIER:.1f} [{secs}s]")
		if self.player.permanent_firerate_multiplier > 1.0:
			buffs.append(f"FR +{(self.player.permanent_firerate_multiplier - 1.0)*100:.0f}%")
		buffs_text = " | ".join(buffs) if buffs else ""
		buffs_surf = self.font_small.render(buffs_text, True, COLOR_WHITE)

		surface.blit(score_surf, (10, 8))
		surface.blit(lives_surf, (10, 30))
		surface.blit(ult_surf, (10, 52))
		surface.blit(wpn_surf, (10, 74))
		surface.blit(ammo_surf, (SCREEN_WIDTH - ammo_surf.get_width() - 10, 30))
		surface.blit(wave_surf, (SCREEN_WIDTH - wave_surf.get_width() - 10, 8))
		if buffs_text:
			surface.blit(buffs_surf, (10, 96))

		if self.boss_active and len(self.boss_group) > 0:
			boss = list(self.boss_group)[0]
			bar_w = SCREEN_WIDTH - 40
			bar_h = 10
			x = 20
			y = 120
			ratio = max(0.0, min(1.0, boss.hp / boss.hp_max))
			pygame.draw.rect(surface, (60, 20, 20), (x, y, bar_w, bar_h), border_radius=3)
			pygame.draw.rect(surface, (220, 60, 60), (x, y, int(bar_w * ratio), bar_h), border_radius=3)
			txt = self.font_small.render(f"Boss HP: {boss.hp}", True, COLOR_WHITE)
			surface.blit(txt, (x, y - 18))

	def draw_menu(self):
		self.screen.fill(COLOR_BG)
		for star in self.stars:
			star.draw(self.screen)
		title = self.font_large.render("Space Battle", True, COLOR_GREEN)
		self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 120))

		for i, item in enumerate(MENU_ITEMS):
			color = COLOR_WHITE if i == self.menu_index else COLOR_DIM
			label = self.font_small.render(item, True, color)
			self.screen.blit(label, (SCREEN_WIDTH // 2 - label.get_width() // 2, 240 + i * MENU_SPACING))

		#tip = self.font_small.render("Стрелки: навигация  Enter: выбрать  Esc: выход", True, COLOR_DIM)
		#self.screen.blit(tip, (SCREEN_WIDTH // 2 - tip.get_width() // 2, SCREEN_HEIGHT - 40))
		pygame.display.flip()

	def draw_stats(self):
		self.screen.fill(COLOR_BG)
		for star in self.stars:
			star.draw(self.screen)
		title = self.font_large.render("Статистика", True, COLOR_GREEN)
		self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

		lines = [
			f"Игр сыграно: {self.stats_games_played}",
			f"Рекорд: {self.stats_high_score}",
			f"Боссов побеждено: {self.stats_bosses_defeated}",
			"",
			"Esc: назад"
		]
		for i, t in enumerate(lines):
			lbl = self.font_small.render(t, True, COLOR_WHITE if t else COLOR_DIM)
			self.screen.blit(lbl, (SCREEN_WIDTH // 2 - lbl.get_width() // 2, 180 + i * 28))
		pygame.display.flip()

	def draw_slider(self, surface: pygame.Surface, x: int, y: int, w: int, h: int, value: float, label: str, selected: bool):
		pygame.draw.rect(surface, (40, 40, 60), (x, y, w, h), border_radius=4)
		fill_w = int(w * max(0.0, min(1.0, value)))
		pygame.draw.rect(surface, (90, 180, 120) if selected else (80, 120, 100), (x, y, fill_w, h), border_radius=4)
		txt = self.font_small.render(f"{label}: {int(value*100)}%", True, COLOR_WHITE)
		surface.blit(txt, (x, y - 22))

	def draw_settings(self):
		self.screen.fill(COLOR_BG)
		for star in self.stars:
			star.draw(self.screen)
		title = self.font_large.render("Настройки", True, COLOR_GREEN)
		self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 70))

		x = 60
		y = 140
		w = SCREEN_WIDTH - 120
		h = 16
		gap = 50

		for i, (label, attr) in enumerate(self.settings_items):
			selected = (i == self.settings_index)
			if attr == "boss_difficulty_index":
				diff_name = DIFFICULTY_NAMES[self.boss_difficulty_index]
				text = f"{label}: {diff_name}"
				col = COLOR_WHITE if selected else COLOR_DIM
				lbl = self.font_small.render(text, True, col)
				self.screen.blit(lbl, (x, y + i * gap))
				help_line = self.font_small.render("←/→: изменить", True, COLOR_DIM)
				self.screen.blit(help_line, (x + w - help_line.get_width(), y + i * gap))
			elif attr == "open_keybinds":
				text = f"{label}"
				col = COLOR_WHITE if selected else COLOR_DIM
				lbl = self.font_small.render(text + " (Enter)", True, col)
				self.screen.blit(lbl, (x, y + i * gap))
			else:
				value = getattr(self, attr)
				self.draw_slider(self.screen, x, y + i * gap, w, h, value, label, selected)

		help1 = self.font_small.render("Вверх/Вниз: выбрать  Влево/Вправо: изменить", True, COLOR_DIM)
		help2 = self.font_small.render("Enter: по умолчанию/открыть  Esc: назад", True, COLOR_DIM)
		self.screen.blit(help1, (SCREEN_WIDTH // 2 - help1.get_width() // 2, SCREEN_HEIGHT - 60))
		self.screen.blit(help2, (SCREEN_WIDTH // 2 - help2.get_width() // 2, SCREEN_HEIGHT - 36))

		pygame.display.flip()

	def draw_keybinds(self):
		self.screen.fill(COLOR_BG)
		for star in self.stars:
			star.draw(self.screen)
		title = self.font_large.render("Управление", True, COLOR_GREEN)
		self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 70))

		x = 60
		y = 140
		gap = 42
		for i, action in enumerate(self.keybind_actions):
			selected = (i == self.keybind_index)
			key_name = pygame.key.name(self.controls[action]).upper()
			label = {
				"move_left": "Движение влево",
				"move_right": "Движение вправо",
				"move_up": "Вверх",
				"move_down": "Вниз",
				"shoot": "Стрелять",
				"ult": "Ульта",
			}.get(action, action)
			text = f"{label}: {key_name}"
			col = COLOR_WHITE if selected else COLOR_DIM
			if selected and self.awaiting_key:
				text += "  [нажмите клавишу...]"
			lbl = self.font_small.render(text, True, col)
			self.screen.blit(lbl, (x, y + i * gap))

		help1 = self.font_small.render("Вверх/Вниз: выбрать  Enter: изменить  Esc: назад", True, COLOR_DIM)
		self.screen.blit(help1, (SCREEN_WIDTH // 2 - help1.get_width() // 2, SCREEN_HEIGHT - 40))
		pygame.display.flip()

	def draw_game_over(self):
		self.screen.fill(COLOR_BG)
		for star in self.stars:
			star.draw(self.screen)
		title = self.font_large.render("Game Over", True, COLOR_RED)
		score = self.font_small.render(f"Final Score: {self.score}", True, COLOR_WHITE)
		tip = self.font_small.render("Enter: в меню  R: заново  Esc: выйти", True, COLOR_DIM)
		self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 2 - 60))
		self.screen.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, SCREEN_HEIGHT // 2 - 16))
		self.screen.blit(tip, (SCREEN_WIDTH // 2 - tip.get_width() // 2, SCREEN_HEIGHT // 2 + 24))
		pygame.display.flip()

	def draw_playing(self):
		self.screen.fill(COLOR_BG)
		for star in self.stars:
			star.draw(self.screen)

		self.enemies.draw(self.screen)
		self.upgrades.draw(self.screen)
		self.boss_group.draw(self.screen)
		self.boss_bullets.draw(self.screen)
		for sprite in sorted(self.all_sprites, key=lambda s: 0 if isinstance(s, Bullet) else 1):
			self.screen.blit(sprite.image, sprite.rect)

		self.draw_hud(self.screen)

		if pygame.time.get_ticks() < self.nuke_flash_until:
			overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
			overlay.set_alpha(120)
			overlay.fill((255, 255, 255))
			self.screen.blit(overlay, (0, 0))

		pygame.display.flip()

	# ---------- LOOP ----------
	def run(self):
		while True:
			dt = self.clock.tick(FPS) / 1000.0

			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					self.quit_game()

				if event.type == pygame.KEYDOWN:
					# глобальный Esc
					if event.key == self.controls["back"]:
						if self.state == "playing":
							self.open_menu(); continue
						elif self.state in ("stats", "settings", "keybinds"):
							self.open_menu(); continue
						elif self.state == "menu":
							self.quit_game()
						elif self.state == "game_over":
							self.open_menu(); continue

					# состояния
					if self.state == "menu":
						if event.key in (pygame.K_UP, pygame.K_w):
							self.menu_index = (self.menu_index - 1) % len(MENU_ITEMS)
						elif event.key in (pygame.K_DOWN, pygame.K_s):
							self.menu_index = (self.menu_index + 1) % len(MENU_ITEMS)
						elif event.key == self.controls["select"] or event.key == pygame.K_SPACE:
							choice = MENU_ITEMS[self.menu_index]
							if choice == "Играть":
								self.start_game()
							elif choice == "Статистика":
								self.open_stats()
							elif choice == "Настройки":
								self.open_settings()
							elif choice == "Выход":
								self.quit_game()

					elif self.state == "settings":
						if event.key in (pygame.K_UP, pygame.K_w):
							self.settings_index = (self.settings_index - 1) % len(self.settings_items)
						elif event.key in (pygame.K_DOWN, pygame.K_s):
							self.settings_index = (self.settings_index + 1) % len(self.settings_items)
						elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d, self.controls["select"], pygame.K_SPACE):
							label, attr = self.settings_items[self.settings_index]
							if attr == "boss_difficulty_index":
								if event.key in (pygame.K_LEFT, pygame.K_a):
									self.boss_difficulty_index = (self.boss_difficulty_index - 1) % len(DIFFICULTY_NAMES)
								elif event.key in (pygame.K_RIGHT, pygame.K_d):
									self.boss_difficulty_index = (self.boss_difficulty_index + 1) % len(DIFFICULTY_NAMES)
								elif event.key in (self.controls["select"], pygame.K_SPACE):
									self.boss_difficulty_index = 1
							elif attr == "open_keybinds":
								if event.key in (self.controls["select"], pygame.K_SPACE):
									self.open_keybinds()
							else:
								value = getattr(self, attr)
								if event.key in (pygame.K_LEFT, pygame.K_a):
									value = max(0.0, round(value - self.slider_step, 2))
								elif event.key in (pygame.K_RIGHT, pygame.K_d):
									value = min(1.0, round(value + self.slider_step, 2))
								elif event.key in (self.controls["select"], pygame.K_SPACE):
									defaults = {
										"vol_master": 0.8,
										"vol_music": 0.8,
										"vol_shoot": 0.15,
										"vol_dead": 0.18,
										"vol_dead_person": 0.22,
										"vol_boss_gauss": 0.18,
									}
									value = defaults.get(attr, 0.8)
								setattr(self, attr, value)
								self._apply_volumes()

					elif self.state == "keybinds":
						if not self.awaiting_key:
							if event.key in (pygame.K_UP, pygame.K_w):
								self.keybind_index = (self.keybind_index - 1) % len(self.keybind_actions)
							elif event.key in (pygame.K_DOWN, pygame.K_s):
								self.keybind_index = (self.keybind_index + 1) % len(self.keybind_actions)
							elif event.key in (self.controls["select"], pygame.K_SPACE, pygame.K_RETURN):
								self.awaiting_key = True
						else:
							# Назначаем новую клавишу для выбранного действия
							action = self.keybind_actions[self.keybind_index]
							# Не позволяем назначать Esc как игровую кнопку (резерв для "назад")
							if event.key != pygame.K_ESCAPE:
								self.controls[action] = event.key
							self.awaiting_key = False

					elif self.state == "game_over":
						if event.key in (self.controls["select"], pygame.K_SPACE, pygame.K_RETURN):
							self.open_menu()
						elif event.key in (pygame.K_r,):
							self.start_game()

			# Рендер/апдейт по состояниям
			if self.state == "menu":
				for star in self.stars:
					star.update(dt)
				self.draw_menu(); continue

			if self.state == "stats":
				for star in self.stars:
					star.update(dt)
				self.draw_stats(); continue

			if self.state == "settings":
				for star in self.stars:
					star.update(dt)
				self.draw_settings(); continue

			if self.state == "keybinds":
				for star in self.stars:
					star.update(dt)
				self.draw_keybinds(); continue

			if self.state == "game_over":
				for star in self.stars:
					star.update(dt)
				self.draw_game_over(); continue

			if self.state == "playing":
				self.update_playing(dt)
				self.draw_playing(); continue


def main():
	Game().run()


if __name__ == "__main__":
	main()