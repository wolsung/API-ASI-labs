#Игра змейка. Баги: 1)моментами жестко виснет игра 2)если нажать быстро вниз влево то игра завершится, а иногда бывает что змейка развернется на 180 градусов 3)при получении бонуски на замедление змейка останавливается хотя должна замедляться.
import pygame
import random
import sys
import time

# Инициализация Pygame
pygame.init()

# Константы
WIDTH, HEIGHT = 600, 600
GRID_SIZE = 20
GRID_WIDTH = WIDTH // GRID_SIZE
GRID_HEIGHT = HEIGHT // GRID_SIZE
FPS = 10

# Цвета
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 120, 255)
YELLOW = (255, 255, 0)
PURPLE = (180, 0, 255)
ORANGE = (255, 165, 0)
BACKGROUND = (20, 20, 30)
GRID_COLOR = (40, 40, 60)

# Направления
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Типы бонусов
SPEED_UP = 0
SPEED_DOWN = 1
SCORE_BOOST = 2
INVINCIBILITY = 3
BONUS_TYPES = [SPEED_UP, SPEED_DOWN, SCORE_BOOST, INVINCIBILITY]
BONUS_COLORS = {
    SPEED_UP: BLUE,
    SPEED_DOWN: PURPLE,
    SCORE_BOOST: YELLOW,
    INVINCIBILITY: ORANGE
}
BONUS_NAMES = {
    SPEED_UP: "Скорость+",
    SPEED_DOWN: "Скорость-",
    SCORE_BOOST: "Очки x2",
    INVINCIBILITY: "Неуязвимость"
}

class Snake:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.length = 3
        self.positions = [(GRID_WIDTH // 2, GRID_HEIGHT // 2)]
        self.direction = RIGHT
        self.score = 0
        self.grow_to = 3
        self.invincible = False
        self.invincible_time = 0
        
    def get_head_position(self):
        return self.positions[0]
    
    def turn(self, point):
        if self.length > 1 and (point[0] * -1, point[1] * -1) == self.direction:
            return
        else:
            self.direction = point
    
    def move(self):
        head = self.get_head_position()
        x, y = self.direction
        new_x = (head[0] + x) % GRID_WIDTH
        new_y = (head[1] + y) % GRID_HEIGHT
        new_position = (new_x, new_y)
        
        # Проверка на столкновение с собой
        if new_position in self.positions[1:] and not self.invincible:
            return False
        
        self.positions.insert(0, new_position)
        if len(self.positions) > self.grow_to:
            self.positions.pop()
            
        return True
    
    def draw(self, surface):
        for i, p in enumerate(self.positions):
            color = GREEN if not self.invincible else ORANGE
            if i == 0:  # Голова змейки
                r = pygame.Rect((p[0] * GRID_SIZE, p[1] * GRID_SIZE), (GRID_SIZE, GRID_SIZE))
                pygame.draw.rect(surface, color, r)
                pygame.draw.rect(surface, WHITE, r, 1)
                
                # Рисуем глаза
                eye_size = GRID_SIZE // 5
                if self.direction == RIGHT:
                    pygame.draw.circle(surface, BLACK, (r.x + GRID_SIZE - eye_size, r.y + eye_size*2), eye_size)
                    pygame.draw.circle(surface, BLACK, (r.x + GRID_SIZE - eye_size, r.y + GRID_SIZE - eye_size*2), eye_size)
                elif self.direction == LEFT:
                    pygame.draw.circle(surface, BLACK, (r.x + eye_size, r.y + eye_size*2), eye_size)
                    pygame.draw.circle(surface, BLACK, (r.x + eye_size, r.y + GRID_SIZE - eye_size*2), eye_size)
                elif self.direction == UP:
                    pygame.draw.circle(surface, BLACK, (r.x + eye_size*2, r.y + eye_size), eye_size)
                    pygame.draw.circle(surface, BLACK, (r.x + GRID_SIZE - eye_size*2, r.y + eye_size), eye_size)
                elif self.direction == DOWN:
                    pygame.draw.circle(surface, BLACK, (r.x + eye_size*2, r.y + GRID_SIZE - eye_size), eye_size)
                    pygame.draw.circle(surface, BLACK, (r.x + GRID_SIZE - eye_size*2, r.y + GRID_SIZE - eye_size), eye_size)
            else:
                r = pygame.Rect((p[0] * GRID_SIZE, p[1] * GRID_SIZE), (GRID_SIZE, GRID_SIZE))
                pygame.draw.rect(surface, color, r)
                pygame.draw.rect(surface, WHITE, r, 1)

class Food:
    def __init__(self):
        self.position = (0, 0)
        self.color = RED
        self.randomize_position()
        
    def randomize_position(self):
        self.position = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
        
    def draw(self, surface):
        r = pygame.Rect((self.position[0] * GRID_SIZE, self.position[1] * GRID_SIZE), (GRID_SIZE, GRID_SIZE))
        pygame.draw.rect(surface, self.color, r)
        pygame.draw.rect(surface, WHITE, r, 1)
        # Рисуем яблочко
        pygame.draw.line(surface, GREEN, 
                        (r.x + GRID_SIZE//2, r.y - 2), 
                        (r.x + GRID_SIZE//2, r.y - GRID_SIZE//3), 2)
        pygame.draw.line(surface, BROWN, 
                        (r.x + GRID_SIZE//2, r.y - GRID_SIZE//3), 
                        (r.x + GRID_SIZE//4, r.y - GRID_SIZE//2), 2)

class Bonus:
    def __init__(self):
        self.position = (0, 0)
        self.type = None
        self.color = WHITE
        self.active = False
        self.spawn_time = 0
        self.duration = 0
        
    def spawn(self):
        self.type = random.choice(BONUS_TYPES)
        self.color = BONUS_COLORS[self.type]
        self.position = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
        self.active = True
        self.spawn_time = time.time()
        
    def draw(self, surface):
        if not self.active:
            return
            
        r = pygame.Rect((self.position[0] * GRID_SIZE, self.position[1] * GRID_SIZE), (GRID_SIZE, GRID_SIZE))
        pygame.draw.rect(surface, self.color, r)
        pygame.draw.rect(surface, WHITE, r, 1)
        
        # Рисуем символ в зависимости от типа бонуса
        font = pygame.font.SysFont('Arial', 12, bold=True)
        if self.type == SPEED_UP:
            text = font.render(">>", True, WHITE)
        elif self.type == SPEED_DOWN:
            text = font.render("<<", True, WHITE)
        elif self.type == SCORE_BOOST:
            text = font.render("x2", True, BLACK)
        elif self.type == INVINCIBILITY:
            text = font.render("ЩИТ", True, BLACK)
            
        text_rect = text.get_rect(center=(r.x + GRID_SIZE//2, r.y + GRID_SIZE//2))
        surface.blit(text, text_rect)

# Дополнительные цвета
BROWN = (139, 69, 19)

def draw_grid(surface):
    for y in range(0, HEIGHT, GRID_SIZE):
        for x in range(0, WIDTH, GRID_SIZE):
            r = pygame.Rect((x, y), (GRID_SIZE, GRID_SIZE))
            pygame.draw.rect(surface, GRID_COLOR, r, 1)

def main():
    # Настройка окна
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Змейка с бонусами')
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('Arial', 20)
    
    # Создание объектов игры
    snake = Snake()
    food = Food()
    bonus = Bonus()
    
    # Переменные для управления игрой
    game_over = False
    paused = False
    last_bonus_spawn = time.time()
    bonus_effect_active = False
    bonus_effect_end = 0
    current_effect = None
    speed_multiplier = 1.0
    
    # Главный игровой цикл
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_SPACE and game_over:
                    # Рестарт игры
                    snake.reset()
                    food.randomize_position()
                    bonus.active = False
                    game_over = False
                    speed_multiplier = 1.0
                elif event.key == pygame.K_p:
                    # Пауза
                    paused = not paused
                elif not paused and not game_over:
                    if event.key == pygame.K_UP:
                        snake.turn(UP)
                    elif event.key == pygame.K_DOWN:
                        snake.turn(DOWN)
                    elif event.key == pygame.K_LEFT:
                        snake.turn(LEFT)
                    elif event.key == pygame.K_RIGHT:
                        snake.turn(RIGHT)
        
        if paused or game_over:
            # Отрисовка экрана паузы или завершения игры
            screen.fill(BACKGROUND)
            draw_grid(screen)
            snake.draw(screen)
            food.draw(screen)
            bonus.draw(screen)
            
            if game_over:
                game_over_font = pygame.font.SysFont('Arial', 50, bold=True)
                game_over_text = game_over_font.render("GAME OVER", True, RED)
                screen.blit(game_over_text, (WIDTH//2 - game_over_text.get_width()//2, HEIGHT//2 - 50))
                
                restart_font = pygame.font.SysFont('Arial', 20)
                restart_text = restart_font.render("Нажмите SPACE для рестарта", True, WHITE)
                screen.blit(restart_text, (WIDTH//2 - restart_text.get_width()//2, HEIGHT//2 + 20))
            else:
                pause_font = pygame.font.SysFont('Arial', 50, bold=True)
                pause_text = pause_font.render("PAUSE", True, YELLOW)
                screen.blit(pause_text, (WIDTH//2 - pause_text.get_width()//2, HEIGHT//2 - 25))
            
            pygame.display.update()
            clock.tick(FPS)
            continue
        
        # Проверяем активность бонусов
        current_time = time.time()
        if bonus_effect_active and current_time > bonus_effect_end:
            bonus_effect_active = False
            if current_effect == SPEED_UP or current_effect == SPEED_DOWN:
                speed_multiplier = 1.0
            elif current_effect == INVINCIBILITY:
                snake.invincible = False
        
        # Спавн бонуса каждые 10-15 секунд
        if not bonus.active and current_time - last_bonus_spawn > random.randint(1, 3):
            bonus.spawn()
            last_bonus_spawn = current_time
        
        # Движение змейки с учетом скорости
        if current_time % (0.1 / speed_multiplier) < 0.05:
            if not snake.move():
                game_over = True
                continue
            
            # Проверка на съедание еды
            if snake.get_head_position() == food.position:
                snake.grow_to += 25
        
                food.randomize_position()
                # Убедимся, что еда не появляется на змейке или бонусе
                while food.position in snake.positions or (bonus.active and food.position == bonus.position):
                    food.randomize_position()
            
            # Проверка на взятие бонуса
            if bonus.active and snake.get_head_position() == bonus.position:
                bonus.active = False
                bonus_effect_active = True
                bonus_effect_end = current_time + 115  # Эффект длится 5 секунд
                current_effect = bonus.type
                
                if bonus.type == SPEED_UP:
                    speed_multiplier = 5
                elif bonus.type == SPEED_DOWN:
                    speed_multiplier = 0.5
                elif bonus.type == SCORE_BOOST:
                    snake.score += 50
                elif bonus.type == INVINCIBILITY:
                    snake.invincible = True
        
        # Отрисовка
        screen.fill(BACKGROUND)
        draw_grid(screen)
        snake.draw(screen)
        food.draw(screen)
        bonus.draw(screen)
        
    
        
        # Отрисовка длины змейки
        length_text = font.render(f"Длина горыныча: {snake.grow_to}", True, WHITE)
        screen.blit(length_text, (5, 30))
        
        # Отрисовка активного бонуса
        if bonus_effect_active:
            effect_text = font.render(BONUS_NAMES[current_effect], True, BONUS_COLORS[current_effect])
            screen.blit(effect_text, (WIDTH - effect_text.get_width() - 10, 5))
            
            # Таймер бонуса
            timer_text = font.render(f"{int(bonus_effect_end - current_time)}с", True, WHITE)
            screen.blit(timer_text, (WIDTH - timer_text.get_width() - 10, 30))
        
        pygame.display.update()
        clock.tick(FPS * speed_multiplier)

if __name__ == "__main__":
    main()