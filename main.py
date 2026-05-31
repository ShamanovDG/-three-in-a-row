'''
1. Добавлен счетчик очков с автообновлением.
2. Центрирование все картики по окку.
3. Просчитывание будущих шариков для создания возможности минимального хода.
4. Запрет на ходы без результата.
'''


from random import choice
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from copy import deepcopy
from random import choice

Window.clearcolor = (0.10, 0.08, 0.16, 1)


class RefillPlanner:
    def __init__(self, rows, cols, palette, max_tries=200):
        self.rows = rows
        self.cols = cols
        self.palette = palette
        self.values = [value for _, value in palette]
        self.max_tries = max_tries

    def extract_values_grid(self, grid):
        values_grid = []
        for row in range(self.rows):
            line = []
            for col in range(self.cols):
                gem = grid[row][col]
                line.append(None if gem is None else gem.value)
            values_grid.append(line)
        return values_grid

    def find_matches_in_values(self, values_grid):
        matched = set()

        for row in range(self.rows):
            count = 1
            for col in range(1, self.cols):
                cur = values_grid[row][col]
                prev = values_grid[row][col - 1]

                if cur is not None and prev is not None and cur == prev:
                    count += 1
                else:
                    if count >= 3:
                        for k in range(col - count, col):
                            matched.add((row, k))
                    count = 1

            if count >= 3:
                for k in range(self.cols - count, self.cols):
                    matched.add((row, k))

        for col in range(self.cols):
            count = 1
            for row in range(1, self.rows):
                cur = values_grid[row][col]
                prev = values_grid[row - 1][col]

                if cur is not None and prev is not None and cur == prev:
                    count += 1
                else:
                    if count >= 3:
                        for k in range(row - count, row):
                            matched.add((k, col))
                    count = 1

            if count >= 3:
                for k in range(self.rows - count, self.rows):
                    matched.add((k, col))

        return matched

    def has_any_match(self, values_grid):
        return len(self.find_matches_in_values(values_grid)) > 0

    def swap_in_values(self, values_grid, r1, c1, r2, c2):
        new_grid = deepcopy(values_grid)
        new_grid[r1][c1], new_grid[r2][c2] = new_grid[r2][c2], new_grid[r1][c1]
        return new_grid

    def has_possible_move(self, values_grid):
        for row in range(self.rows):
            for col in range(self.cols):
                if col + 1 < self.cols:
                    swapped = self.swap_in_values(values_grid, row, col, row, col + 1)
                    if self.has_any_match(swapped):
                        return True

                if row + 1 < self.rows:
                    swapped = self.swap_in_values(values_grid, row, col, row + 1, col)
                    if self.has_any_match(swapped):
                        return True

        return False

    def build_random_refill(self, values_grid, spawn_positions):
        trial = deepcopy(values_grid)
        spawned_values = {}

        for row, col in spawn_positions:
            value = choice(self.values)
            trial[row][col] = value
            spawned_values[(row, col)] = value

        return trial, spawned_values

    def generate_valid_refill(self, grid, spawn_positions):
        base_values = self.extract_values_grid(grid)

        for _ in range(self.max_tries):
            trial_grid, spawned_values = self.build_random_refill(base_values, spawn_positions)

            if self.has_any_match(trial_grid):
                continue

            if not self.has_possible_move(trial_grid):
                continue

            return spawned_values

        trial_grid, spawned_values = self.build_random_refill(base_values, spawn_positions)
        return spawned_values

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
            self.shadow = Ellipse(pos=(self.x + 4, self.y - 4), size=self.size)

            self.fill_color = Color(*color_rgba)
            self.circle = Ellipse(pos=self.pos, size=self.size)

            self.stroke_color = Color(1, 1, 1, 0.18)
            self.stroke = Line(width=1.2)

        self.label = Label(
            text=str(value),
            bold=True,
            font_size=24,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=self.size,
            pos=self.pos,
            text_size=self.size,
            halign='center',
            valign='middle',
        )
        self.add_widget(self.label)

        self.bind(pos=self._update_graphics, size=self._update_graphics)
        self._update_graphics()

    def _update_graphics(self, *args):
        self.circle.pos = self.pos
        self.circle.size = self.size

        self.shadow.pos = (self.x + 4, self.y - 4)
        self.shadow.size = self.size

        cx = self.center_x
        cy = self.center_y
        r = min(self.width, self.height) / 2 - 0.6
        self.stroke.circle = (cx, cy, r)

        self.label.pos = self.pos
        self.label.size = self.size
        self.label.text_size = self.size


class Match3Board(FloatLayout):
    rows = 6
    cols = 6
    cell_size = 78
    gap = 10
    margin_x = 24
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
        self.grid = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self.selected = None
        self.touch_start = None
        self.animating = False
        self.score = 0
        self.bind(size=self.reposition_board, pos=self.reposition_board)

        self.build_score_ui()
        Clock.schedule_once(self.build_board, 0)
        self.refill_planner = RefillPlanner(self.rows, self.cols, self.palette)

    def reposition_board(self, *args):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem:
                    gem.pos = self.grid_to_pos(row, col)

        self.update_score_ui_pos()

    def board_pixel_width(self):
        return self.cols * self.cell_size + (self.cols - 1) * self.gap

    def board_left(self):
        return (self.width - self.board_pixel_width()) / 2

    def bring_score_to_front(self):
        if self.score_label.parent:
            self.remove_widget(self.score_label)
        self.add_widget(self.score_label)

    def build_score_ui(self):
        self.score_label = Label(
            text=self.score_text(),
            bold=True,
            font_size=28,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(220, 50),
            halign='right',
            valign='middle',
        )
        self.score_label.text_size = self.score_label.size
        self.add_widget(self.score_label)

        self.bind(size=self.update_score_ui_pos, pos=self.update_score_ui_pos)
        Clock.schedule_once(self.update_score_ui_pos, 0)

    def create_gem_by_value(self, row, col, value):
        for color_rgba, v in self.palette:
            if v == value:
                return Gem(row, col, color_rgba, value)
        raise ValueError(f"Unknown gem value: {value}")

    def update_score_ui_pos(self, *args):
        right_margin = 80
        top_margin = 12

        x = self.width - self.score_label.width - right_margin
        y = self.height - self.score_label.height - top_margin

        self.score_label.pos = (x, y)

    def score_text(self):
        return f"Очки: {self.score}"

    def update_score(self):
        self.score_label.text = self.score_text()

    def build_board(self, *args):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.create_random_gem(row, col)
                gem.pos = self.grid_to_pos(row, col)
                self.grid[row][col] = gem
                self.add_widget(gem)

        self.bring_score_to_front()
        Clock.schedule_once(self.resolve_matches, 0.1)

    def create_random_gem(self, row, col):
        color_rgba, value = choice(self.palette)
        return Gem(row, col, color_rgba, value)

    def grid_to_pos(self, row, col):
        x = self.board_left() + col * (self.cell_size + self.gap)
        y = self.margin_y + (self.rows - 1 - row) * (self.cell_size + self.gap)
        return (x, y)

    def spawn_pos_above(self, row, col, extra_rows=1):
        x = self.board_left() + col * (self.cell_size + self.gap)
        y = self.margin_y + (self.rows - 1 - row + extra_rows) * (self.cell_size + self.gap)
        return (x, y)

    def gem_at_touch(self, pos):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem and gem.collide_point(*pos):
                    return gem
        return None

    def on_touch_down(self, touch):
        if self.animating:
            return True

        gem = self.gem_at_touch(touch.pos)
        if gem:
            self.selected = gem
            self.touch_start = touch.pos
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.animating:
            return True

        if not self.selected or not self.touch_start:
            return super().on_touch_up(touch)

        dx = touch.pos[0] - self.touch_start[0]
        dy = touch.pos[1] - self.touch_start[1]

        min_swipe = 25
        if abs(dx) < min_swipe and abs(dy) < min_swipe:
            self.selected = None
            self.touch_start = None
            return True

        if abs(dx) > abs(dy):
            drow, dcol = (0, 1) if dx > 0 else (0, -1)
        else:
            drow, dcol = (-1, 0) if dy > 0 else (1, 0)

        r1, c1 = self.selected.row, self.selected.col
        r2, c2 = r1 + drow, c1 + dcol

        if 0 <= r2 < self.rows and 0 <= c2 < self.cols:
            other = self.grid[r2][c2]
            self.swap_gems(self.selected, other)

        self.selected = None
        self.touch_start = None
        return True

    def swap_gems(self, gem1, gem2):
        self.animating = True

        r1, c1 = gem1.row, gem1.col
        r2, c2 = gem2.row, gem2.col

        pos1 = self.grid_to_pos(r1, c1)
        pos2 = self.grid_to_pos(r2, c2)

        self.grid[r1][c1], self.grid[r2][c2] = self.grid[r2][c2], self.grid[r1][c1]
        gem1.row, gem1.col = r2, c2
        gem2.row, gem2.col = r1, c1

        anim1 = Animation(pos=pos2, duration=0.18, t="out_quad")
        anim2 = Animation(pos=pos1, duration=0.18, t="out_quad")

        done = {"count": 0}

        def finish(*args):
            done["count"] += 1
            if done["count"] == 2:
                matches = self.find_matches()
                if matches:
                    Clock.schedule_once(self.resolve_matches, 0.02)
                else:
                    self.swap_back(gem1, gem2, r1, c1, r2, c2)

        anim1.bind(on_complete=finish)
        anim2.bind(on_complete=finish)

        anim1.start(gem1)
        anim2.start(gem2)

    def swap_back(self, gem1, gem2, old_r1, old_c1, old_r2, old_c2):
        self.grid[old_r2][old_c2], self.grid[old_r1][old_c1] = self.grid[old_r1][old_c1], self.grid[old_r2][old_c2]
        gem1.row, gem1.col = old_r1, old_c1
        gem2.row, gem2.col = old_r2, old_c2

        pos1 = self.grid_to_pos(old_r1, old_c1)
        pos2 = self.grid_to_pos(old_r2, old_c2)

        anim1 = Animation(pos=pos1, duration=0.18, t="out_quad")
        anim2 = Animation(pos=pos2, duration=0.18, t="out_quad")

        done = {"count": 0}

        def finish_back(*args):
            done["count"] += 1
            if done["count"] == 2:
                self.animating = False

        anim1.bind(on_complete=finish_back)
        anim2.bind(on_complete=finish_back)

        anim1.start(gem1)
        anim2.start(gem2)

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
                while end < self.cols:
                    nxt = self.grid[row][end]
                    if nxt and nxt.value == gem.value:
                        end += 1
                    else:
                        break

                length = end - start
                if length >= 3:
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
                while end < self.rows:
                    nxt = self.grid[end][col]
                    if nxt and nxt.value == gem.value:
                        end += 1
                    else:
                        break

                length = end - start
                if length >= 3:
                    groups.append([(r, col) for r in range(start, end)])

                start = end

        return groups

    def find_matches(self):
        matched = set()
        for group in self.find_match_groups():
            for cell in group:
                matched.add(cell)
        return matched

    def add_score_for_groups(self, groups):
        gained = 0
        for group in groups:
            gained += len(group) - 2

        old_score = self.score
        self.show_score_gain(gained)

        def apply_score(*args):
            self.score = old_score + gained
            self.update_score()

        Clock.schedule_once(apply_score, 0.5)
    
    def show_score_gain(self, gained):
        self.score_label.texture_update()

        gain_label = Label(
            text=f" + {gained}",
            bold=True,
            font_size=self.score_label.font_size,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(80, self.score_label.height),
            halign='left',
            valign='middle',
        )
        gain_label.text_size = gain_label.size

        text_width = self.score_label.texture_size[0]
        x = self.score_label.right - text_width + 2
        y = self.score_label.y

        gain_label.pos = (x + text_width - 4, y)
        self.add_widget(gain_label)

        def remove_gain(*args):
            if gain_label.parent:
                self.remove_widget(gain_label)

        Clock.schedule_once(remove_gain, 0.5)


    def resolve_matches(self, *args):
        groups = self.find_match_groups()
        matches = set()

        for group in groups:
            for cell in group:
                matches.add(cell)

        if not matches:
            self.animating = False
            return

        self.add_score_for_groups(groups)

        for row, col in matches:
            old_gem = self.grid[row][col]
            if old_gem:
                self.remove_widget(old_gem)
                self.grid[row][col] = None

        Clock.schedule_once(self.collapse_columns, 0.05)

    def collapse_columns(self, *args):
        self.animating = True
        animations_left = {"count": 0}

        def one_done(*_):
            animations_left["count"] -= 1
            if animations_left["count"] == 0:
                self.bring_score_to_front()
                Clock.schedule_once(self.resolve_matches, 0.05)

        for col in range(self.cols):
            existing = []

            for row in range(self.rows - 1, -1, -1):
                gem = self.grid[row][col]
                if gem is not None:
                    existing.append(gem)

            for row in range(self.rows):
                self.grid[row][col] = None

            target_row = self.rows - 1
            for gem in existing:
                old_row = gem.row
                gem.row = target_row
                gem.col = col
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
            spawn_positions = []

            for i in range(missing):
                new_row = target_row
                spawn_positions.append((new_row, col))
                target_row -= 1

            if spawn_positions:
                spawned_values = self.refill_planner.generate_valid_refill(self.grid, spawn_positions)

                for i, (new_row, col) in enumerate(spawn_positions):
                    value = spawned_values[(new_row, col)]
                    new_gem = self.create_gem_by_value(new_row, col, value)

                    start_pos = self.spawn_pos_above(new_row, col, extra_rows=missing - i)
                    end_pos = self.grid_to_pos(new_row, col)

                    new_gem.pos = start_pos
                    self.grid[new_row][col] = new_gem
                    self.add_widget(new_gem)

                    animations_left["count"] += 1
                    anim = Animation(pos=end_pos, duration=0.35, t="out_quad")
                    anim.bind(on_complete=one_done)
                    anim.start(new_gem)

                target_row -= 1

        self.bring_score_to_front()

        if animations_left["count"] == 0:
            Clock.schedule_once(self.resolve_matches, 0.05)


class Match3App(App):
    def build(self):
        return Match3Board()


Match3App().run()
