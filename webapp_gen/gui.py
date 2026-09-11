from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .backend import KNOWN_FLAGS, Settings, WebApp, WebAppManager
from .i18n import translator


FLAG_LABELS = {
    "--disable-features=Translate,OptimizationGuide": "Disable Translate / Optimization Guide",
    "--disable-background-networking": "Disable background networking",
    "--disable-extensions": "Disable extensions",
    "--disable-sync": "Disable sync",
    "--disable-gpu": "Disable GPU",
    "--incognito": "Incognito",
    "--start-maximized": "Start maximized",
}


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.t = translator(settings.language)
        self.setWindowTitle(self.t("settings"))
        form = QFormLayout(self)
        self.language = QLineEdit(settings.language)
        self.language.setPlaceholderText("pl / en")
        self.icon_path = QLineEdit(settings.default_icon_path)
        icon_row = QWidget()
        icon_layout = QHBoxLayout(icon_row)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(self.icon_path)
        browse = QPushButton(self.t("browse"))
        browse.clicked.connect(self.choose_folder)
        icon_layout.addWidget(browse)
        self.chromium = QLineEdit(settings.chromium_command)
        form.addRow(self.t("language"), self.language)
        form.addRow(self.t("icon_path"), icon_row)
        form.addRow(self.t("chromium"), self.chromium)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.t("icon_path"), self.icon_path.text())
        if folder:
            self.icon_path.setText(folder)

    def value(self) -> Settings:
        language = self.language.text().strip().lower()
        if language not in {"pl", "en"}:
            language = "pl"
        return Settings(language, self.icon_path.text().strip(), self.chromium.text().strip() or "chromium")


class MainWindow(QMainWindow):
    def __init__(self, manager: WebAppManager):
        super().__init__()
        self.manager = manager
        self.settings = manager.load_settings()
        self.t = translator(self.settings.language)
        self.current_name: str | None = None
        self.pending_icon: str | None = None
        self.dirty = False
        self.setWindowTitle(f"{self.t('title')} {__version__}")
        self.setMinimumSize(880, 590)
        self.resize(1040, 680)
        self._build_ui()
        self.reload_apps()

    def _build_ui(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        settings_action = QAction(self.t("settings"), self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        heading = QLabel(self.t("installed"))
        heading.setObjectName("sectionTitle")
        left_layout.addWidget(heading)
        self.app_list = QListWidget()
        self.app_list.currentItemChanged.connect(self.select_app)
        left_layout.addWidget(self.app_list, 1)
        new_button = QPushButton(self.t("new"))
        new_button.clicked.connect(self.new_app)
        left_layout.addWidget(new_button)
        splitter.addWidget(left)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        editor = QWidget()
        layout = QVBoxLayout(editor)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.textEdited.connect(self.mark_dirty)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://…")
        self.url.textEdited.connect(self.mark_dirty)
        form.addRow(self.t("name"), self.name)
        form.addRow(self.t("url"), self.url)

        icon_row = QWidget()
        icon_layout = QHBoxLayout(icon_row)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setFrameShape(QFrame.StyledPanel)
        self.icon_path = QLineEdit()
        self.icon_path.setReadOnly(True)
        choose_icon = QPushButton(self.t("choose"))
        choose_icon.clicked.connect(self.choose_icon)
        icon_layout.addWidget(self.icon_preview)
        icon_layout.addWidget(self.icon_path, 1)
        icon_layout.addWidget(choose_icon)
        form.addRow(self.t("icon"), icon_row)
        layout.addLayout(form)

        flags_title = QLabel(self.t("flags"))
        flags_title.setObjectName("sectionTitle")
        layout.addWidget(flags_title)
        self.flag_checks: dict[str, QCheckBox] = {}
        for flag in KNOWN_FLAGS:
            check = QCheckBox(FLAG_LABELS[flag])
            check.stateChanged.connect(self.mark_dirty)
            self.flag_checks[flag] = check
            layout.addWidget(check)

        custom_form = QFormLayout()
        self.custom_flags = QLineEdit()
        self.custom_flags.setPlaceholderText("--some-flag=value")
        self.custom_flags.textEdited.connect(self.mark_dirty)
        custom_form.addRow(self.t("custom"), self.custom_flags)
        layout.addLayout(custom_form)

        ext_title = QLabel(self.t("extensions"))
        ext_title.setObjectName("sectionTitle")
        layout.addWidget(ext_title)
        self.extensions = QListWidget()
        self.extensions.setMaximumHeight(150)
        self.extensions.itemChanged.connect(self.mark_dirty)
        layout.addWidget(self.extensions)
        self.extensions_hint = QLabel()
        self.extensions_hint.setWordWrap(True)
        layout.addWidget(self.extensions_hint)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.save_button = QPushButton(self.t("save"))
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save_app)
        self.remove_button = QPushButton(self.t("remove"))
        self.remove_button.clicked.connect(self.remove_app)
        self.launch_button = QPushButton(self.t("launch"))
        self.launch_button.clicked.connect(self.launch_app)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.launch_button)
        layout.addLayout(buttons)
        scroll.setWidget(editor)
        splitter.addWidget(scroll)
        splitter.setSizes([260, 780])
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(self.t("ready"))

    def reload_apps(self, selected: str | None = None):
        self.app_list.blockSignals(True)
        self.app_list.clear()
        for app in self.manager.list_apps():
            item = QListWidgetItem(app.name)
            item.setData(Qt.UserRole, app.name)
            if app.icon and Path(app.icon).is_file():
                item.setIcon(QIcon(app.icon))
            self.app_list.addItem(item)
        self.app_list.blockSignals(False)
        if selected:
            matches = self.app_list.findItems(selected, Qt.MatchExactly)
            if matches:
                self.app_list.setCurrentItem(matches[0])
                return
        if self.app_list.count():
            self.app_list.setCurrentRow(0)
        else:
            self.new_app()

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        return QMessageBox.question(self, self.t("title"), self.t("unsaved")) == QMessageBox.Yes

    def select_app(self, current, previous):
        if current is None:
            return
        if not self._confirm_discard():
            self.app_list.blockSignals(True)
            self.app_list.setCurrentItem(previous)
            self.app_list.blockSignals(False)
            return
        app = self.manager.load_app(current.data(Qt.UserRole))
        self.populate(app)

    def populate(self, app: WebApp):
        self.current_name = app.name
        self.pending_icon = None
        self.name.setText(app.name)
        self.name.setEnabled(False)
        self.url.setText(app.url)
        self.icon_path.setText(app.icon)
        self._set_icon_preview(app.icon)
        for flag, check in self.flag_checks.items():
            check.setChecked(flag in app.flags)
        unknown = [f for f in app.flags if f not in KNOWN_FLAGS]
        custom = " ".join(unknown + ([app.custom_flags] if app.custom_flags else []))
        self.custom_flags.setText(custom)
        self._load_extensions(set(app.extensions))
        self.remove_button.setEnabled(True)
        self.launch_button.setEnabled(True)
        self.dirty = False

    def new_app(self):
        if not self._confirm_discard():
            return
        self.app_list.clearSelection()
        defaults = [
            "--disable-features=Translate,OptimizationGuide",
            "--disable-background-networking",
        ]
        self.populate(WebApp(name="", flags=defaults))
        self.current_name = None
        self.name.setEnabled(True)
        self.name.setFocus()
        self.remove_button.setEnabled(False)
        self.launch_button.setEnabled(False)
        self.dirty = False

    def _load_extensions(self, selected: set[str]):
        self.extensions.blockSignals(True)
        self.extensions.clear()
        available = self.manager.available_extensions()
        for name in sorted(set(available) | selected, key=str.casefold):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in selected else Qt.Unchecked)
            if name not in available:
                item.setToolTip("Folder missing / Brak folderu")
            self.extensions.addItem(item)
        self.extensions.blockSignals(False)
        self.extensions_hint.setText(
            "" if available else self.t("no_extensions", path=str(self.manager.paths.extensions_dir))
        )

    def selected_extensions(self) -> list[str]:
        return [
            self.extensions.item(i).text()
            for i in range(self.extensions.count())
            if self.extensions.item(i).checkState() == Qt.Checked
        ]

    def choose_icon(self):
        start = self.settings.default_icon_path or str(Path.home())
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.t("select_icon"),
            start,
            "Images (*.png *.svg *.jpg *.jpeg *.webp *.ico);;All files (*)",
        )
        if filename:
            self.pending_icon = filename
            self.icon_path.setText(filename)
            self._set_icon_preview(filename)
            self.mark_dirty()

    def _set_icon_preview(self, path: str):
        pixmap = QPixmap(path) if path and Path(path).is_file() else QPixmap()
        if pixmap.isNull():
            self.icon_preview.setPixmap(QPixmap())
            self.icon_preview.setText("—")
        else:
            self.icon_preview.setText("")
            self.icon_preview.setPixmap(
                pixmap.scaled(QSize(56, 56), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def make_app(self) -> WebApp:
        flags = [flag for flag, check in self.flag_checks.items() if check.isChecked()]
        return WebApp(
            name=self.name.text().strip(),
            url=self.url.text().strip(),
            icon="" if self.pending_icon else self.icon_path.text(),
            flags=flags,
            custom_flags=self.custom_flags.text(),
            extensions=self.selected_extensions(),
        )

    def save_app(self):
        app = self.make_app()
        if self.current_name is None and (self.manager.paths.apps_config_dir / f"{app.name}.cfg").exists():
            QMessageBox.warning(self, self.t("error"), self.t("app_exists"))
            return
        try:
            saved = self.manager.save_app(app, self.pending_icon)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, self.t("error"), str(error))
            return
        was_new = self.current_name is None
        self.current_name = saved.name
        self.pending_icon = None
        self.dirty = False
        self.reload_apps(saved.name)
        self.statusBar().showMessage(self.t("created" if was_new else "saved", name=saved.name), 5000)

    def remove_app(self):
        if not self.current_name:
            return
        answer = QMessageBox.question(
            self,
            self.t("remove"),
            self.t("confirm_remove", name=self.current_name),
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.manager.remove_app(self.current_name)
        except OSError as error:
            QMessageBox.critical(self, self.t("error"), str(error))
            return
        self.current_name = None
        self.dirty = False
        self.reload_apps()

    def launch_app(self):
        if not self.current_name:
            return
        try:
            self.manager.launch(self.current_name)
        except OSError as error:
            QMessageBox.critical(self, self.t("error"), str(error))

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            self.settings = dialog.value()
            self.manager.save_settings(self.settings)
            self.manager.refresh_launchers()
            QMessageBox.information(
                self,
                self.t("settings"),
                "Ustawienia zapisane. Zmiana języka będzie widoczna po ponownym uruchomieniu.\n"
                "Settings saved. Language changes apply after restart.",
            )

    def mark_dirty(self, *_):
        self.dirty = True

    def closeEvent(self, event):
        event.accept() if self._confirm_discard() else event.ignore()


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("webapp-gen")
    app.setOrganizationName("webapp-gen")
    app.setStyleSheet(
        "QLabel#sectionTitle { font-size: 16px; font-weight: 600; margin-top: 6px; }"
        "QPushButton { min-height: 28px; padding: 2px 10px; }"
        "QLineEdit { min-height: 28px; }"
    )
    window = MainWindow(WebAppManager())
    window.show()
    return app.exec()
