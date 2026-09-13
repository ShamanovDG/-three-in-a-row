import sqlite3
from copy import deepcopy
from datetime import datetime
from random import choice

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivy.utils import platform

if platform == "android":
    from jnius import autoclass, cast, PythonJavaClass, java_method
    from android.runnable import run_on_ui_thread

Window.clearcolor = (0.10, 0.08, 0.16, 1)


if platform == "android":
    # Слушатель инициализации Yandex Ads SDK.
    class YandexInitializationListener(PythonJavaClass):
        __javainterfaces__ = ["com/yandex/mobile/ads/common/InitializationListener"]
        __javacontext__ = "app"

        # ВАЖНО: __cinit__ у PythonJavaClass не принимает произвольные
        # kwargs — Cython передаёт ему те же аргументы, что были указаны
        # при создании объекта, даже если наш __init__ их не принимает.
        # Поэтому конструктор не принимает параметров: колбэк присваивается
        # отдельным атрибутом ПОСЛЕ создания объекта.
        on_complete = None

        @java_method("()V")
        def onInitializationCompleted(self):
            print("[YandexAds] SDK initialization completed")
            if self.on_complete:
                self.on_complete()

    # Слушатель событий жизненного цикла баннера.
class BannerAdEventListenerImpl(PythonJavaClass):
    __javainterfaces__ = [
        "com/yandex/mobile/ads/banner/BannerAdEventListener"
    ]
    __javacontext__ = "app"

    on_loaded = None
    on_failed = None

    @java_method("()V")
    def onAdLoaded(self):
        print("[YandexAds] Banner loaded successfully")
        if self.on_loaded:
            self.on_loaded()

    @java_method(
        "(Lcom/yandex/mobile/ads/common/AdRequestError;)V"
    )
    def onAdFailedToLoad(self, error):
        try:
            message = error.toString()
        except Exception:
            message = "<no error details>"

        print(f"[YandexAds] Banner failed to load: {message}")

        if self.on_failed:
            self.on_failed(message)

    @java_method("()V")
    def onAdClicked(self):
        print("[YandexAds] Banner clicked")

    @java_method(
        "(Lcom/yandex/mobile/ads/impressiondata/ImpressionData;)V"
    )
    def onImpression(self, impression_data):
        print("[YandexAds] Banner impression")


class YandexBannerAds:

    def destroy_banner(self):
        if platform != "android":
            return

        self._destroy_banner_on_ui_thread()


    @run_on_ui_thread
    def _destroy_banner_on_ui_thread(self):
        try:
            if self.banner_view is not None:
                self.banner_view.destroy()
                self.banner_view = None

            if self.banner_container is not None:
                parent = self.banner_container.getParent()
                if parent is not None:
                    parent.removeView(self.banner_container)
                self.banner_container = None

        except Exception as error:
            print(f"[YandexAds] Failed to destroy banner: {error}")

    def __init__(self, ad_unit_id):
        self.ad_unit_id = ad_unit_id
        self.banner_view = None
        self.banner_container = None
        self._init_listener = None
        self._ad_event_listener = None

    def show_banner(self):
        if platform != "android":
            return
        self._show_banner_on_ui_thread()

    @run_on_ui_thread
    def _show_banner_on_ui_thread(self):
        try:
            self._show_banner_impl()
        except Exception as exc:
            print(f"[YandexAds] Failed to show banner: {exc}")

    def _show_banner_impl(self):
        PythonActivity = autoclass(
            "org.kivy.android.PythonActivity"
        )
        FrameLayout = autoclass(
            "android.widget.FrameLayout"
        )
        FrameLayoutParams = autoclass(
            "android.widget.FrameLayout$LayoutParams"
        )
        Gravity = autoclass("android.view.Gravity")

        YandexAds = autoclass(
            "com.yandex.mobile.ads.common.YandexAds"
        )
        BannerAdView = autoclass(
            "com.yandex.mobile.ads.banner.BannerAdView"
        )
        BannerAdSize = autoclass(
            "com.yandex.mobile.ads.banner.BannerAdSize"
        )
        AdRequestBuilder = autoclass(
            "com.yandex.mobile.ads.common.AdRequest$Builder"
        )

        # Получаем текущую Android Activity.
        # Эту строку нельзя переносить ниже: activity используется далее.
        activity = PythonActivity.mActivity

        # Инициализируем SDK. Listener сохраняем в self, чтобы Python
        # не удалил Java callback сборщиком мусора до его вызова.
        self._init_listener = YandexInitializationListener()
        self._init_listener.on_complete = (
            lambda: print("[YandexAds] SDK initialization completed")
        )
        YandexAds.initialize(activity, self._init_listener)

        # android.R.id.content = 16908290.
        # Это корневой контейнер настоящего Android-окна.
        root_view = cast(
            "android.widget.FrameLayout",
            activity.findViewById(16908290)
        )

        # Создаём отдельный контейнер для баннера внизу экрана.
        self.banner_container = FrameLayout(activity)

        container_params = FrameLayoutParams(
            FrameLayoutParams.MATCH_PARENT,
            FrameLayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM
        )
        root_view.addView(self.banner_container, container_params)

        # Создаём Android View баннера.
        self.banner_view = BannerAdView(activity)

        # Вычисляем ширину устройства в dp.
        # Для BannerAdSize.sticky(...) нужны dp, а не реальные пиксели.
        display_metrics = activity.getResources().getDisplayMetrics()
        screen_width_px = display_metrics.widthPixels
        density = display_metrics.density
        screen_width_dp = int(screen_width_px / density)

        # Yandex Mobile Ads SDK 8.1.0:
        # sticky(), а не stickySize() и не getStickySize().
        self.banner_view.setAdSize(
            BannerAdSize.sticky(activity, screen_width_dp)
        )

        # Listener покажет в adb logcat, загрузилась ли реклама.
        self._ad_event_listener = BannerAdEventListenerImpl()

        self._ad_event_listener.on_loaded = (
            lambda: print("[YandexAds] Banner loaded successfully")
        )

        self._ad_event_listener.on_failed = (
            lambda error: print(
                f"[YandexAds] Banner failed to load: {error}"
            )
        )

        self.banner_view.setBannerAdEventListener(
            self._ad_event_listener
        )

        # Размещаем баннер по центру контейнера.
        banner_params = FrameLayoutParams(
            FrameLayoutParams.WRAP_CONTENT,
            FrameLayoutParams.WRAP_CONTENT,
            Gravity.CENTER_HORIZONTAL
        )
        self.banner_container.addView(
            self.banner_view,
            banner_params
        )

        # SDK 8: ID задаётся через AdRequest$Builder.
        request = AdRequestBuilder(self.ad_unit_id).build()

        # Отправляем запрос рекламы.
        self.banner_view.loadAd(request)


class ResultsRepository:
    def __init__(self, db_path="match3_results.db"):
        self.db_path = db_path
        self.setup()

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

    def load_results(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""
                SELECT id, played_at, score, target_score, won, time_left
                FROM game_results
                ORDER BY id DESC
            """).fetchall()


class RefillPlanner:
    def __init__(self, rows, cols, palette, max_tries=200):
        self.rows = rows
        self.cols = cols
        self.values = [value for _, value in palette]
        self.max_tries = max_tries

    def extract_values_grid(self, grid):
        return [
            [None if gem is None else gem.value for gem in row]
            for row in grid
        ]

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

    def has_any_match(self, values_grid):
        return bool(self.find_matches_in_values(values_grid))

    def swap_in_values(self, values_grid, r1, c1, r2, c2):
        new_grid = deepcopy(values_grid)
        new_grid[r1][c1], new_grid[r2][c2] = new_grid[r2][c2], new_grid[r1][c1]
        return new_grid

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

        _, spawned_values = self.build_random_refill(base_values, spawn_positions)
        return spawned_values


class Gem(Widget):
    def __init__(self, row, col, color_rgba, value, gem_size=72, **kwargs):
        super().__init__(**kwargs)
        self.row = row
        self.col = col
        self.value = value
        self.base_color = color_rgba

        self.size_hint = (None, None)
        self.size = (gem_size, gem_size)

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

    def _update_graphics(self, *_):
        self.circle.pos = self.pos
        self.circle.size = self.size

        shadow_dx = self.width * 0.05
        shadow_dy = self.height * 0.05
        self.shadow.pos = (self.x + shadow_dx, self.y - shadow_dy)
        self.shadow.size = self.size

        radius = min(self.width, self.height) / 2 - max(0.6, self.width * 0.01)
        self.stroke.width = max(1.0, self.width * 0.018)
        self.stroke.circle = (self.center_x, self.center_y, radius)

        self.label.pos = self.pos
        self.label.size = self.size
        self.label.text_size = self.size
        self.label.font_size = max(14, self.width * 0.33)


class Match3Board(FloatLayout):
    rows = 6
    cols = 6

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

        with self.canvas.before:
            self.board_bg_color = Color(1, 1, 1, 0.05)
            self.board_bg = RoundedRectangle(radius=[18])

        self.build_ui()
        self.bind(size=self.reposition_board, pos=self.reposition_board)

        Clock.schedule_once(self.build_board, 0)

    def safe_width(self):
        return max(self.width, 1)

    def safe_height(self):
        return max(self.height, 1)

    def board_side(self):
        return min(self.safe_width() * 0.95, self.safe_height() * 0.68)

    def gap_px(self):
        return max(4, self.board_side() * 0.018)

    def cell_size_px(self):
        gap = self.gap_px()
        return (self.board_side() - gap * (self.cols - 1)) / self.cols

    def gem_size_px(self):
        return self.cell_size_px() * 0.95

    def board_pixel_width(self):
        cell = self.cell_size_px()
        gap = self.gap_px()
        return self.cols * cell + (self.cols - 1) * gap

    def board_pixel_height(self):
        cell = self.cell_size_px()
        gap = self.gap_px()
        return self.rows * cell + (self.rows - 1) * gap

    def board_left(self):
        return (self.safe_width() - self.board_pixel_width()) / 2

    def board_bottom(self):
        lower_reserved = self.safe_height() * 0.08
        top_reserved = self.safe_height() * 0.16
        free_y = self.safe_height() - top_reserved - lower_reserved - self.board_pixel_height()
        return lower_reserved + max(0, free_y / 2)

    def board_rect(self):
        padding = self.cell_size_px() * 0.18
        return (
            self.board_left() - padding,
            self.board_bottom() - padding,
            self.board_pixel_width() + padding * 2,
            self.board_pixel_height() + padding * 2,
        )

    def grid_to_pos(self, row, col):
        cell = self.cell_size_px()
        gap = self.gap_px()
        gem = self.gem_size_px()

        x = self.board_left() + col * (cell + gap) + (cell - gem) / 2
        y = self.board_bottom() + (self.rows - 1 - row) * (cell + gap) + (cell - gem) / 2
        return x, y

    def spawn_pos_above(self, row, col, extra_rows=1):
        cell = self.cell_size_px()
        gap = self.gap_px()
        gem = self.gem_size_px()

        x = self.board_left() + col * (cell + gap) + (cell - gem) / 2
        y = self.board_bottom() + (self.rows - 1 - row + extra_rows) * (cell + gap) + (cell - gem) / 2
        return x, y

    def swipe_threshold_px(self):
        return max(18, min(self.safe_width(), self.safe_height()) * 0.025)

    def build_ui(self):
        self.timer_label = self.make_label(self.timer_text(), "left")
        self.score_label = self.make_label(self.score_text(), "right")
        self.status_label = self.make_label("", "center")

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

    def make_label(self, text, halign):
        label = Label(
            text=text,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            halign=halign,
            valign="middle",
        )
        label.text_size = label.size
        return label

    def make_button(self, text, callback):
        btn = Button(
            text=text,
            size_hint=(None, None),
            opacity=0,
            disabled=True,
            background_normal="",
            background_down="",
            background_color=(0.28, 0.24, 0.42, 1),
            color=(1, 1, 1, 1),
            bold=True,
        )
        btn.bind(on_release=lambda *_: callback())
        return btn

    def update_ui_positions(self, *_):
        w = self.safe_width()
        h = self.safe_height()

        side_margin = w * 0.04
        top_margin = h * 0.02

        small_font = max(18, min(w, h) * 0.028)
        status_font = max(24, min(w, h) * 0.05)

        panel_w = min(w * 0.32, 280)
        panel_h = max(42, h * 0.07)

        self.timer_label.font_size = small_font
        self.score_label.font_size = small_font
        self.status_label.font_size = status_font

        self.timer_label.size = (panel_w, panel_h)
        self.score_label.size = (panel_w, panel_h)
        self.status_label.size = (min(w * 0.75, 560), max(60, h * 0.1))

        self.timer_label.text_size = self.timer_label.size
        self.score_label.text_size = self.score_label.size
        self.status_label.text_size = self.status_label.size

        self.timer_label.pos = (
            side_margin,
            h - self.timer_label.height - top_margin,
        )

        self.score_label.pos = (
            w - self.score_label.width - side_margin,
            h - self.score_label.height - top_margin,
        )

        self.status_label.pos = (
            (w - self.status_label.width) / 2,
            h * 0.53,
        )

        btn_w = min(w * 0.34, 260)
        btn_h = max(46, h * 0.075)

        self.restart_button.size = (btn_w, btn_h)
        self.results_button.size = (btn_w, btn_h)

        self.restart_button.font_size = max(16, btn_h * 0.34)
        self.results_button.font_size = max(16, btn_h * 0.34)

        self.restart_button.pos = (
            (w - btn_w) / 2,
            h * 0.36,
        )

        self.results_button.pos = (
            (w - btn_w) / 2,
            h * 0.27,
        )

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

    def show_end_buttons(self):
        for btn in (self.restart_button, self.results_button):
            btn.opacity = 1
            btn.disabled = False

    def hide_end_buttons(self):
        for btn in (self.restart_button, self.results_button):
            btn.opacity = 0
            btn.disabled = True

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

    def score_text(self):
        return f"Очки: {self.score}"

    def timer_text(self):
        return f"Время: {self.time_left}"

    def update_score(self):
        self.score_label.text = self.score_text()

    def update_timer(self):
        self.timer_label.text = self.timer_text()

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

    def reposition_board(self, *_):
        bx, by, bw, bh = self.board_rect()
        radius = max(10, self.cell_size_px() * 0.2)
        self.board_bg.pos = (bx, by)
        self.board_bg.size = (bw, bh)
        self.board_bg.radius = [radius]

        gem_size = self.gem_size_px()
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem:
                    gem.size = (gem_size, gem_size)
                    gem.pos = self.grid_to_pos(row, col)

        self.update_ui_positions()

    def create_random_gem(self, row, col):
        color_rgba, value = choice(self.palette)
        return Gem(row, col, color_rgba, value, gem_size=self.gem_size_px())

    def create_gem_by_value(self, row, col, value):
        for color_rgba, v in self.palette:
            if v == value:
                return Gem(row, col, color_rgba, value, gem_size=self.gem_size_px())
        raise ValueError(f"Unknown gem value: {value}")

    def clear_board_widgets(self):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem and gem.parent:
                    self.remove_widget(gem)

    def build_board(self, *_):
        self.clear_board_widgets()

        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.create_random_gem(row, col)
                gem.pos = self.grid_to_pos(row, col)
                self.grid[row][col] = gem
                self.add_widget(gem)

        self.reposition_board()
        self.bring_ui_to_front()
        self.start_level_timer()
        Clock.schedule_once(self.resolve_matches, 0.1)

    def restart_level(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

        self.clear_board_widgets()
        self.reset_state()
        self.bring_ui_to_front()
        self.build_board()

    def start_level_timer(self):
        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.tick, 1)

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

    def gem_at_touch(self, pos):
        for row in range(self.rows):
            for col in range(self.cols):
                gem = self.grid[row][col]
                if gem and gem.collide_point(*pos):
                    return gem
        return None

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

        threshold = self.swipe_threshold_px()
        if abs(dx) < threshold and abs(dy) < threshold:
            return True

        drow, dcol = (
            (0, 1) if abs(dx) > abs(dy) and dx > 0 else
            (0, -1) if abs(dx) > abs(dy) else
            (-1, 0) if dy > 0 else
            (1, 0)
        )

        r1, c1 = selected.row, selected.col
        r2, c2 = r1 + drow, c1 + dcol

        if 0 <= r2 < self.rows and 0 <= c2 < self.cols:
            self.swap_gems(selected, self.grid[r2][c2])

        return True

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

    def find_matches(self):
        return {cell for group in self.find_match_groups() for cell in group}

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

    def show_score_gain(self, gained):
        self.score_label.texture_update()

        gain_label = Label(
            text=f" + {gained}",
            bold=True,
            font_size=self.score_label.font_size,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(max(70, self.safe_width() * 0.1), self.score_label.height),
            halign="left",
            valign="middle",
        )
        gain_label.text_size = gain_label.size
        gain_label.pos = (self.score_label.right - 2, self.score_label.y)

        self.add_widget(gain_label)

        def remove_gain(*_):
            if gain_label.parent:
                self.remove_widget(gain_label)

        Clock.schedule_once(remove_gain, 0.5)

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

    def swap_back(self, gem1, gem2, old_r1, old_c1, old_r2, old_c2):
        self.grid[old_r2][old_c2], self.grid[old_r1][old_c1] = self.grid[old_r1][old_c1], self.grid[old_r2][old_c2]
        gem1.row, gem1.col = old_r1, old_c1
        gem2.row, gem2.col = old_r2, old_c2

        self.animate_pair(
            gem1, self.grid_to_pos(old_r1, old_c1),
            gem2, self.grid_to_pos(old_r2, old_c2),
            0.18, lambda: setattr(self, "animating", False)
        )

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
                gem.size = (self.gem_size_px(), self.gem_size_px())

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


class Match3App(App):
    def build(self):
        self.board = Match3Board()
        Clock.schedule_once(self.init_ads, 1)
        return self.board

    def init_ads(self, *_):
        # Только для тестов.
        # Перед публикацией обязательно замените на настоящий ID R-M-...
        self.ads = YandexBannerAds("demo-banner-yandex")
        self.ads.show_banner()

    def on_stop(self):
        if hasattr(self, "ads") and self.ads:
            self.ads.destroy_banner()


Match3App().run()
