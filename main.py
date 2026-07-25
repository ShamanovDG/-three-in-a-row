import sqlite3
from copy import deepcopy
from datetime import datetime
from random import choice

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

Window.clearcolor = (0.10, 0.08, 0.16, 1)


# Класс для работы с базой данных результатов игры #
class ResultsRepository:
    def __init__(self, db_path="match3_results.db"):
        self.db_path = db_path
        self.setup()

    # Создать таблицу результатов в базе данных, если она ещё не существует
    def setup(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS game_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    played_at TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    target_score INTEGER NOT NULL,
                    won INTEGER NOT NULL,
                    time_left INTEGER NOT NULL
                )
            """)

    # Сохранить один результат игры в базу данных
    def save_result(self, score, target_score, won, time_left):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO game_results (played_at, score, target_score, won, time_left)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                score,
                target_score,
                int(won),
                time_left
            ))

    # Загрузить список всех сохранённых результатов игр
    def load_results(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""
                SELECT id, played_at, score, target_score, won, time_left
                FROM game_results
                ORDER BY id DESC
            """).fetchall()


# Класс для подбора новых значений камней при дозаполнении поля
class RefillPlanner:
    def __init__(self, rows, cols, palette, max_tries=200):
        self.rows = rows
        self.cols = cols
        self.values = [value for _, value in palette]
        self.max_tries = max_tries

    # Построить сетку значений (value) из сетки объектов Gem/None
    def extract_values_grid(self, grid):
        return [
            [None if gem is None else gem.value for gem in row]
            for row in grid
        ]

    # Найти все совпадения по 3+ одинаковых значений в сетке
    def find_matches_in_values(self, values_grid):
        matched = set()

        for row in range(self.rows):
            count = 1
            for col in range(1, self.cols):
                cur, prev = values_grid[row][col], values_grid[row][col - 1]
                if cur is not None and cur == prev:
                    count += 1
                else:
                    if count >= 3:
                        matched.update((row, k) for k in range(col - count, col))
                    count = 1
            if count >= 3:
                matched.update((row, k) for k in range(self.cols - count, self.cols))

        for col in range(self.cols):
            count = 1
            for row in range(1, self.rows):
                cur, prev = values_grid[row][col], values_grid[row - 1][col]
                if cur is not None and cur == prev:
                    count += 1
                else:
                    if count >= 3:
                        matched.update((k, col) for k in range(row - count, row))
                    count = 1
            if count >= 3:
                matched.update((k, col) for k in range(self.rows - count, self.rows))

        return matched

    # Проверить, есть ли хотя бы одно совпадение в сетке значений
    def has_any_match(self, values_grid):
        return bool(self.find_matches_in_values(values_grid))

    # Вернуть копию сетки значений с обменом двух ячеек
    def swap_in_values(self, values_grid, r1, c1, r2, c2):
        new_grid = deepcopy(values_grid)
        new_grid[r1][c1], new_grid[r2][c2] = new_grid[r2][c2], new_grid[r1][c1]
        return new_grid

    # Проверить, существует ли хотя бы один ход, который даёт совпадение
    def has_possible_move(self, values_grid):
        for row in range(self.rows):
            for col in range(self.cols):
                if col + 1 < self.cols:
                    if self.has_any_match(self.swap_in_values(values_grid, row, col, row, col + 1)):
                        return True
                if row + 1 < self.rows:
                    if self.has_any_match(self.swap_in_values(values_grid, row, col, row + 1, col)):
                        return True
        return False

    # Сгенерировать случайные значения для новых камней в заданных позициях
    def build_random_refill(self, values_grid, spawn_positions):
        trial = deepcopy(values_grid)
        spawned_values = {}
        for row, col in spawn_positions:
            value = choice(self.values)
            trial[row][col] = value
            spawned_values[(row, col)] = value
        return trial, spawned_values

    # Сгенерировать дозаполнение без мгновенных совпадений, но с возможным ходом
    def generate_valid_refill(self, grid, spawn_positions):
        base_values = self.extract_values_grid(grid)

        for _ in range(self.max_tries):
            trial_grid, spawned_values = self.build_random_refill(base_values, spawn_positions)
            if self.has_any_match(trial_grid):
                continue
            if not self.has_possible_move(trial_grid):
                continue
            return spawned_values

        _, spawned_values = self.build_random_refill(base_values, spawn_positions)
        return spawned_values


# Класс, представляющий один камень на игровом поле
class Gem(Widget):
    def __init__(self, row, col, color_rgba, value, **kwargs):
        super().__init__(**kwargs)
        self.row = row
        self.col = col
        self.value = value

        self.size_hint = (None, None)
        self.size = (72, 72)

        with self.canvas.before:
            self.shadow_color = Color(0, 0, 0, 0.18)
            self.shadow = Ellipse(size=self.size)

            self.fill_color = Color(*color_rgba)
            self.circle = Ellipse(size=self.size)

            self.stroke_color = Color(1, 1, 1, 0.18)
            self.stroke = Line(width=1.2)

        self.label = Label(
            text=str(value),
            bold=True,
            font_size=24,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=self.size,
            text_size=self.size,
            halign="center",
            valign="middle",
        )
        self.add_widget(self.label)

        self.bind(pos=self._update_graphics, size=self._update_graphics)
        self._update_graphics()

    # Обновить графику камня (круг, тень, обводка и текст) при изменении размера/позиции
    def _update_graphics(self, *_):
        self.circle.pos = self.pos
        self.circle.size = self.size
        self.shadow.pos = (self.x + 4, self.y - 4)
        self.shadow.size = self.size

        radius = min(self.width, self.height) / 2 - 0.6
        self.stroke.circle = (self.center_x, self.center_y, radius)

        self.label.pos = self.pos
        self.label.size = self.size
        self.label.text_size = self.size


# Класс, представляющий игровое поле для игры «Match-3»
class Match3Board(FloatLayout):
    rows = 6
    cols = 6
    cell_size = 78
    gap = 10
    margin_y = 24

    palette = [
        ((0.92, 0.30, 0.36, 1), 1),
        ((0.25, 0.72, 0.98, 1), 2),
        ((0.38, 0.83, 0.43, 1), 3),
        ((0.95, 0.78, 0.28, 1), 4),
        ((0.70, 0.45, 0.95, 1), 5),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.target_score = 30
        self.initial_time = 60

        self.repo = ResultsRepository()
        self.refill_planner = RefillPlanner(self.rows, self.cols, self.palette)

        self.grid = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self.selected = None
        self.touch_start = None
        self.timer_event = None

        self.score = 0
        self.time_left = self.initial_time
        self.animating = False
        self.level_finished = False

        self.build_ui()
        self.bind(size=self.reposition_board, pos=self.reposition_board)

        Clock.schedule_once(self.build_board, 0)

    # ---------- UI ----------

    # Создать элементы интерфейса (метки и кнопки) и разместить их на доске
    def build_ui(self):
        self.score_label = self.make_label(self.score_text(), 28, (260, 50), "right")
        self.timer_label = self.make_label(self.timer_text(), 28, (220, 50), "left")
        self.status_label = self.make_label("", 42, (500, 80), "center")

        self.restart_button = self.make_button("Играть ещё раз", self.restart_level)
        self.results_button = self.make_button("Результаты", self.show_results_popup)

        for widget in [
            self.score_label,
            self.timer_label,
            self.status_label,
            self.restart_button,
            self.results_button,
        ]:
            self.add_widget(widget)

        self.hide_end_buttons()
        self.bind(size=self.update_ui_positions, pos=self.update_ui_positions)
        Clock.schedule_once(self.update_ui_positions, 0)

    # Создать метку с заданным текстом, размером шрифта, размером и выравниванием
    def make_label(self, text, font_size, size, halign):
        label = Label(
            text=text,
            bold=True,
            font_size=font_size,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=size,
            halign=halign,
            valign="middle",
        )
        label.text_size = label.size
        return label

    # Создать кнопку с заданным текстом и функцией обратного вызова
    def make_button(self, text, callback):
        btn = Button(
            text=text,
            size_hint=(None, None),
            size=(220, 56),
            opacity=0,
            disabled=True,
        )
        btn.bind(on_release=lambda *_: callback())
        return btn

    # Обновить позиции элементов интерфейса при изменении размера окна
    def update_ui_positions(self, *_):
        top_margin = 12
        side_margin = 30

        self.timer_label.pos = (
            side_margin,
            self.height - self.timer_label.height - top_margin,
        )
        self.score_label.pos = (
            self.width - self.score_label.width - side_margin,
            self.height - self.score_label.height - top_margin,
        )
        self.status_label.pos = (
            (self.width - self.status_label.width) / 2,
            self.height / 2 - self.status_label.height / 2 + 30,
        )
        self.restart_button.pos = (
            (self.width - self.restart_button.width) / 2,
            self.height / 2 - 110,
        )
        self.results_button.pos = (
            (self.width - self.results_button.width) / 2,
            self.height / 2 - 180,
        )

    # Переместить элементы интерфейса на передний план поверх камней
    def bring_ui_to_front(self):
        for widget in [
            self.score_label,
            self.timer_label,
            self.status_label,
            self.restart_button,
            self.results_button,
        ]:
            if widget.parent:
                self.remove_widget(widget)
            self.add_widget(widget)

    # Показать кнопки «Играть ещё раз» и «Результаты»
    def show_end_buttons(self):
        for btn in (self.restart_button, self.results_button):
            btn.opacity = 1
            btn.disabled = False

    # Скрыть кнопки «Играть ещё раз» и «Результаты»
    def hide_end_buttons(self):
        for btn in (self.restart_button, self.results_button):
            btn.opacity = 0
            btn.disabled = True

    # Показать всплывающее окно с таблицей сохранённых результатов
    def show_results_popup(self):
        rows = self.repo.load_results()

        root = GridLayout(cols=1, spacing=8, padding=10, size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        header = GridLayout(cols=6, size_hint_y=None, height=35, spacing=5)
        for text in ["ID", "Дата", "Очки", "Цель", "Победа", "Ост.время"]:
            header.add_widget(Label(text=text, bold=True, color=(1, 1, 1, 1)))
        root.add_widget(header)

        if not rows:
            root.add_widget(Label(text="Нет сохранённых результатов", size_hint_y=None, height=40))
        else:
            for row in rows:
                line = GridLayout(cols=6, size_hint_y=None, height=32, spacing=5)
                values = [
                    str(row[0]),
                    str(row[1]),
                    str(row[2]),
                    str(row[3]),
                    "Да" if row[4] else "Нет",
                    str(row[5]),
                ]
                for value in values:
                    line.add_widget(Label(text=value, color=(1, 1, 1, 1)))
                root.add_widget(line)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(root)

        close_btn = Button(text="Закрыть", size_hint_y=None, height=50)
        content = GridLayout(cols=1, spacing=10, padding=10)
        content.add_widget(scroll)
        content.add_widget(close_btn)

        popup = Popup(
            title="История матчей",
            content=content,
            size_hint=(0.9, 0.8),
            auto_dismiss=False,
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    # ---------- Методы управления состоянием игры ----------

    # Вернуть строку с текущим количеством очков
    def score_text(self):
        return f"Очки: {self.score}"

    # Вернуть строку с оставшимся временем
    def timer_text(self):
        return f"Время: {self.time_left}"

    # Обновить текст метки счёта
    def update_score(self):
        self.score_label.text = self.score_text()

    # Обновить текст метки таймера
    def update_timer(self):
        self.timer_label.text = self.timer_text()

    # Сбросить состояние игры: поле, выбор, счёт, время и статус
    def reset_state(self):
        self.grid = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self.selected = None
        self.touch_start = None
        self.animating = False
        self.level_finished = False
        self.score = 0
        self.time_left = self.initial_time

        self.status_label.text = ""
        self.update_score()
        self.update_timer()
        self.hide_end_buttons()

    # ---------- Board geometry ----------

    # Вычислить ширину игрового поля в пикселях
    def board_pixel_width(self):
        return self.cols * self.cell_size + (self.cols - 1) * self.gap

    # Вычислить координату X левого края игрового поля
    def board_left(self):
        return (self.width - self.board_pixel_width()) / 2

    # Преобразовать координаты сетки (row, col) в позицию на экране (x, y)
    def grid_to_pos(self, row, col):
        x = self.board_left() + col * (self.cell_size + self.gap)
        y = self.margin_y + (self.rows - 1 - row) * (self.cell_size + self.gap)
        return x, y

    # Вычислить позицию появления нового камня над текущей строкой
    def spawn_pos_above(self, row, col, extra_rows=1):
        x = self.board_left() + col * (self.cell_size + self.gap)
        y = self.margin_y + (self.rows - 1 - row + extra_rows) * (self.cell_size + self.gap)
        return x, y

    # Перерасчитать позиции всех камней при изменении размера окна
    def reposition_board(self, *_):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem:
                    gem.pos = self.grid_to_pos(row, col)
        self.update_ui_positions()

    # ---------- Board building ----------

    # Создать случайный камень для указанной клетки
    def create_random_gem(self, row, col):
        color_rgba, value = choice(self.palette)
        return Gem(row, col, color_rgba, value)

    # Создать камень по его значению с выбором нужного цвета из палитры
    def create_gem_by_value(self, row, col, value):
        for color_rgba, v in self.palette:
            if v == value:
                return Gem(row, col, color_rgba, value)
        raise ValueError(f"Unknown gem value: {value}")

    # Удалить все камни с поля из иерархии виджетов
    def clear_board_widgets(self):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem and gem.parent:
                    self.remove_widget(gem)

    # Построить начальное игровое поле и запустить таймер уровня
    def build_board(self, *_):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.create_random_gem(row, col)
                gem.pos = self.grid_to_pos(row, col)
                self.grid[row][col] = gem
                self.add_widget(gem)

        self.bring_ui_to_front()
        self.start_level_timer()
        Clock.schedule_once(self.resolve_matches, 0.1)

    # Полностью перезапустить уровень и начать игру заново
    def restart_level(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

        self.clear_board_widgets()
        self.reset_state()
        self.bring_ui_to_front()
        self.build_board()

    # ---------- Timer ----------

    # Запустить таймер уровня, вызывающий tick каждую секунду
    def start_level_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.tick, 1)

    # Обновить оставшееся время и завершить уровень при его истечении
    def tick(self, _dt):
        if self.level_finished:
            return False

        self.time_left -= 1
        if self.time_left <= 0:
            self.time_left = 0
            self.update_timer()
            self.finish_level(False)
            return False

        self.update_timer()

    # Завершить уровень, сохранить результат и показать статус/кнопки
    def finish_level(self, won):
        if self.level_finished:
            return

        self.level_finished = True
        self.animating = False

        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

        self.repo.save_result(self.score, self.target_score, won, self.time_left)

        if won:
            self.status_label.text = "Уровень пройден!"
            self.status_label.color = (0.45, 1, 0.55, 1)
        else:
            self.status_label.text = "Время вышло"
            self.status_label.color = (1, 0.4, 0.4, 1)

        self.show_end_buttons()
        self.bring_ui_to_front()

    # ---------- Input ----------

    # Найти камень, по которому кликнул/тапнул пользователь
    def gem_at_touch(self, pos):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem and gem.collide_point(*pos):
                    return gem
        return None

    # Обработать нажатие: выбрать камень для возможного обмена
    def on_touch_down(self, touch):
        if self.level_finished:
            return super().on_touch_down(touch)

        if self.animating:
            return True

        gem = self.gem_at_touch(touch.pos)
        if gem:
            self.selected = gem
            self.touch_start = touch.pos
            return True

        return super().on_touch_down(touch)

    # Обработать отпускание: определить направление свайпа и выполнить ход
    def on_touch_up(self, touch):
        if self.level_finished:
            return super().on_touch_up(touch)

        if self.animating:
            return True

        if not self.selected or not self.touch_start:
            return super().on_touch_up(touch)

        dx = touch.pos[0] - self.touch_start[0]
        dy = touch.pos[1] - self.touch_start[1]

        self.selected, selected = None, self.selected
        self.touch_start = None

        if abs(dx) < 25 and abs(dy) < 25:
            return True

        drow, dcol = (0, 1) if abs(dx) > abs(dy) and dx > 0 else \
                     (0, -1) if abs(dx) > abs(dy) else \
                     (-1, 0) if dy > 0 else (1, 0)

        r1, c1 = selected.row, selected.col
        r2, c2 = r1 + drow, c1 + dcol

        if 0 <= r2 < self.rows and 0 <= c2 < self.cols:
            self.swap_gems(selected, self.grid[r2][c2])

        return True

    # ---------- Match logic ----------

    # Найти все группы совпадающих камней по 3+ в строках и столбцах
    def find_match_groups(self):
        groups = []

        for row in range(self.rows):
            start = 0
            while start < self.cols:
                gem = self.grid[row][start]
                if gem is None:
                    start += 1
                    continue

                end = start + 1
                while end < self.cols and self.grid[row][end] and self.grid[row][end].value == gem.value:
                    end += 1

                if end - start >= 3:
                    groups.append([(row, c) for c in range(start, end)])
                start = end

        for col in range(self.cols):
            start = 0
            while start < self.rows:
                gem = self.grid[start][col]
                if gem is None:
                    start += 1
                    continue

                end = start + 1
                while end < self.rows and self.grid[end][col] and self.grid[end][col].value == gem.value:
                    end += 1

                if end - start >= 3:
                    groups.append([(r, col) for r in range(start, end)])
                start = end

        return groups

    # Вернуть множество всех координат клеток, входящих в совпадения
    def find_matches(self):
        return {cell for group in self.find_match_groups() for cell in group}

    # Начислить очки за группы совпадений с небольшой задержкой
    def add_score_for_groups(self, groups):
        gained = sum(len(group) - 2 for group in groups)
        old_score = self.score
        self.show_score_gain(gained)

        def apply_score(*_):
            if self.level_finished:
                return
            self.score = old_score + gained
            self.update_score()
            if self.score >= self.target_score:
                self.finish_level(True)

        Clock.schedule_once(apply_score, 0.5)

    # Показать временную надпись «+N» рядом со счётчиком очков
    def show_score_gain(self, gained):
        self.score_label.texture_update()

        gain_label = Label(
            text=f" + {gained}",
            bold=True,
            font_size=self.score_label.font_size,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(80, self.score_label.height),
            halign="left",
            valign="middle",
        )
        gain_label.text_size = gain_label.size

        text_width = self.score_label.texture_size[0]
        gain_label.pos = (self.score_label.right - 2, self.score_label.y)

        self.add_widget(gain_label)

        def remove_gain(*_):
            if gain_label.parent:
                self.remove_widget(gain_label)

        Clock.schedule_once(remove_gain, 0.5)

    # ---------- Animation ----------

    # Анимировать перемещение пары камней и вызвать callback после завершения обеих анимаций
    def animate_pair(self, gem1, pos1, gem2, pos2, duration, callback):
        done = {"count": 0}

        def finish(*_):
            done["count"] += 1
            if done["count"] == 2:
                callback()

        anim1 = Animation(pos=pos1, duration=duration, t="out_quad")
        anim2 = Animation(pos=pos2, duration=duration, t="out_quad")
        anim1.bind(on_complete=finish)
        anim2.bind(on_complete=finish)
        anim1.start(gem1)
        anim2.start(gem2)

    # Обменять два камня местами и решить, оставить ход или откатить его назад
    def swap_gems(self, gem1, gem2):
        self.animating = True

        r1, c1 = gem1.row, gem1.col
        r2, c2 = gem2.row, gem2.col

        self.grid[r1][c1], self.grid[r2][c2] = self.grid[r2][c2], self.grid[r1][c1]
        gem1.row, gem1.col = r2, c2
        gem2.row, gem2.col = r1, c1

        def after_swap():
            if self.find_matches():
                Clock.schedule_once(self.resolve_matches, 0.02)
            else:
                self.swap_back(gem1, gem2, r1, c1, r2, c2)

        self.animate_pair(
            gem1, self.grid_to_pos(r2, c2),
            gem2, self.grid_to_pos(r1, c1),
            0.18, after_swap
        )

    # Откатить обмен камней, если после хода не появилось совпадений
    def swap_back(self, gem1, gem2, old_r1, old_c1, old_r2, old_c2):
        self.grid[old_r2][old_c2], self.grid[old_r1][old_c1] = self.grid[old_r1][old_c1], self.grid[old_r2][old_c2]
        gem1.row, gem1.col = old_r1, old_c1
        gem2.row, gem2.col = old_r2, old_c2

        self.animate_pair(
            gem1, self.grid_to_pos(old_r1, old_c1),
            gem2, self.grid_to_pos(old_r2, old_c2),
            0.18, lambda: setattr(self, "animating", False)
        )

    # Удалить совпавшие камни и запустить перестройку столбцов
    def resolve_matches(self, *_):
        groups = self.find_match_groups()
        matches = {cell for group in groups for cell in group}

        if not matches:
            self.animating = False
            return

        self.add_score_for_groups(groups)

        for row, col in matches:
            gem = self.grid[row][col]
            if gem:
                self.remove_widget(gem)
                self.grid[row][col] = None

        Clock.schedule_once(self.collapse_columns, 0.05)

    # Сдвинуть камни вниз в каждом столбце и дозаполнить пустые клетки новыми камнями
    def collapse_columns(self, *_):
        self.animating = True
        animations_left = {"count": 0}

        def one_done(*_):
            animations_left["count"] -= 1
            if animations_left["count"] == 0:
                self.bring_ui_to_front()
                Clock.schedule_once(self.resolve_matches, 0.05)

        for col in range(self.cols):
            existing = [
                self.grid[row][col]
                for row in range(self.rows - 1, -1, -1)
                if self.grid[row][col] is not None
            ]

            for row in range(self.rows):
                self.grid[row][col] = None

            target_row = self.rows - 1
            for gem in existing:
                old_row = gem.row
                gem.row, gem.col = target_row, col
                self.grid[target_row][col] = gem
                target_pos = self.grid_to_pos(target_row, col)

                if old_row != target_row:
                    animations_left["count"] += 1
                    anim = Animation(pos=target_pos, duration=0.18, t="out_quad")
                    anim.bind(on_complete=one_done)
                    anim.start(gem)
                else:
                    gem.pos = target_pos

                target_row -= 1

            missing = target_row + 1
            spawn_positions = [(row, col) for row in range(target_row, -1, -1)]

            if spawn_positions:
                spawned_values = self.refill_planner.generate_valid_refill(self.grid, spawn_positions)

                for i, (new_row, col_) in enumerate(spawn_positions):
                    value = spawned_values[(new_row, col_)]
                    new_gem = self.create_gem_by_value(new_row, col_, value)
                    new_gem.pos = self.spawn_pos_above(new_row, col_, extra_rows=missing - i)
                    self.grid[new_row][col_] = new_gem
                    self.add_widget(new_gem)

                    animations_left["count"] += 1
                    anim = Animation(pos=self.grid_to_pos(new_row, col_), duration=0.35, t="out_quad")
                    anim.bind(on_complete=one_done)
                    anim.start(new_gem)

        self.bring_ui_to_front()

        if animations_left["count"] == 0:
            Clock.schedule_once(self.resolve_matches, 0.05)


# Главный класс Kivy-приложения
class Match3App(App):
    # Создать и вернуть корневой виджет приложения — игровое поле
    def build(self):
        return Match3Board()


# Точка входа: запуск игры
Match3App().run()
