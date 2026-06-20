from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, QTimer, Qt, Signal, QSize
from PySide6.QtGui import QBrush, QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_analyzer import build_prompt, build_rule_based_report, ollama_available, analyze
from app_paths import describe_gsi_installation, find_dota_gsi_targets, remember_manual_gsi_dir, resource_path, writable_config_path
from config import APP_NAME, APP_VERSION, GSI_AUTH_TOKEN, GSI_HOST, GSI_PORT, MAX_RECENT_MATCH_DETAILS, STEAM64
from dota_api import OpenDotaClient, OpenDotaError
from dota_meta import build_hero_meta_rows, match_history_rows
from dota_catalog import (
    download_catalog_assets,
    draft_analysis_markdown,
    get_hero_catalog,
    get_item_catalog,
    hero_details_markdown,
    hero_icon_path,
    item_build_analysis_markdown,
    item_details_markdown,
    item_icon_path,
    source_summary,
)
from profile_store import delete_profile, load_profiles, upsert_profile
from live_gsi import GSIReceiver, LiveCoach, local_probe, make_gsi_config_text, write_gsi_config
from pro_lab import build_learning_feed, download_replay, replays_dir, static_patterns
from map_assets import update_real_map_guides
from pro_players import build_role_comparison, generate_focus_plan, get_pros_for_role, style_matches
from role_detector import detect_role_detailed


class DataWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, steam64: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.steam64 = steam64

    def run(self) -> None:
        try:
            client = OpenDotaClient()
            summary = client.get_player_summary(
                self.steam64,
                recent_limit=20,
                detail_limit=MAX_RECENT_MATCH_DETAILS,
            )
            role_info = detect_role_detailed(summary.top_heroes, summary.heroes_by_id, summary.performances)
            comparison = build_role_comparison(summary.metrics, role_info["role"])
            styles = style_matches(summary.metrics, role_info["role"])
            focus_plan = generate_focus_plan(comparison, role_info["role"])
            self.loaded.emit(
                {
                    "summary": summary,
                    "role_info": role_info,
                    "comparison": comparison,
                    "styles": styles,
                    "focus_plan": focus_plan,
                }
            )
        except OpenDotaError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Непредвиденная ошибка загрузки: {exc}")


class AIWorker(QThread):
    finished_text = Signal(str)
    failed = Signal(str)

    def __init__(self, data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.data = data

    def run(self) -> None:
        try:
            summary = self.data["summary"]
            role_info = self.data["role_info"]
            comparison = self.data["comparison"]
            styles = self.data["styles"]
            focus_plan = self.data["focus_plan"]
            rule_report = build_rule_based_report(summary, role_info, comparison, styles, focus_plan)
            if ollama_available():
                prompt = build_prompt(summary, role_info, comparison, styles, focus_plan)
                llm_text = analyze(prompt)
                if llm_text.startswith("Локальная модель Ollama сейчас недоступна"):
                    self.finished_text.emit(llm_text + "\n\n---\n\n" + rule_report)
                else:
                    self.finished_text.emit(llm_text)
            else:
                self.finished_text.emit(rule_report)
        except Exception as exc:
            self.failed.emit(f"Не удалось построить AI-анализ: {exc}")


class ProLabWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, steam64: str, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.steam64 = steam64
        self.role = role

    def run(self) -> None:
        try:
            client = OpenDotaClient()
            self.loaded.emit(build_learning_feed(client, self.steam64, self.role, limit=8))
        except Exception as exc:
            self.failed.emit(f"Не удалось обновить Pro Lab: {exc}")


class ReplayDownloadWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, match_id: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.match_id = match_id
        self.label = label

    def run(self) -> None:
        try:
            ok, message = download_replay(OpenDotaClient(), self.match_id, label=self.label)
            self.done.emit(ok, message)
        except Exception as exc:
            self.done.emit(False, f"Не удалось скачать демку: {exc}")


class CatalogWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            client = OpenDotaClient()
            heroes = get_hero_catalog(client)
            items = get_item_catalog(client)
            summary = source_summary(heroes, items)
            if any(x.get("source") == "OpenDota" for x in heroes) or any(x.get("source") == "OpenDota" for x in items):
                asset_stats = download_catalog_assets(heroes, items, client)
                if asset_stats.get("hero_downloaded") or asset_stats.get("item_downloaded"):
                    summary += f"; иконки обновлены: герои {asset_stats.get('hero_downloaded', 0)}, предметы {asset_stats.get('item_downloaded', 0)}"
            else:
                summary += "; иконки не скачивались: нет соединения с OpenDota"
            self.loaded.emit({
                "heroes": heroes,
                "items": items,
                "summary": summary,
            })
        except Exception as exc:
            # The catalog still works offline; if anything unexpected happens,
            # send the bundled data instead of blocking the whole app.
            heroes = get_hero_catalog(None)
            items = get_item_catalog(None)
            self.loaded.emit({
                "heroes": heroes,
                "items": items,
                "summary": source_summary(heroes, items) + f"; offline fallback: {exc}",
            })


class MapAssetWorker(QThread):
    done = Signal(object)

    def run(self) -> None:
        try:
            self.done.emit(update_real_map_guides())
        except Exception as exc:
            self.done.emit({"ok": False, "message": f"Не удалось обновить карту: {exc}", "updated": 0})


class HeroMetaWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            client = OpenDotaClient()
            rows = build_hero_meta_rows(client)
            self.loaded.emit({"rows": rows, "updated_at": int(time.time())})
        except Exception as exc:
            self.failed.emit(f"Не удалось загрузить мету героев: {exc}")


class MatchHistoryWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, steam64: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.steam64 = steam64

    def run(self) -> None:
        try:
            client = OpenDotaClient()
            summary = client.get_player_summary(self.steam64, recent_limit=50, detail_limit=15)
            self.loaded.emit({"summary": summary, "rows": match_history_rows(summary)})
        except Exception as exc:
            self.failed.emit(f"Не удалось загрузить историю матчей: {exc}")


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "—", hint: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setWordWrap(True)
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("CardHint")
        self.hint_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.hint_label)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value_label.setText(value)
        if hint is not None:
            self.hint_label.setText(hint)


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(QIcon(str(resource_path("ui", "assets", "dota_coach.ico"))))
        self.resize(1320, 820)

        self.data: dict[str, Any] | None = None
        self.data_worker: DataWorker | None = None
        self.ai_worker: AIWorker | None = None
        self.pro_lab_worker: ProLabWorker | None = None
        self.replay_worker: ReplayDownloadWorker | None = None
        self.pro_lab_feed: dict[str, Any] | None = None
        self.catalog_worker: CatalogWorker | None = None
        self.map_asset_worker: MapAssetWorker | None = None
        self.hero_meta_worker: HeroMetaWorker | None = None
        self.match_history_worker: MatchHistoryWorker | None = None
        self.hero_catalog: list[dict[str, Any]] = []
        self.item_catalog: list[dict[str, Any]] = []
        self.hero_meta_rows: list[dict[str, Any]] = []
        self.match_history_rows: list[dict[str, Any]] = []
        self.saved_profiles: list[dict[str, str]] = load_profiles()
        self._populating_profiles = False

        self.gsi = GSIReceiver(GSI_HOST, GSI_PORT, GSI_AUTH_TOKEN)
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(1000)
        self.live_timer.timeout.connect(self.update_live_panel)

        self.cards: dict[str, StatCard] = {}
        self.live_labels: dict[str, QLabel] = {}

        self._build_ui()
        self._populate_profile_combo()
        self.load_catalog()
        self.load_hero_meta()
        self.load_data()
        QTimer.singleShot(700, self.autostart_gsi)

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
        self.gsi.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_sidebar(), 0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_dashboard_page())
        self.stack.addWidget(self._build_heroes_page())
        self.stack.addWidget(self._build_items_page())
        self.stack.addWidget(self._build_best_heroes_page())
        self.stack.addWidget(self._build_match_history_page())
        self.stack.addWidget(self._build_compare_page())
        self.stack.addWidget(self._build_live_page())
        self.stack.addWidget(self._build_pro_lab_page())
        self.stack.addWidget(self._build_ai_page())
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

    def _wrap_scroll_page(self, content: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setObjectName("PageScroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        content.setMinimumWidth(980)
        area.setWidget(content)
        return area

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title_box = QVBoxLayout()
        title = QLabel("Dota Coach AI")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Анализ игр, герои, предметы, драфты, live-GSI подсказки и Pro Lab")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)

        self.status_label = QLabel("Готовлю данные…")
        self.status_label.setObjectName("StatusPill")
        layout.addWidget(self.status_label)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(190)
        self.profile_combo.currentIndexChanged.connect(self.on_profile_selected)
        layout.addWidget(self.profile_combo)

        initial_account = self.saved_profiles[0]["steam_id"] if self.saved_profiles else ("" if int(STEAM64 or 0) == 0 else str(STEAM64))
        self.steam_input = QLineEdit(initial_account)
        self.steam_input.setPlaceholderText("Steam64 или account_id")
        self.steam_input.setMinimumWidth(210)
        layout.addWidget(self.steam_input)

        save_profile_btn = QPushButton("Сохранить игрока")
        save_profile_btn.clicked.connect(self.save_current_profile)
        layout.addWidget(save_profile_btn)

        delete_profile_btn = QPushButton("Удалить")
        delete_profile_btn.clicked.connect(self.delete_current_profile)
        layout.addWidget(delete_profile_btn)

        help_profile_btn = QPushButton("Как подключить")
        help_profile_btn.clicked.connect(self.show_profile_help)
        layout.addWidget(help_profile_btn)

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.load_data)
        layout.addWidget(refresh_btn)
        return header

    def show_account_help(self) -> None:
        QMessageBox.information(
            self,
            "Как подключить аккаунт",
            "1) У игрока должен быть публичный профиль матчей в Dota 2 / Steam.\n"
            "2) В верхнее поле можно вставить account_id, Steam64, ссылку OpenDota вида https://www.opendota.com/players/123 или Steam profile URL.\n"
            "3) Нажми «Сохранить игрока», чтобы добавить профиль в список.\n"
            "4) Нажми «Обновить» — Dashboard, История матчей, Лучшие герои и Pro Lab загрузятся для выбранного игрока.\n"
            "5) Для ИИ-ответов Ollama необязательна: без неё работает встроенный тренер. Если нужна локальная LLM, установи Ollama и модель из README."
        )


    def _populate_profile_combo(self, select_value: str | None = None) -> None:
        combo = getattr(self, "profile_combo", None)
        if combo is None:
            return
        self.saved_profiles = load_profiles()
        current = select_value or (self.steam_input.text().strip() if hasattr(self, "steam_input") else "")
        self._populating_profiles = True
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Профили игроков", "")
        for row in self.saved_profiles:
            label = f"{row.get('name', 'Игрок')} · {row.get('steam_id', '')}"
            combo.addItem(label, row.get("steam_id", ""))
        if current:
            for idx in range(combo.count()):
                if str(combo.itemData(idx)) == str(current):
                    combo.setCurrentIndex(idx)
                    break
        combo.blockSignals(False)
        self._populating_profiles = False

    def on_profile_selected(self, index: int) -> None:
        if getattr(self, "_populating_profiles", False):
            return
        combo = getattr(self, "profile_combo", None)
        if combo is None or index < 0:
            return
        value = str(combo.itemData(index) or "").strip()
        if value:
            self.steam_input.setText(value)
            self.load_data()

    def save_current_profile(self) -> None:
        value = self.steam_input.text().strip()
        if not value:
            QMessageBox.information(self, "Профиль", "Введи Steam64 или account_id игрока. Для другого человека нужен его публичный профиль матчей.")
            return
        default_name = f"Игрок {value[-4:]}"
        name, ok = QInputDialog.getText(self, "Сохранить игрока", "Название профиля:", text=default_name)
        if not ok:
            return
        self.saved_profiles = upsert_profile(name, value)
        self._populate_profile_combo(select_value=value)
        self.status_label.setText("Профиль сохранен")
        self.load_data()

    def delete_current_profile(self) -> None:
        value = self.steam_input.text().strip()
        if not value:
            return
        self.saved_profiles = delete_profile(value)
        self._populate_profile_combo()
        self.status_label.setText("Профиль удален")

    def show_profile_help(self) -> None:
        QMessageBox.information(
            self,
            "Как подключить другого игрока",
            "1) У игрока должна быть публичная история матчей Dota 2/Steam.\n"
            "2) Сверху можно вставить Steam64, короткий account_id, ссылку OpenDota /players/... или Steam profile /profiles/...\n"
            "3) Нажми «Сохранить игрока», дай профилю имя и нажми «Обновить».\n"
            "4) Dashboard, история матчей, герои, Лучшие герои и Pro Lab подтягиваются через OpenDota для выбранного профиля.\n"
            "5) Для обычной статистики локальный ИИ не нужен. Ollama нужна только для расширенного текста во вкладке «ИИ Тренер».\n"
            "6) Для Live Coach нужно отдельно установить cfg в Dota 2 и запустить игру с -gamestateintegration."
        )

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        buttons = [
            ("Dashboard", 0),
            ("Герои", 1),
            ("Предметы", 2),
            ("Лучшие герои", 3),
            ("История матчей", 4),
            ("Сравнение роли", 5),
            ("Live Coach", 6),
            ("Pro Lab", 7),
            ("ИИ Тренер", 8),
        ]
        for text, index in buttons:
            button = QPushButton(text)
            button.setMinimumHeight(42)
            button.clicked.connect(lambda checked=False, i=index: self.stack.setCurrentIndex(i))
            layout.addWidget(button)

        layout.addStretch(1)
        info = QLabel("Безопасный режим: приложение не читает память игры, не показывает скрытую информацию и принимает только легальные GSI-данные.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        layout.addWidget(info)
        return sidebar

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        grid = QGridLayout()
        grid.setSpacing(12)
        card_specs = [
            ("role", "Роль", "—", "Определяется по героям, линиям и экономике"),
            ("winrate", "Winrate", "—", "Последние матчи OpenDota"),
            ("kda", "K/D/A", "—", "Средние показатели"),
            ("economy", "GPM / XPM", "—", "Темп экономики и опыта"),
            ("farm", "LH/min", "—", "Темп фарма"),
            ("vision", "Vision", "—", "Варды и стаки, если есть детали матчей"),
        ]
        for idx, (key, title, value, hint) in enumerate(card_specs):
            card = StatCard(title, value, hint)
            self.cards[key] = card
            grid.addWidget(card, idx // 3, idx % 3)
        layout.addLayout(grid)

        tables = QHBoxLayout()
        tables.setSpacing(14)

        hero_box = QGroupBox("Любимые герои")
        hero_layout = QVBoxLayout(hero_box)
        self.heroes_table = QTableWidget(0, 4)
        self._setup_table(self.heroes_table, ["Герой", "Игры", "WR", "Роли героя"])
        hero_layout.addWidget(self.heroes_table)
        tables.addWidget(hero_box, 3)

        plan_box = QGroupBox("Фокус на следующие игры")
        plan_layout = QVBoxLayout(plan_box)
        self.focus_text = QTextEdit()
        self.focus_text.setReadOnly(True)
        self.focus_text.setMinimumHeight(180)
        plan_layout.addWidget(self.focus_text)
        tables.addWidget(plan_box, 2)
        layout.addLayout(tables, 1)

        self.errors_text = QLabel("")
        self.errors_text.setObjectName("Warning")
        self.errors_text.setWordWrap(True)
        layout.addWidget(self.errors_text)
        return page

    def _build_heroes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("Герои: база, контрпики и драфт 5v5")
        title.setObjectName("SectionTitle")
        top.addWidget(title, 1)
        self.catalog_status = QLabel("Загружаю базу героев и предметов…")
        self.catalog_status.setObjectName("StatusPill")
        top.addWidget(self.catalog_status)
        refresh_btn = QPushButton("Обновить базу и иконки")
        refresh_btn.clicked.connect(self.load_catalog)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        filters = QHBoxLayout()
        self.hero_search = QLineEdit()
        self.hero_search.setPlaceholderText("Поиск героя")
        self.hero_search.textChanged.connect(self._fill_catalog_heroes)
        filters.addWidget(self.hero_search, 1)
        self.hero_attr_filter = QComboBox()
        self.hero_attr_filter.addItems(["Все типы", "Сила", "Ловкость", "Интеллект", "Универсальность"])
        self.hero_attr_filter.currentIndexChanged.connect(self._fill_catalog_heroes)
        filters.addWidget(self.hero_attr_filter)
        layout.addLayout(filters)

        middle = QHBoxLayout()
        self.catalog_heroes_table = QTableWidget(0, 4)
        self._setup_table(self.catalog_heroes_table, ["", "Герой", "Тип", "Роли"])
        self.catalog_heroes_table.setIconSize(QSize(76, 44))
        self.catalog_heroes_table.verticalHeader().setDefaultSectionSize(50)
        self.catalog_heroes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.catalog_heroes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.catalog_heroes_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.catalog_heroes_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.catalog_heroes_table.itemSelectionChanged.connect(self._show_selected_catalog_hero)
        middle.addWidget(self.catalog_heroes_table, 3)

        detail_box = QGroupBox("Информация, контрпики и контр-предметы")
        detail_layout = QVBoxLayout(detail_box)
        self.hero_detail_text = QTextEdit()
        self.hero_detail_text.setReadOnly(True)
        self.hero_detail_text.setMarkdown("Выбери героя слева.")
        detail_layout.addWidget(self.hero_detail_text)
        middle.addWidget(detail_box, 2)
        layout.addLayout(middle, 2)

        draft_box = QGroupBox("Мини-игра: собери драфт 5 на 5")
        draft_layout = QVBoxLayout(draft_box)
        draft_controls = QHBoxLayout()
        self.draft_hero_combo = QComboBox()
        self.draft_hero_combo.setMinimumWidth(260)
        draft_controls.addWidget(QLabel("Герой:"))
        draft_controls.addWidget(self.draft_hero_combo, 1)
        add_ally = QPushButton("Добавить в мой пик")
        add_ally.clicked.connect(lambda checked=False: self._add_draft_hero("ally"))
        add_enemy = QPushButton("Добавить во врага")
        add_enemy.clicked.connect(lambda checked=False: self._add_draft_hero("enemy"))
        analyze_btn = QPushButton("Оценить драфт")
        analyze_btn.clicked.connect(self._analyze_draft)
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self._clear_draft)
        draft_controls.addWidget(add_ally)
        draft_controls.addWidget(add_enemy)
        draft_controls.addWidget(analyze_btn)
        draft_controls.addWidget(clear_btn)
        draft_layout.addLayout(draft_controls)

        draft_lists = QHBoxLayout()
        self.ally_draft_list = QListWidget()
        self.enemy_draft_list = QListWidget()
        for label, widget in (("Мой драфт", self.ally_draft_list), ("Вражеский драфт", self.enemy_draft_list)):
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            widget.setMaximumHeight(150)
            box_layout.addWidget(widget)
            draft_lists.addWidget(box)
        self.draft_result_text = QTextEdit()
        self.draft_result_text.setReadOnly(True)
        self.draft_result_text.setMaximumHeight(180)
        self.draft_result_text.setMarkdown("Добавь героев и нажми **Оценить драфт**.")
        draft_lists.addWidget(self.draft_result_text, 2)
        draft_layout.addLayout(draft_lists)
        layout.addWidget(draft_box, 1)
        return self._wrap_scroll_page(page)

    def _build_items_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("Предметы: база, сборки и мини-игра")
        title.setObjectName("SectionTitle")
        top.addWidget(title, 1)
        refresh_btn = QPushButton("Обновить базу и иконки")
        refresh_btn.clicked.connect(self.load_catalog)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        filters = QHBoxLayout()
        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Поиск предмета")
        self.item_search.textChanged.connect(self._fill_catalog_items)
        filters.addWidget(self.item_search, 1)
        self.item_category_filter = QComboBox()
        self.item_category_filter.addItem("Все категории")
        self.item_category_filter.currentIndexChanged.connect(self._fill_catalog_items)
        filters.addWidget(self.item_category_filter)
        layout.addLayout(filters)

        middle = QHBoxLayout()
        self.catalog_items_table = QTableWidget(0, 4)
        self._setup_table(self.catalog_items_table, ["", "Предмет", "Категория", "Лучше на"])
        self.catalog_items_table.setIconSize(QSize(40, 40))
        self.catalog_items_table.verticalHeader().setDefaultSectionSize(50)
        self.catalog_items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.catalog_items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.catalog_items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.catalog_items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.catalog_items_table.itemSelectionChanged.connect(self._show_selected_catalog_item)
        middle.addWidget(self.catalog_items_table, 3)

        detail_box = QGroupBox("Описание и кому подходит")
        detail_layout = QVBoxLayout(detail_box)
        self.item_detail_text = QTextEdit()
        self.item_detail_text.setReadOnly(True)
        self.item_detail_text.setMarkdown("Выбери предмет слева.")
        detail_layout.addWidget(self.item_detail_text)
        middle.addWidget(detail_box, 2)
        layout.addLayout(middle, 2)

        build_box = QGroupBox("Мини-игра: собери предметы на героя")
        build_layout = QVBoxLayout(build_box)
        build_controls = QHBoxLayout()
        self.item_hero_combo = QComboBox()
        self.item_hero_combo.setMinimumWidth(230)
        self.build_item_combo = QComboBox()
        self.build_item_combo.setMinimumWidth(260)
        build_controls.addWidget(QLabel("Герой:"))
        build_controls.addWidget(self.item_hero_combo)
        build_controls.addWidget(QLabel("Предмет:"))
        build_controls.addWidget(self.build_item_combo, 1)
        add_item = QPushButton("Добавить")
        add_item.clicked.connect(self._add_build_item)
        analyze = QPushButton("Оценить билд")
        analyze.clicked.connect(self._analyze_item_build)
        clear = QPushButton("Очистить")
        clear.clicked.connect(self._clear_item_build)
        build_controls.addWidget(add_item)
        build_controls.addWidget(analyze)
        build_controls.addWidget(clear)
        build_layout.addLayout(build_controls)

        build_bottom = QHBoxLayout()
        self.build_items_list = QListWidget()
        self.build_items_list.setMaximumHeight(160)
        build_bottom.addWidget(self.build_items_list, 1)
        self.build_result_text = QTextEdit()
        self.build_result_text.setReadOnly(True)
        self.build_result_text.setMaximumHeight(180)
        self.build_result_text.setMarkdown("Выбери героя, добавь 3-6 предметов и нажми **Оценить билд**.")
        build_bottom.addWidget(self.build_result_text, 2)
        build_layout.addLayout(build_bottom)
        neutral_box = QGroupBox("Нейтральные предметы")
        neutral_layout = QVBoxLayout(neutral_box)
        neutral_hint = QLabel(
            "Нейтральные предметы выделены отдельной категорией. В билде они считаются отдельно: 6 основных слотов + 1 нейтральный слот. "
            "В мини-игре можно добавить нейтралку и увидеть, подходит ли она герою и стадии игры."
        )
        neutral_hint.setObjectName("Muted")
        neutral_hint.setWordWrap(True)
        neutral_layout.addWidget(neutral_hint)
        layout.addWidget(neutral_box)

        layout.addWidget(build_box, 1)
        return self._wrap_scroll_page(page)

    def _build_best_heroes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("Лучшие герои: мета, винрейты и пики")
        title.setObjectName("SectionTitle")
        top.addWidget(title, 1)
        self.hero_meta_status = QLabel("Загружаю OpenDota heroStats…")
        self.hero_meta_status.setObjectName("StatusPill")
        top.addWidget(self.hero_meta_status)
        refresh_btn = QPushButton("Обновить мету")
        refresh_btn.clicked.connect(self.load_hero_meta)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        hint = QLabel(
            "Таблица обновляется через публичные данные OpenDota heroStats. Это не жестко привязано к твоему аккаунту: "
            "если героев/патч меняют, нажми «Обновить мету», и приложение подтянет свежие значения из API."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        filters = QHBoxLayout()
        self.hero_meta_search = QLineEdit()
        self.hero_meta_search.setPlaceholderText("Поиск героя")
        self.hero_meta_search.textChanged.connect(self._fill_hero_meta_table)
        filters.addWidget(self.hero_meta_search, 1)
        self.hero_meta_sort = QComboBox()
        self.hero_meta_sort.addItems(["WR", "Популярность", "Pro WR", "Pro pick"])
        self.hero_meta_sort.currentIndexChanged.connect(self._fill_hero_meta_table)
        filters.addWidget(self.hero_meta_sort)
        layout.addLayout(filters)

        self.hero_meta_table = QTableWidget(0, 8)
        self._setup_table(self.hero_meta_table, ["", "Герой", "Тип", "WR", "Пики", "Pro WR", "Pro pick", "Роли"])
        self.hero_meta_table.setIconSize(QSize(70, 40))
        self.hero_meta_table.verticalHeader().setDefaultSectionSize(48)
        self.hero_meta_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.hero_meta_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        self.hero_meta_table.itemSelectionChanged.connect(self._show_selected_meta_hero)
        layout.addWidget(self.hero_meta_table, 2)

        meta_box = QGroupBox("Разбор выбранного героя")
        meta_layout = QVBoxLayout(meta_box)
        self.hero_meta_detail = QTextEdit()
        self.hero_meta_detail.setReadOnly(True)
        self.hero_meta_detail.setMarkdown("Выбери героя в таблице, чтобы увидеть краткий meta-разбор.")
        meta_layout.addWidget(self.hero_meta_detail)
        layout.addWidget(meta_box, 1)
        return self._wrap_scroll_page(page)

    def _build_match_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("История матчей игрока")
        title.setObjectName("SectionTitle")
        top.addWidget(title, 1)
        self.match_history_status = QLabel("Введи Steam64/account_id и нажми «Обновить историю»")
        self.match_history_status.setObjectName("StatusPill")
        top.addWidget(self.match_history_status)
        refresh_btn = QPushButton("Обновить историю")
        refresh_btn.clicked.connect(self.load_match_history)
        open_btn = QPushButton("Открыть матч")
        open_btn.clicked.connect(self.open_selected_match)
        top.addWidget(refresh_btn)
        top.addWidget(open_btn)
        layout.addLayout(top)

        hint = QLabel(
            "Можно смотреть не только твой аккаунт: вставь Steam64 или account_id любого игрока с публичной историей матчей, "
            "сохрани его как профиль и обнови историю."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.match_history_table = QTableWidget(0, 9)
        self._setup_table(self.match_history_table, ["Match ID", "Дата", "Герой", "Результат", "K/D/A", "Длительность", "GPM/XPM", "LH/DN", "Источник"])
        self.match_history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.match_history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.match_history_table.itemSelectionChanged.connect(self._show_selected_match)
        layout.addWidget(self.match_history_table, 2)

        detail_box = QGroupBox("Детали выбранного матча")
        detail_layout = QVBoxLayout(detail_box)
        self.match_detail_text = QTextEdit()
        self.match_detail_text.setReadOnly(True)
        self.match_detail_text.setMarkdown("Выбери матч в таблице. Детальные поля появляются, если OpenDota успел разобрать match details.")
        detail_layout.addWidget(self.match_detail_text)
        layout.addWidget(detail_box, 1)
        return self._wrap_scroll_page(page)

    def _build_compare_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        self.compare_title = QLabel("Сравнение с ориентиром роли")
        self.compare_title.setObjectName("SectionTitle")
        layout.addWidget(self.compare_title)

        self.compare_table = QTableWidget(0, 6)
        self._setup_table(self.compare_table, ["Метрика", "Игрок", "Ориентир", "Δ", "Статус", "Совет"])
        self.compare_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.compare_table, 1)

        styles_box = QGroupBox("Pro-style совпадения")
        styles_layout = QVBoxLayout(styles_box)
        self.styles_text = QTextEdit()
        self.styles_text.setReadOnly(True)
        styles_layout.addWidget(self.styles_text)
        layout.addWidget(styles_box, 1)
        return self._wrap_scroll_page(page)

    def _build_live_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        self.gsi_status = QLabel("GSI сервер остановлен")
        self.gsi_status.setObjectName("StatusPill")
        top.addWidget(self.gsi_status, 1)

        start_btn = QPushButton("Запустить Live GSI")
        start_btn.clicked.connect(lambda checked=False: self.start_gsi(show_error=True))
        stop_btn = QPushButton("Остановить")
        stop_btn.clicked.connect(self.stop_gsi)
        save_cfg_btn = QPushButton("Сохранить cfg")
        save_cfg_btn.clicked.connect(self.save_gsi_cfg)
        install_cfg_btn = QPushButton("Установить cfg в Dota 2")
        install_cfg_btn.clicked.connect(self.install_gsi_cfg)
        probe_btn = QPushButton("Тест сервера")
        probe_btn.clicked.connect(self.test_gsi_server)
        diag_btn = QPushButton("Диагностика cfg")
        diag_btn.clicked.connect(self.refresh_gsi_diagnostics)
        repair_btn = QPushButton("Починить Live")
        repair_btn.clicked.connect(self.repair_live_setup)
        manual_cfg_btn = QPushButton("Выбрать cfg-папку")
        manual_cfg_btn.clicked.connect(self.install_gsi_cfg_manual)
        top.addWidget(start_btn)
        top.addWidget(stop_btn)
        top.addWidget(save_cfg_btn)
        top.addWidget(install_cfg_btn)
        top.addWidget(probe_btn)
        top.addWidget(diag_btn)
        top.addWidget(repair_btn)
        top.addWidget(manual_cfg_btn)
        layout.addLayout(top)

        info = QLabel(
            "Если после копирования cfg всё ещё «данных нет», нажми «Тест сервера». Если тест прошёл, значит проблема не в приложении, "
            "а в том, что Dota не читает нужный cfg или не была полностью перезапущена. Кнопка «Починить Live» удаляет старые cfg Dota Coach, "
            "ставит свежий файл в найденные папки и запускает сервер. Если Dota стоит в нестандартной папке — нажми «Выбрать cfg-папку»."
        )
        info.setObjectName("Muted")
        info.setWordWrap(True)
        layout.addWidget(info)

        live_grid = QGridLayout()
        live_grid.setSpacing(10)
        for idx, key in enumerate(["hero", "time", "kda", "resources", "farm", "state"]):
            card = StatCard(key.title(), "—")
            self.live_labels[key] = card.value_label
            live_grid.addWidget(card, idx // 3, idx % 3)
        layout.addLayout(live_grid)

        tip_box = QGroupBox("Live-подсказка")
        tip_layout = QVBoxLayout(tip_box)
        self.live_tip = QTextEdit()
        self.live_tip.setReadOnly(True)
        self.live_tip.setMinimumHeight(120)
        self.live_tip.setText("Запусти матч. Если данные не идут — нажми «Тест сервера», потом «Диагностика cfg».")
        tip_layout.addWidget(self.live_tip)
        layout.addWidget(tip_box)

        diag_box = QGroupBox("Диагностика Live")
        diag_layout = QVBoxLayout(diag_box)
        self.live_diag_text = QTextEdit()
        self.live_diag_text.setReadOnly(True)
        self.live_diag_text.setMaximumHeight(150)
        diag_layout.addWidget(self.live_diag_text)
        layout.addWidget(diag_box)

        cfg_box = QGroupBox("Содержимое gamestate_integration_dota_coach.cfg")
        cfg_layout = QVBoxLayout(cfg_box)
        self.cfg_text = QTextEdit()
        self.cfg_text.setReadOnly(True)
        self.cfg_text.setPlainText(make_gsi_config_text())
        self.cfg_text.setMaximumHeight(180)
        cfg_layout.addWidget(self.cfg_text)
        layout.addWidget(cfg_box)
        return self._wrap_scroll_page(page)

    def _build_pro_lab_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("Pro Lab: гайды, паттерны и моменты")
        title.setObjectName("SectionTitle")
        top.addWidget(title, 1)

        refresh_btn = QPushButton("Обновить Pro Lab")
        refresh_btn.clicked.connect(self.refresh_pro_lab)
        map_btn = QPushButton("Обновить карту Dota")
        map_btn.clicked.connect(self.refresh_map_assets)
        my_replay_btn = QPushButton("Скачать мою демку")
        my_replay_btn.clicked.connect(self.download_my_replay)
        pro_replay_btn = QPushButton("Скачать pro демку")
        pro_replay_btn.clicked.connect(self.download_selected_pro_replay)
        folder_btn = QPushButton("Папка replays")
        folder_btn.clicked.connect(self.open_replays_folder)
        top.addWidget(refresh_btn)
        top.addWidget(map_btn)
        top.addWidget(my_replay_btn)
        top.addWidget(pro_replay_btn)
        top.addWidget(folder_btn)
        layout.addLayout(top)

        self.pro_lab_status = QLabel("Pro Lab готовит паттерны. Нажми «Обновить Pro Lab», чтобы подтянуть свежие pro-матчи.")
        self.pro_lab_status.setObjectName("StatusPill")
        layout.addWidget(self.pro_lab_status)

        patterns_box = QGroupBox("Карты и паттерны движения")
        self.patterns_grid = QGridLayout(patterns_box)
        self.patterns_grid.setSpacing(12)
        self._populate_pattern_cards()
        layout.addWidget(patterns_box)

        bottom = QHBoxLayout()
        pro_box = QGroupBox("Свежие pro-моменты OpenDota")
        pro_layout = QVBoxLayout(pro_box)
        self.pro_table = QTableWidget(0, 6)
        self._setup_table(self.pro_table, ["Match", "Лига", "Герой", "Длительность", "Момент", "Урок"])
        self.pro_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.pro_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        pro_layout.addWidget(self.pro_table)
        bottom.addWidget(pro_box, 3)

        compare_box = QGroupBox("Твой момент vs pro момент")
        compare_layout = QVBoxLayout(compare_box)
        self.pro_comparison_text = QTextEdit()
        self.pro_comparison_text.setReadOnly(True)
        self.pro_comparison_text.setText(
            "Здесь будет сравнение твоего последнего матча с pro-матчем: фарм, смерти, tower damage и таймкоды для просмотра replay."
        )
        compare_layout.addWidget(self.pro_comparison_text)
        bottom.addWidget(compare_box, 2)
        layout.addLayout(bottom, 1)
        return self._wrap_scroll_page(page)

    def _populate_pattern_cards(self) -> None:
        grid = getattr(self, "patterns_grid", None)
        if grid is None:
            return
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for idx, pattern in enumerate(static_patterns()):
            grid.addWidget(self._build_pattern_card(pattern), idx, 0)

    def refresh_map_assets(self, checked: bool = False) -> None:
        if self.map_asset_worker and self.map_asset_worker.isRunning():
            return
        self.pro_lab_status.setText("Пробую скачать чистую карту Dota и перерисовать маршруты…")
        self.map_asset_worker = MapAssetWorker(self)
        self.map_asset_worker.done.connect(self.on_map_assets_updated)
        self.map_asset_worker.start()

    def on_map_assets_updated(self, result: dict[str, Any]) -> None:
        self.pro_lab_status.setText(str(result.get("message") or "Карта обновлена"))
        self._populate_pattern_cards()
        if not result.get("ok"):
            QMessageBox.information(
                self,
                "Карта Pro Lab",
                str(result.get("message") or "Не удалось скачать карту. Оставлены встроенные схемы.")
                + "\n\nВстроенная карта теперь тоже сделана как minimap: Radiant/Dire, река, линии, лес, кемпы, вышки и маршруты поверх неё."
            )


    def _build_pattern_card(self, pattern: Any) -> QWidget:
        card = QFrame()
        card.setObjectName("StatCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        image = QLabel()
        image.setMinimumWidth(430)
        pixmap = QPixmap(pattern.image)
        if not pixmap.isNull():
            image.setPixmap(pixmap.scaled(430, 430, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        image.setAlignment(Qt.AlignCenter)
        layout.addWidget(image, 0)

        text_box = QVBoxLayout()
        title = QLabel(pattern.title)
        title.setObjectName("CardValue")
        title.setWordWrap(True)
        text_box.addWidget(title)
        bullets = QLabel("\n".join(f"• {item}" for item in pattern.bullets))
        bullets.setWordWrap(True)
        text_box.addWidget(bullets)
        drill = QLabel(pattern.drill)
        drill.setObjectName("Muted")
        drill.setWordWrap(True)
        text_box.addWidget(drill)
        layout.addLayout(text_box, 1)
        return card

    def _build_learning_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("Pro Lab: гайды и паттерны")
        title.setObjectName("SectionTitle")
        top.addWidget(title, 1)
        self.learning_status = QLabel("Готово к обновлению")
        self.learning_status.setObjectName("StatusPill")
        top.addWidget(self.learning_status)
        refresh_btn = QPushButton("Обновить Pro Lab")
        refresh_btn.clicked.connect(self.refresh_learning_hub)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        hint = QLabel(
            "Здесь будут обучающие паттерны по фарму, vision, позиционке и авто-карточки из твоих матчей и свежих pro-матчей. "
            "Видео из .dem напрямую не вырезается Python-ом: приложение создает match_id/timecode-пары, а mp4-нарезку можно подключить через Dota/OBS/ffmpeg позже."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(330)
        cards_host = QWidget()
        cards_layout = QHBoxLayout(cards_host)
        cards_layout.setContentsMargins(4, 4, 4, 4)
        cards_layout.setSpacing(14)
        for card in GUIDE_CARDS:
            cards_layout.addWidget(self._build_guide_card(card))
        cards_layout.addStretch(1)
        scroll.setWidget(cards_host)
        layout.addWidget(scroll)

        feed_box = QGroupBox("Авто-разбор: твои моменты vs pro")
        feed_layout = QVBoxLayout(feed_box)
        self.learning_text = QTextEdit()
        self.learning_text.setReadOnly(True)
        self.learning_text.setMarkdown(
            "## Нажми «Обновить Pro Lab»\n\n"
            "Приложение загрузит свежие pro-матчи через OpenDota, найдет твои моменты в последних играх "
            "и соберет карточки для сравнения: твой таймкод vs pro-таймкод."
        )
        feed_layout.addWidget(self.learning_text)
        layout.addWidget(feed_box, 1)
        return page

    def _build_guide_card(self, card: dict[str, Any]) -> QWidget:
        frame = QFrame()
        frame.setObjectName("GuideCard")
        frame.setMinimumWidth(330)
        frame.setMaximumWidth(380)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_path = resource_path("ui", "assets", "patterns", str(card.get("image", "")))
        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            image_label.setPixmap(pixmap.scaled(340, 195, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            image_label.setText("Нет изображения")
            image_label.setObjectName("Muted")
        layout.addWidget(image_label)

        title = QLabel(str(card.get("title", "Гайд")))
        title.setObjectName("CardValue")
        title.setWordWrap(True)
        layout.addWidget(title)

        body = QLabel(str(card.get("body", "")))
        body.setObjectName("Muted")
        body.setWordWrap(True)
        layout.addWidget(body)

        checklist = card.get("checklist") or []
        if checklist:
            checks = QLabel("\n".join(f"• {item}" for item in checklist))
            checks.setWordWrap(True)
            layout.addWidget(checks)
        return frame

    def _build_ai_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("ИИ Тренер")
        title.setObjectName("SectionTitle")
        top.addWidget(title, 1)
        analyze_btn = QPushButton("Сделать полный разбор")
        analyze_btn.clicked.connect(self.run_ai_analysis)
        top.addWidget(analyze_btn)
        layout.addLayout(top)

        hint = QLabel(
            "Если Ollama и модель установлены — будет LLM-отчет. Если нет — приложение покажет встроенный тренерский анализ по метрикам."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.ai_text = QTextEdit()
        self.ai_text.setReadOnly(True)
        self.ai_text.setText("Сначала загрузятся данные игрока. Потом нажми «Сделать полный разбор».")
        layout.addWidget(self.ai_text, 1)
        return self._wrap_scroll_page(page)

    def _setup_table(self, table: QTableWidget, headers: list[str]) -> None:
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.viewport().setAutoFillBackground(True)
        palette = table.palette()
        palette.setColor(QPalette.Base, QColor("#0f1724"))
        palette.setColor(QPalette.AlternateBase, QColor("#101927"))
        palette.setColor(QPalette.Text, QColor("#f7fbff"))
        palette.setColor(QPalette.Highlight, QColor("#2d5f9d"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        table.setPalette(palette)

    def _table_item(self, value: Any, row: int) -> QTableWidgetItem:
        item = QTableWidgetItem(str(value))
        fg = QColor("#f7fbff")
        # Keep both colors dark. This removes the bright Windows/Fusion stripes
        # that made white text unreadable on some systems.
        bg = QColor("#0f1724" if row % 2 == 0 else "#132033")
        item.setForeground(QBrush(fg))
        item.setBackground(QBrush(bg))
        item.setData(Qt.ForegroundRole, fg)
        item.setData(Qt.BackgroundRole, bg)
        return item

    def load_catalog(self, checked: bool = False) -> None:
        if self.catalog_worker and self.catalog_worker.isRunning():
            return
        if hasattr(self, "catalog_status"):
            self.catalog_status.setText("Обновляю базу героев/предметов…")
        self.catalog_worker = CatalogWorker(self)
        self.catalog_worker.loaded.connect(self.on_catalog_loaded)
        self.catalog_worker.failed.connect(self.on_catalog_failed)
        self.catalog_worker.start()

    def on_catalog_loaded(self, data: dict[str, Any]) -> None:
        self.hero_catalog = list(data.get("heroes") or [])
        self.item_catalog = list(data.get("items") or [])
        message = data.get("summary") or f"Герои: {len(self.hero_catalog)}, предметы: {len(self.item_catalog)}"
        if hasattr(self, "catalog_status"):
            self.catalog_status.setText(message)
        self._refresh_catalog_combos()
        self._fill_catalog_heroes()
        self._fill_catalog_items()

    def on_catalog_failed(self, message: str) -> None:
        if hasattr(self, "catalog_status"):
            self.catalog_status.setText("Ошибка базы")
        QMessageBox.warning(self, "База героев/предметов", message)

    def _refresh_catalog_combos(self) -> None:
        hero_names = [h.get("name", "") for h in self.hero_catalog if h.get("name")]
        item_names = [i.get("name", "") for i in self.item_catalog if i.get("name")]
        for attr_name in ("draft_hero_combo", "item_hero_combo"):
            combo = getattr(self, attr_name, None)
            if combo is not None:
                current = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(hero_names)
                if current:
                    idx = combo.findText(current)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.blockSignals(False)
        combo = getattr(self, "build_item_combo", None)
        if combo is not None:
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(item_names)
            if current:
                idx = combo.findText(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        cat_combo = getattr(self, "item_category_filter", None)
        if cat_combo is not None:
            current = cat_combo.currentText()
            cats = sorted({i.get("category", "Other") for i in self.item_catalog})
            cat_combo.blockSignals(True)
            cat_combo.clear()
            cat_combo.addItem("Все категории")
            cat_combo.addItems(cats)
            idx = cat_combo.findText(current)
            if idx >= 0:
                cat_combo.setCurrentIndex(idx)
            cat_combo.blockSignals(False)

    def _fill_catalog_heroes(self) -> None:
        table = getattr(self, "catalog_heroes_table", None)
        if table is None:
            return
        text = getattr(self, "hero_search", QLineEdit()).text().strip().lower()
        attr_filter = getattr(self, "hero_attr_filter", QComboBox()).currentText()
        rows: list[dict[str, Any]] = []
        for hero in self.hero_catalog:
            name = hero.get("name", "")
            roles_text = ", ".join(hero.get("roles") or [])
            if text and text not in name.lower() and text not in roles_text.lower():
                continue
            if attr_filter != "Все типы" and hero.get("attr_ru") != attr_filter:
                continue
            rows.append(hero)
        table.setRowCount(len(rows))
        for row, hero in enumerate(rows):
            name = hero.get("name", "—")
            icon_cell = self._table_item("", row)
            icon_cell.setIcon(QIcon(str(hero_icon_path(name))))
            table.setItem(row, 0, icon_cell)
            values = [name, hero.get("attr_ru", "—"), ", ".join(hero.get("roles") or [])]
            for col, value in enumerate(values, start=1):
                table.setItem(row, col, self._table_item(value, row))
        if rows and table.currentRow() < 0:
            table.selectRow(0)
            self._show_selected_catalog_hero()

    def _show_selected_catalog_hero(self) -> None:
        table = getattr(self, "catalog_heroes_table", None)
        text = getattr(self, "hero_detail_text", None)
        if table is None or text is None:
            return
        row = table.currentRow()
        if row < 0 or table.item(row, 1) is None:
            return
        name = table.item(row, 1).text()
        hero = next((h for h in self.hero_catalog if h.get("name") == name), None)
        if hero:
            text.setMarkdown(hero_details_markdown(hero))

    def _fill_catalog_items(self) -> None:
        table = getattr(self, "catalog_items_table", None)
        if table is None:
            return
        text = getattr(self, "item_search", QLineEdit()).text().strip().lower()
        cat_filter = getattr(self, "item_category_filter", QComboBox()).currentText()
        rows: list[dict[str, Any]] = []
        for item in self.item_catalog:
            name = item.get("name", "")
            hay = " ".join([name, item.get("category", ""), item.get("best_for", ""), " ".join(item.get("tags") or [])]).lower()
            if text and text not in hay:
                continue
            if cat_filter != "Все категории" and item.get("category") != cat_filter:
                continue
            rows.append(item)
        table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            name = item.get("name", "—")
            icon_cell = self._table_item("", row)
            icon_cell.setIcon(QIcon(str(item_icon_path(name))))
            table.setItem(row, 0, icon_cell)
            values = [name, item.get("category", "—"), item.get("best_for", "—")]
            for col, value in enumerate(values, start=1):
                table.setItem(row, col, self._table_item(value, row))
        if rows and table.currentRow() < 0:
            table.selectRow(0)
            self._show_selected_catalog_item()

    def _show_selected_catalog_item(self) -> None:
        table = getattr(self, "catalog_items_table", None)
        text = getattr(self, "item_detail_text", None)
        if table is None or text is None:
            return
        row = table.currentRow()
        if row < 0 or table.item(row, 1) is None:
            return
        name = table.item(row, 1).text()
        item = next((i for i in self.item_catalog if i.get("name") == name), None)
        if item:
            text.setMarkdown(item_details_markdown(item))

    def _add_draft_hero(self, side: str) -> None:
        combo = getattr(self, "draft_hero_combo", None)
        if combo is None:
            return
        name = combo.currentText().strip()
        if not name:
            return
        target = self.ally_draft_list if side == "ally" else self.enemy_draft_list
        existing = [target.item(i).text() for i in range(target.count())]
        if name in existing:
            return
        if target.count() >= 5:
            QMessageBox.information(self, "Драфт заполнен", "В драфте максимум 5 героев.")
            return
        item = QListWidgetItem(QIcon(str(hero_icon_path(name))), name)
        target.addItem(item)

    def _draft_names(self, widget: QListWidget) -> list[str]:
        return [widget.item(i).text() for i in range(widget.count())]

    def _clear_draft(self) -> None:
        self.ally_draft_list.clear()
        self.enemy_draft_list.clear()
        self.draft_result_text.setMarkdown("Добавь героев и нажми **Оценить драфт**.")

    def _analyze_draft(self) -> None:
        allies = self._draft_names(self.ally_draft_list)
        enemies = self._draft_names(self.enemy_draft_list)
        self.draft_result_text.setMarkdown(draft_analysis_markdown(allies, enemies, self.hero_catalog))

    def _add_build_item(self) -> None:
        combo = getattr(self, "build_item_combo", None)
        if combo is None:
            return
        name = combo.currentText().strip()
        if not name:
            return
        if self.build_items_list.count() >= 8:
            QMessageBox.information(self, "Слоты", "Для оценки хватит 6 основных предметов и 1-2 ситуационных.")
            return
        self.build_items_list.addItem(QListWidgetItem(QIcon(str(item_icon_path(name))), name))

    def _clear_item_build(self) -> None:
        self.build_items_list.clear()
        self.build_result_text.setMarkdown("Выбери героя, добавь 3-6 предметов и нажми **Оценить билд**.")

    def _analyze_item_build(self) -> None:
        hero_name = self.item_hero_combo.currentText().strip() if hasattr(self, "item_hero_combo") else ""
        item_names = [self.build_items_list.item(i).text() for i in range(self.build_items_list.count())]
        self.build_result_text.setMarkdown(item_build_analysis_markdown(hero_name, item_names, self.hero_catalog, self.item_catalog))

    def load_hero_meta(self, checked: bool = False) -> None:
        if self.hero_meta_worker and self.hero_meta_worker.isRunning():
            return
        if hasattr(self, "hero_meta_status"):
            self.hero_meta_status.setText("Загружаю OpenDota heroStats…")
        self.hero_meta_worker = HeroMetaWorker(self)
        self.hero_meta_worker.loaded.connect(self.on_hero_meta_loaded)
        self.hero_meta_worker.failed.connect(self.on_hero_meta_failed)
        self.hero_meta_worker.start()

    def on_hero_meta_loaded(self, data: dict[str, Any]) -> None:
        self.hero_meta_rows = list(data.get("rows") or [])
        updated = time.strftime("%H:%M", time.localtime(int(data.get("updated_at") or time.time())))
        if hasattr(self, "hero_meta_status"):
            self.hero_meta_status.setText(f"Мета обновлена: {len(self.hero_meta_rows)} героев, {updated}")
        self._fill_hero_meta_table()

    def on_hero_meta_failed(self, message: str) -> None:
        if hasattr(self, "hero_meta_status"):
            self.hero_meta_status.setText("Ошибка меты")
        if hasattr(self, "hero_meta_detail"):
            self.hero_meta_detail.setPlainText(message)

    def _fill_hero_meta_table(self) -> None:
        table = getattr(self, "hero_meta_table", None)
        if table is None:
            return
        query = getattr(self, "hero_meta_search", QLineEdit()).text().strip().lower()
        sort_mode = getattr(self, "hero_meta_sort", QComboBox()).currentText()
        rows = []
        for row in self.hero_meta_rows:
            name = str(row.get("name") or "")
            roles = ", ".join(row.get("roles") or [])
            if query and query not in name.lower() and query not in roles.lower():
                continue
            rows.append(row)
        key_map = {
            "WR": lambda x: (float(x.get("public_wr") or 0), int(x.get("public_picks") or 0)),
            "Популярность": lambda x: (int(x.get("public_picks") or 0), float(x.get("public_wr") or 0)),
            "Pro WR": lambda x: (float(x.get("pro_wr") or 0), int(x.get("pro_pick") or 0)),
            "Pro pick": lambda x: (int(x.get("pro_pick") or 0), float(x.get("pro_wr") or 0)),
        }
        rows.sort(key=key_map.get(sort_mode, key_map["WR"]), reverse=True)
        table.setRowCount(len(rows))
        for row_idx, hero in enumerate(rows):
            name = str(hero.get("name") or "—")
            icon_cell = self._table_item("", row_idx)
            icon_cell.setIcon(QIcon(str(hero_icon_path(name))))
            table.setItem(row_idx, 0, icon_cell)
            values = [
                name,
                hero.get("attr_ru", "—"),
                f"{float(hero.get('public_wr') or 0):.2f}%",
                f"{int(hero.get('public_picks') or 0):,}".replace(",", " "),
                f"{float(hero.get('pro_wr') or 0):.2f}%",
                str(int(hero.get("pro_pick") or 0)),
                ", ".join(hero.get("roles") or []),
            ]
            for col, value in enumerate(values, start=1):
                table.setItem(row_idx, col, self._table_item(value, row_idx))
        if rows and table.currentRow() < 0:
            table.selectRow(0)
            self._show_selected_meta_hero()

    def _show_selected_meta_hero(self) -> None:
        table = getattr(self, "hero_meta_table", None)
        detail = getattr(self, "hero_meta_detail", None)
        if table is None or detail is None:
            return
        row = table.currentRow()
        if row < 0 or table.item(row, 1) is None:
            return
        name = table.item(row, 1).text()
        hero = next((x for x in self.hero_meta_rows if str(x.get("name")) == name), None)
        if not hero:
            return
        public_picks = int(hero.get("public_picks") or 0)
        public_wr = float(hero.get("public_wr") or 0)
        pro_pick = int(hero.get("pro_pick") or 0)
        pro_wr = float(hero.get("pro_wr") or 0)
        verdict = "сильный герой меты" if public_wr >= 52 and public_picks >= 1000 else "ситуативный герой" if public_wr >= 49 else "требует осторожного пика"
        detail.setMarkdown(
            f"## {name}\n\n"
            f"**Тип:** {hero.get('attr_ru', '—')}  \n"
            f"**Публичный WR:** {public_wr:.2f}% на {public_picks:,} пиках  \n".replace(",", " ")
            + f"**Pro WR:** {pro_wr:.2f}% | pro pick: {pro_pick}  \n"
            + f"**Роли:** {', '.join(hero.get('roles') or []) or '—'}  \n"
            + f"**Оценка:** {verdict}.\n\n"
            + "**Как использовать:** не смотри только на винрейт. Сверяй героя с ролью, контрпиками, линией, уроном по зданиям, контролем и тем, закрывает ли он проблему твоего драфта."
        )

    def load_match_history(self, checked: bool = False) -> None:
        steam64 = self.steam_input.text().strip()
        if not steam64:
            if hasattr(self, "match_history_status"):
                self.match_history_status.setText("Введи Steam64/account_id")
            QMessageBox.information(self, "История матчей", "Вставь Steam64 или account_id игрока. Для чужого аккаунта история должна быть публичной.")
            return
        if self.match_history_worker and self.match_history_worker.isRunning():
            return
        if hasattr(self, "match_history_status"):
            self.match_history_status.setText("Загружаю историю OpenDota…")
        self.match_history_worker = MatchHistoryWorker(steam64, self)
        self.match_history_worker.loaded.connect(self.on_match_history_loaded)
        self.match_history_worker.failed.connect(self.on_match_history_failed)
        self.match_history_worker.start()

    def on_match_history_loaded(self, data: dict[str, Any]) -> None:
        self.match_history_rows = list(data.get("rows") or [])
        if hasattr(self, "match_history_status"):
            self.match_history_status.setText(f"История загружена: {len(self.match_history_rows)} матчей")
        self._fill_match_history_table()

    def on_match_history_failed(self, message: str) -> None:
        if hasattr(self, "match_history_status"):
            self.match_history_status.setText("Ошибка истории")
        if hasattr(self, "match_detail_text"):
            self.match_detail_text.setPlainText(message)

    def _fill_match_history_table(self) -> None:
        table = getattr(self, "match_history_table", None)
        if table is None:
            return
        rows = self.match_history_rows
        table.setRowCount(len(rows))
        for row_idx, item in enumerate(rows):
            values = [
                item.get("match_id", "—"),
                item.get("date", "—"),
                item.get("hero", "—"),
                item.get("result", "—"),
                item.get("kda", "—"),
                item.get("duration", "—"),
                item.get("gpm_xpm", "—"),
                item.get("lh_dn", "—"),
                item.get("source", "—"),
            ]
            for col, value in enumerate(values):
                table.setItem(row_idx, col, self._table_item(value, row_idx))
        if rows and table.currentRow() < 0:
            table.selectRow(0)
            self._show_selected_match()

    def _show_selected_match(self) -> None:
        table = getattr(self, "match_history_table", None)
        detail = getattr(self, "match_detail_text", None)
        if table is None or detail is None:
            return
        row = table.currentRow()
        if row < 0 or row >= len(self.match_history_rows):
            return
        item = self.match_history_rows[row]
        raw = item.get("raw") or {}
        detail.setMarkdown(
            f"## Матч {item.get('match_id', '—')}\n\n"
            f"**Дата:** {item.get('date', '—')}  \n"
            f"**Герой:** {item.get('hero', '—')}  \n"
            f"**Результат:** {item.get('result', '—')}  \n"
            f"**K/D/A:** {item.get('kda', '—')}  \n"
            f"**Длительность:** {item.get('duration', '—')}  \n"
            f"**GPM/XPM:** {item.get('gpm_xpm', '—')}  \n"
            f"**LH/DN:** {item.get('lh_dn', '—')}\n\n"
            "**Что смотреть:** первые 10 минут, смерти перед объектами, пропущенные волны, TP без цели, момент первого сильного предмета.\n\n"
            f"**Технические поля:** source={item.get('source', '—')}, hero_id={raw.get('hero_id', '—')}, lane_role={raw.get('lane_role', '—')}"
        )

    def open_selected_match(self) -> None:
        table = getattr(self, "match_history_table", None)
        if table is None or table.currentRow() < 0 or table.item(table.currentRow(), 0) is None:
            QMessageBox.information(self, "Матч", "Выбери матч в истории.")
            return
        match_id = table.item(table.currentRow(), 0).text().strip()
        if match_id and match_id != "—":
            webbrowser.open(f"https://www.opendota.com/matches/{match_id}")

    def load_data(self) -> None:
        steam64 = self.steam_input.text().strip()
        if not steam64:
            self.status_label.setText("Введи Steam64/account_id")
            if hasattr(self, "errors_text"):
                self.errors_text.setText("Чтобы приложение работало у любого игрока, вставь его Steam64 или account_id в верхнее поле и нажми «Обновить». Профиль матчей должен быть публичным.")
            return
        if self.data_worker and self.data_worker.isRunning():
            return
        self.status_label.setText("Загрузка OpenDota…")
        self.errors_text.setText("")
        self.data_worker = DataWorker(steam64, self)
        self.data_worker.loaded.connect(self.on_data_loaded)
        self.data_worker.failed.connect(self.on_data_failed)
        self.data_worker.start()

    def on_data_loaded(self, data: dict[str, Any]) -> None:
        self.data = data
        summary = data["summary"]
        role_info = data["role_info"]
        comparison = data["comparison"]
        styles = data["styles"]
        focus_plan = data["focus_plan"]
        metrics = summary.metrics

        self.status_label.setText("Данные загружены")
        self.cards["role"].set_value(
            f"{role_info['role_ru']}",
            f"Уверенность {role_info['confidence']}%",
        )
        self.cards["winrate"].set_value(
            f"{metrics.get('winrate', 0)}%",
            f"{int(metrics.get('wins', 0))}W / {int(metrics.get('losses', 0))}L, деталей матчей: {summary.detailed_matches}",
        )
        self.cards["kda"].set_value(
            f"{metrics.get('avg_kills', 0)} / {metrics.get('avg_deaths', 0)} / {metrics.get('avg_assists', 0)}",
            f"KDA ratio {metrics.get('avg_kda', 0)}",
        )
        self.cards["economy"].set_value(
            f"{metrics.get('avg_gpm', 0)} / {metrics.get('avg_xpm', 0)}",
            "По детальным матчам, если OpenDota их отдал",
        )
        self.cards["farm"].set_value(
            f"{metrics.get('last_hits_per_min', 0)}",
            f"Средняя длительность {metrics.get('avg_duration_min', 0)} мин",
        )
        self.cards["vision"].set_value(
            f"{metrics.get('wards_per_match', 0)} wards / {metrics.get('camps_stacked_per_match', 0)} stacks",
            "Для саппортов это ключевой блок",
        )

        self._fill_heroes_table(summary.top_heroes)
        self.match_history_rows = match_history_rows(summary)
        self._fill_match_history_table()
        if hasattr(self, "match_history_status"):
            self.match_history_status.setText(f"Последние матчи: {len(self.match_history_rows)}. Для 50 матчей нажми «Обновить историю».")
        self._fill_comparison_table(comparison)
        self._fill_styles(styles, role_info)
        self.focus_text.setMarkdown("\n".join(f"- {item}" for item in focus_plan))
        self.compare_title.setText(f"Сравнение с ориентиром роли: {role_info['role_ru']}")
        self.ai_text.setText("Данные готовы. Нажми «Сделать полный разбор», чтобы получить отчет.")

        if summary.errors:
            self.errors_text.setText("Часть детальных матчей не загрузилась: " + "; ".join(summary.errors[:3]))
        self.update_live_panel()
        self.refresh_pro_lab(silent=True)

    def on_data_failed(self, message: str) -> None:
        self.status_label.setText("Ошибка загрузки")
        self.ai_text.setText(message)
        QMessageBox.warning(self, "Ошибка OpenDota", message)

    def _fill_heroes_table(self, heroes: list[dict[str, Any]]) -> None:
        self.heroes_table.setRowCount(len(heroes))
        for row, hero in enumerate(heroes):
            values = [
                hero.get("name", "—"),
                str(hero.get("games", 0)),
                f"{hero.get('winrate', 0)}%",
                ", ".join(hero.get("roles") or []),
            ]
            for col, value in enumerate(values):
                self.heroes_table.setItem(row, col, self._table_item(value, row))

    def _fill_comparison_table(self, comparison: list[dict[str, Any]]) -> None:
        self.compare_table.setRowCount(len(comparison))
        for row, item in enumerate(comparison):
            values = [
                item["label"],
                str(item["player"]),
                str(item["target"]),
                f"{item['delta']:+}",
                item["status"],
                item["advice"],
            ]
            for col, value in enumerate(values):
                cell = self._table_item(value, row)
                if col == 4:
                    cell.setTextAlignment(Qt.AlignCenter)
                self.compare_table.setItem(row, col, cell)

    def _fill_styles(self, styles: list[dict[str, Any]], role_info: dict[str, Any]) -> None:
        pros = ", ".join(get_pros_for_role(role_info["role"]))
        lines = [
            f"Роль: {role_info.get('role_ru', role_info['role'])}",
            f"Референсы роли: {pros or 'нет данных'}",
            "",
        ]
        for style in styles:
            lines.append(f"• {style['name']} — {style['similarity']}%")
            lines.append(f"  Стиль: {style['style']}")
        self.styles_text.setPlainText("\n".join(lines))

    def refresh_learning_hub(self) -> None:
        if self.learning_worker and self.learning_worker.isRunning():
            return
        role = "Carry"
        if self.data:
            role = self.data["role_info"].get("role", "Carry")
        steam64 = self.steam_input.text().strip() or str(STEAM64)
        self.learning_status.setText("Загрузка OpenDota…")
        self.learning_text.setMarkdown("## Обновляю Pro Lab…\n\nЗагружаю твои последние матчи, свежие pro-матчи и собираю пары таймкодов.")
        self.learning_worker = LearningWorker(steam64, role, self)
        self.learning_worker.loaded.connect(self.on_learning_loaded)
        self.learning_worker.failed.connect(self.on_learning_failed)
        self.learning_worker.start()

    def on_learning_loaded(self, feed: dict[str, Any]) -> None:
        pairs = len(feed.get("pairs") or [])
        pro = len(feed.get("pro_moments") or [])
        user = len(feed.get("user_moments") or [])
        self.learning_status.setText(f"Готово: {pairs} пар, {user} твоих, {pro} pro")
        self.learning_text.setMarkdown(format_learning_feed_markdown(feed))

    def on_learning_failed(self, message: str) -> None:
        self.learning_status.setText("Ошибка Pro Lab")
        self.learning_text.setPlainText(message)

    def run_ai_analysis(self) -> None:
        if not self.data:
            self.ai_text.setText("Данные еще не загружены. Нажми «Обновить» и дождись результата.")
            return
        if self.ai_worker and self.ai_worker.isRunning():
            return
        mode = "Ollama" if ollama_available() else "встроенный анализ"
        self.ai_text.setText(f"Готовлю отчет ({mode})…")
        self.ai_worker = AIWorker(self.data, self)
        self.ai_worker.finished_text.connect(self.ai_text.setMarkdown)
        self.ai_worker.failed.connect(self.ai_text.setPlainText)
        self.ai_worker.start()

    def autostart_gsi(self) -> None:
        self.start_gsi(show_error=False)
        self.refresh_gsi_diagnostics()

    def start_gsi(self, show_error: bool = True) -> None:
        try:
            self.gsi.start()
            self.live_timer.start()
            self.gsi_status.setText(f"GSI слушает {self.gsi.endpoint}")
            self.live_tip.setText("Сервер запущен. Жду JSON snapshot от Dota 2. Для проверки нажми «Тест сервера».")
            self.cfg_text.setPlainText(make_gsi_config_text(endpoint=self.gsi.endpoint, token=GSI_AUTH_TOKEN))
            self.refresh_gsi_diagnostics()
        except OSError as exc:
            message = f"Порт {GSI_PORT} занят или недоступен: {exc}"
            self.gsi_status.setText("GSI не запустился")
            self.live_tip.setText(message)
            if show_error:
                QMessageBox.warning(self, "GSI не запустился", message)

    def stop_gsi(self) -> None:
        self.live_timer.stop()
        self.gsi.stop()
        self.gsi_status.setText("GSI сервер остановлен")
        self.refresh_gsi_diagnostics()

    def repair_live_setup(self) -> None:
        self.start_gsi(show_error=False)
        targets = find_dota_gsi_targets(create=True)
        removed: list[str] = []
        for target in targets:
            folder = target.parent
            if not folder.exists():
                continue
            for old in folder.glob("gamestate_integration_dota_coach*.cfg"):
                try:
                    old.unlink()
                    removed.append(str(old))
                except OSError:
                    pass
        written: list[str] = []
        for target in targets:
            try:
                write_gsi_config(target, endpoint=self.gsi.endpoint, token=GSI_AUTH_TOKEN)
                written.append(str(target))
            except OSError:
                continue
        self.refresh_gsi_diagnostics()
        if written:
            QMessageBox.information(
                self,
                "Live переустановлен",
                "Я запустил сервер, удалил старые cfg Dota Coach и записал новый cfg сюда:\n"
                + "\n".join(written[:8])
                + "\n\nТеперь полностью закрой Dota 2, запусти заново и зайди в лобби/матч."
            )
        else:
            QMessageBox.warning(
                self,
                "Папка Dota не найдена",
                "Автоматически Dota 2 не найдена. Нажми «Выбрать cfg-папку» и укажи папку cfg вручную."
            )

    def install_gsi_cfg_manual(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выбери папку cfg Dota 2",
            str(Path.home()),
        )
        if not folder:
            return
        target_dir = Path(folder)
        target = target_dir / "gamestate_integration_dota_coach.cfg"
        try:
            write_gsi_config(target, endpoint=self.gsi.endpoint, token=GSI_AUTH_TOKEN)
            remember_manual_gsi_dir(target_dir)
            self.cfg_text.setPlainText(target.read_text("utf-8"))
            QMessageBox.information(
                self,
                "CFG установлен вручную",
                f"Файл записан:\n{target}\n\nПроверь, что это именно папка Dota 2 cfg, например:\n"
                "steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\\n\n"
                "После этого полностью перезапусти Dota 2."
            )
        except OSError as exc:
            QMessageBox.warning(self, "Ошибка записи", f"Не удалось записать cfg:\n{exc}")
        self.refresh_gsi_diagnostics()

    def save_gsi_cfg(self) -> None:
        target = writable_config_path("gamestate_integration_dota_coach.cfg")
        write_gsi_config(target, endpoint=self.gsi.endpoint, token=GSI_AUTH_TOKEN)
        self.cfg_text.setPlainText(target.read_text("utf-8"))
        QMessageBox.information(
            self,
            "CFG сохранен",
            f"Файл сохранен:\n{target}\n\n"
            "Если автоматическая установка не сработает, скопируй этот файл прямо в папку Dota 2:\n"
            "steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\",
        )

    def install_gsi_cfg(self) -> None:
        targets = find_dota_gsi_targets(create=True)
        if not targets:
            saved = writable_config_path("gamestate_integration_dota_coach.cfg")
            write_gsi_config(saved, endpoint=self.gsi.endpoint, token=GSI_AUTH_TOKEN)
            self.cfg_text.setPlainText(saved.read_text("utf-8"))
            QMessageBox.warning(
                self,
                "Dota 2 не найдена",
                "Я не нашел папку Dota 2 автоматически.\n\n"
                f"CFG сохранен здесь:\n{saved}\n\n"
                "Скопируй его вручную прямо в:\n"
                "steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\\n\n"
                "Можно дополнительно скопировать и в:\n"
                "steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\gamestate_integration\\",
            )
            self.refresh_gsi_diagnostics()
            return

        written: list[str] = []
        errors: list[str] = []
        for target in targets:
            try:
                write_gsi_config(target, endpoint=self.gsi.endpoint, token=GSI_AUTH_TOKEN)
                written.append(str(target))
            except OSError as exc:
                errors.append(f"{target}: {exc}")

        if written:
            self.cfg_text.setPlainText(Path(written[0]).read_text("utf-8"))
            message = "CFG установлен в несколько безопасных мест:\n" + "\n".join(written[:6])
            if errors:
                message += "\n\nЧасть путей не записалась:\n" + "\n".join(errors[:3])
            message += "\n\nТеперь полностью перезапусти Dota 2."
            QMessageBox.information(self, "CFG установлен", message)
        else:
            QMessageBox.warning(self, "CFG не установлен", "Не удалось записать cfg:\n" + "\n".join(errors[:3]))
        self.refresh_gsi_diagnostics()

    def test_gsi_server(self) -> None:
        if not self.gsi.is_running:
            self.start_gsi(show_error=False)
        ok, message = local_probe(endpoint=self.gsi.endpoint, token=GSI_AUTH_TOKEN)
        self.update_live_panel()
        self.refresh_gsi_diagnostics()
        if ok:
            QMessageBox.information(
                self,
                "Сервер работает",
                message + "\n\nЕсли после этого Dota всё равно не присылает данные, причина почти точно в cfg-пути, параметре запуска или в том, что Dota не была перезапущена.",
            )
        else:
            QMessageBox.warning(self, "Сервер не отвечает", message)

    def refresh_gsi_diagnostics(self) -> None:
        if not hasattr(self, "live_diag_text"):
            return
        diag = self.gsi.diagnostics()
        lines = [
            f"Сервер: {'запущен' if diag['running'] else 'остановлен'}",
            f"Endpoint в cfg: {diag['endpoint']}",
            f"Фактический bind: {diag.get('bound_host') or '—'}:{GSI_PORT}",
            f"Принято POST-запросов: {diag['request_count']}",
            f"Последний путь: {diag['last_path'] or '—'}",
            f"Последняя ошибка: {diag['last_error'] or 'нет'}",
        ]
        if diag["last_seen_seconds"] is None:
            lines.append("Последний snapshot: нет")
        else:
            lines.append(f"Последний snapshot: {int(diag['last_seen_seconds'])} сек. назад")
        lines.append("")
        rows = describe_gsi_installation()
        if not rows:
            lines.append("CFG-пути не найдены автоматически. Нажми «Сохранить cfg» и скопируй файл вручную в game\\dota\\cfg.")
        else:
            lines.append("Найденные cfg-файлы:")
            for row in rows[:8]:
                lines.append(f"• файл: {row['exists']} | папка: {row['folder_exists']} | {row['path']}")
        self.live_diag_text.setPlainText("\n".join(lines))

    def update_live_panel(self) -> None:
        role = "Carry"
        if self.data:
            role = self.data["role_info"].get("role", "Carry")
        coach = LiveCoach(role)
        payload = self.gsi.latest()
        seconds = self.gsi.seconds_since_last_snapshot()
        if seconds is None:
            if self.gsi.is_running:
                self.gsi_status.setText(f"GSI слушает {self.gsi.endpoint}; данных пока нет")
            self.refresh_gsi_diagnostics()
            return

        if seconds > 12:
            self.gsi_status.setText(f"GSI запущен, но данные устарели: {int(seconds)} сек. назад")
        else:
            self.gsi_status.setText(f"Live: последний snapshot {int(seconds)} сек. назад")

        live = coach.summarize(payload)
        self.live_labels["hero"].setText(f"{live['hero']} lvl {live['level']}")
        self.live_labels["time"].setText(f"{live['minute']} мин")
        self.live_labels["kda"].setText(f"{live['kills']} / {live['deaths']} / {live['assists']}")
        self.live_labels["resources"].setText(f"HP {int(live['health_ratio']*100)}% / MP {int(live['mana_ratio']*100)}% / {live['gold']} gold")
        self.live_labels["farm"].setText(f"LH {live['last_hits']} / DN {live['denies']} / GPM {live['gpm']}")
        self.live_labels["state"].setText(str(live.get("game_state", "unknown")))
        self.live_tip.setPlainText(coach.tip(payload))
        self.refresh_gsi_diagnostics()

    def refresh_pro_lab(self, silent: bool = False) -> None:
        if self.pro_lab_worker and self.pro_lab_worker.isRunning():
            return
        steam64 = self.steam_input.text().strip() or str(STEAM64)
        role = "Carry"
        if self.data:
            role = self.data["role_info"].get("role", "Carry")
        self.pro_lab_status.setText("Pro Lab: загружаю свежие pro-матчи и сравнение…")
        self.pro_lab_worker = ProLabWorker(steam64, role, self)
        self.pro_lab_worker.loaded.connect(self.on_pro_lab_loaded)
        self.pro_lab_worker.failed.connect(self.on_pro_lab_failed)
        self.pro_lab_worker.start()

    def on_pro_lab_loaded(self, feed: dict[str, Any]) -> None:
        self.pro_lab_feed = feed
        cards = feed.get("pro_cards") or []
        self.pro_lab_status.setText(f"Pro Lab обновлен: роль {feed.get('role_ru', '—')}, pro-матчей {len(cards)}")
        self.pro_table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            values = [
                card.get("match_id", "—"),
                card.get("league", "—"),
                card.get("hero", "—"),
                card.get("duration", "—"),
                card.get("moment", "—"),
                card.get("lesson", "—"),
            ]
            for col, value in enumerate(values):
                self.pro_table.setItem(row, col, self._table_item(value, row))
        self.pro_comparison_text.setPlainText(feed.get("comparison") or "Нет сравнения.")

    def on_pro_lab_failed(self, message: str) -> None:
        self.pro_lab_status.setText("Pro Lab: ошибка обновления")
        self.pro_comparison_text.setPlainText(message)

    def download_my_replay(self) -> None:
        match_id = str((self.pro_lab_feed or {}).get("user_match_id") or "").strip()
        if not match_id:
            QMessageBox.information(self, "Нет матча", "Сначала нажми «Обновить Pro Lab», чтобы найти твой последний матч.")
            return
        self._start_replay_download(match_id, "my")

    def download_selected_pro_replay(self) -> None:
        match_id = ""
        selected = self.pro_table.selectedItems()
        if selected:
            match_id = self.pro_table.item(selected[0].row(), 0).text()
        if not match_id:
            match_id = str((self.pro_lab_feed or {}).get("pro_match_id") or "").strip()
        if not match_id:
            QMessageBox.information(self, "Нет pro-матча", "Сначала нажми «Обновить Pro Lab» и выбери pro-матч в таблице.")
            return
        self._start_replay_download(match_id, "pro")

    def _start_replay_download(self, match_id: str, label: str) -> None:
        if self.replay_worker and self.replay_worker.isRunning():
            return
        self.pro_lab_status.setText(f"Скачиваю демку {match_id}…")
        self.replay_worker = ReplayDownloadWorker(match_id, label, self)
        self.replay_worker.done.connect(self.on_replay_downloaded)
        self.replay_worker.start()

    def on_replay_downloaded(self, ok: bool, message: str) -> None:
        self.pro_lab_status.setText("Демка скачана" if ok else "Демка не скачалась")
        if ok:
            QMessageBox.information(self, "Replay", message)
        else:
            QMessageBox.warning(self, "Replay", message)

    def open_replays_folder(self) -> None:
        folder = replays_dir()
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            QMessageBox.information(self, "Папка replay", f"Папка replay:\n{folder}\n\nНе удалось открыть автоматически: {exc}")

    def debug_dump_loaded_data(self) -> str:
        if not self.data:
            return "{}"
        summary = self.data["summary"]
        return json.dumps(
            {
                "metrics": summary.metrics,
                "role_info": self.data["role_info"],
                "comparison": self.data["comparison"],
                "pro_lab": self.pro_lab_feed or {},
                "gsi": self.gsi.diagnostics(),
            },
            ensure_ascii=False,
            indent=2,
        )
