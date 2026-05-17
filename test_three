from random import choice
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Ellipse, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window


Window.clearcolor = (0.10, 0.08, 0.16, 1)


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
    margin_y = 80

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
        Clock.schedule_once(self.build_board, 0)

    def build_board(self, *args):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.create_random_gem(row, col)
                gem.pos = self.grid_to_pos(row, col)
                self.grid[row][col] = gem
                self.add_widget(gem)

        Clock.schedule_once(self.resolve_matches, 0.1)

    def create_random_gem(self, row, col):
        color_rgba, value = choice(self.palette)
        return Gem(row, col, color_rgba, value)

    def grid_to_pos(self, row, col):
        x = self.margin_x + col * (self.cell_size + self.gap)
        y = self.margin_y + (self.rows - 1 - row) * (self.cell_size + self.gap)
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
                Clock.schedule_once(self.resolve_matches, 0.02)

        anim1.bind(on_complete=finish)
        anim2.bind(on_complete=finish)

        anim1.start(gem1)
        anim2.start(gem2)

    def find_matches(self):
        matched = set()

        # Горизонтали
        for row in range(self.rows):
            count = 1
            for col in range(1, self.cols):
                current = self.grid[row][col]
                prev = self.grid[row][col - 1]

                if current and prev and current.value == prev.value:
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
                current = self.grid[row][col]
                prev = self.grid[row - 1][col]

                if current and prev and current.value == prev.value:
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

    def resolve_matches(self, *args):
        matches = self.find_matches()

        if not matches:
            self.animating = False
            return

        for row, col in matches:
            old_gem = self.grid[row][col]
            if old_gem:
                self.remove_widget(old_gem)

            new_gem = self.create_random_gem(row, col)
            new_gem.pos = self.grid_to_pos(row, col)
            self.grid[row][col] = new_gem
            self.add_widget(new_gem)

        Clock.schedule_once(self.resolve_matches, 0.05)


class Match3App(App):
    def build(self):
        return Match3Board()


Match3App().run()
