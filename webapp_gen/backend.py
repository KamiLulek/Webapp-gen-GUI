from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


APP_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
KNOWN_FLAGS = (
    "--disable-features=Translate,OptimizationGuide",
    "--disable-background-networking",
    "--disable-extensions",
    "--disable-sync",
    "--disable-gpu",
    "--incognito",
    "--start-maximized",
)


def _parse_assignment(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return re.sub(r'\\(["\\$`])', r'\1', raw[1:-1])
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1]
    try:
        values = shlex.split(raw, comments=False, posix=True)
        return " ".join(values)
    except ValueError:
        return raw.strip("\"'")


def _quote_cfg(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace(chr(96), "\\" + chr(96)) + '"'


def _desktop_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", " ").replace("\r", "")


@dataclass(frozen=True)
class Paths:
    home: Path = field(default_factory=Path.home)

    @property
    def wrapper_dir(self) -> Path:
        return self.home / ".local/bin/webapp-list"

    @property
    def desktop_dir(self) -> Path:
        return self.home / ".local/share/applications"

    @property
    def icon_dir(self) -> Path:
        return self.home / ".local/share/icons/webapp-ico"

    @property
    def extensions_dir(self) -> Path:
        return self.home / ".local/share/webapp-extensions"

    @property
    def config_dir(self) -> Path:
        return self.home / ".config/webapp-gen"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.cfg"

    @property
    def apps_config_dir(self) -> Path:
        return self.config_dir / "apps"

    def ensure(self) -> None:
        for path in (
            self.wrapper_dir,
            self.desktop_dir,
            self.icon_dir,
            self.extensions_dir,
            self.apps_config_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    language: str = "pl"
    default_icon_path: str = ""
    chromium_command: str = "chromium"


@dataclass
class WebApp:
    name: str
    url: str = ""
    icon: str = ""
    flags: list[str] = field(default_factory=list)
    custom_flags: str = ""
    extensions: list[str] = field(default_factory=list)


class WebAppManager:
    def __init__(self, paths: Paths | None = None):
        self.paths = paths or Paths()
        self.paths.ensure()

    def load_settings(self) -> Settings:
        default = Settings(default_icon_path=str(self.paths.home / "Obrazy"))
        data = self._read_cfg(self.paths.config_file)
        language = data.get("LANG_CHOICE", default.language)
        if language not in {"pl", "en"}:
            language = "pl"
        return Settings(
            language=language,
            default_icon_path=data.get("DEFAULT_ICON_PATH", default.default_icon_path),
            chromium_command=data.get("CHROMIUM_COMMAND", default.chromium_command),
        )

    def save_settings(self, settings: Settings) -> None:
        self.paths.config_dir.mkdir(parents=True, exist_ok=True)
        body = "\n".join(
            (
                "# webapp-gen config",
                f"LANG_CHOICE={_quote_cfg(settings.language)}",
                f"DEFAULT_ICON_PATH={_quote_cfg(settings.default_icon_path)}",
                f"CHROMIUM_COMMAND={_quote_cfg(settings.chromium_command or 'chromium')}",
                "",
            )
        )
        self.paths.config_file.write_text(body, encoding="utf-8")

    def list_apps(self) -> list[WebApp]:
        apps: list[WebApp] = []
        for cfg in sorted(self.paths.apps_config_dir.glob("*.cfg"), key=lambda p: p.name.lower()):
            try:
                apps.append(self.load_app(cfg.stem))
            except (OSError, ValueError):
                continue
        return sorted(apps, key=lambda app: app.name.casefold())

    def load_app(self, name: str) -> WebApp:
        data = self._read_cfg(self.paths.apps_config_dir / f"{name}.cfg")
        stored_name = data.get("NAME") or data.get("NAZWA") or name
        return WebApp(
            name=stored_name,
            url=data.get("URL", ""),
            icon=data.get("ICON", ""),
            flags=shlex.split(data.get("FLAGS", "")),
            custom_flags=data.get("CUSTOM_FLAGS", ""),
            extensions=[x for x in data.get("EXTENSIONS", "").split(",") if x],
        )

    def available_extensions(self) -> list[str]:
        try:
            return sorted(
                (p.name for p in self.paths.extensions_dir.iterdir() if p.is_dir()),
                key=str.casefold,
            )
        except OSError:
            return []

    def save_app(self, app: WebApp, icon_source: str | None = None) -> WebApp:
        self.validate(app)
        self.paths.ensure()
        cfg_path = self.paths.apps_config_dir / f"{app.name}.cfg"
        icon = app.icon
        if icon_source:
            source = Path(icon_source).expanduser()
            if not source.is_file():
                raise ValueError("Wybrany plik ikony nie istnieje.")
            suffix = source.suffix.lower() or ".png"
            destination = self.paths.icon_dir / f"{app.name}{suffix}"
            shutil.copy2(source, destination)
            icon = str(destination)

        saved = WebApp(
            name=app.name,
            url=app.url.strip(),
            icon=icon,
            flags=list(dict.fromkeys(app.flags)),
            custom_flags=app.custom_flags.strip(),
            extensions=list(dict.fromkeys(app.extensions)),
        )
        cfg = "\n".join(
            (
                f"NAME={_quote_cfg(saved.name)}",
                f"URL={_quote_cfg(saved.url)}",
                f"ICON={_quote_cfg(saved.icon)}",
                f"FLAGS={_quote_cfg(' '.join(saved.flags))}",
                f"CUSTOM_FLAGS={_quote_cfg(saved.custom_flags)}",
                f"EXTENSIONS={_quote_cfg(','.join(saved.extensions))}",
                "",
            )
        )
        cfg_path.write_text(cfg, encoding="utf-8")
        self._write_wrapper(saved)
        self._write_desktop(saved)
        self._refresh_desktop_database()
        return saved

    def remove_app(self, name: str, remove_profile: bool = False) -> None:
        if not APP_NAME_RE.fullmatch(name):
            raise ValueError("Nieprawidłowa nazwa aplikacji.")
        targets = [
            self.paths.wrapper_dir / f"{name}-app",
            self.paths.apps_config_dir / f"{name}.cfg",
            self.paths.desktop_dir / f"{name}.desktop",
        ]
        targets.extend(self.paths.icon_dir.glob(f"{name}.*"))
        for target in targets:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        if remove_profile:
            profile = self.paths.config_dir.parent / f"{name}-app"
            if profile.is_dir():
                shutil.rmtree(profile)
        self._refresh_desktop_database()

    def launch(self, name: str) -> None:
        wrapper = self.paths.wrapper_dir / f"{name}-app"
        if not wrapper.is_file():
            raise FileNotFoundError(f"Brak wrappera: {wrapper}")
        subprocess.Popen(
            [str(wrapper)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def refresh_launchers(self) -> None:
        """Regenerate wrappers and desktop files after a global setting change."""
        for app in self.list_apps():
            self._write_wrapper(app)
            self._write_desktop(app)
        self._refresh_desktop_database()

    @staticmethod
    def validate(app: WebApp) -> None:
        if not APP_NAME_RE.fullmatch(app.name):
            raise ValueError("Nazwa może zawierać tylko litery, cyfry, _ i -.")
        if not app.url.strip():
            raise ValueError("URL nie może być pusty.")
        if "\n" in app.url or "\r" in app.url:
            raise ValueError("URL nie może zawierać nowej linii.")

    @staticmethod
    def _read_cfg(path: Path) -> dict[str, str]:
        if not path.is_file():
            return {}
        result: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                result[key] = _parse_assignment(value)
        return result

    def _write_wrapper(self, app: WebApp) -> None:
        cfg_path = self.paths.apps_config_dir / f"{app.name}.cfg"
        wrapper_path = self.paths.wrapper_dir / f"{app.name}-app"
        chromium = self.load_settings().chromium_command or "chromium"
        body = f'''#!/bin/bash
set -e
source {shlex.quote(str(cfg_path))}
NAME="${{NAME:-$NAZWA}}"
read -r -a _FLAGS <<< "${{FLAGS:-}}"
read -r -a _CUSTOM_FLAGS <<< "${{CUSTOM_FLAGS:-}}"
_EXT_ARGS=()
if [[ -n "${{EXTENSIONS:-}}" ]]; then
    IFS=',' read -ra _EXT_NAMES <<< "$EXTENSIONS"
    _EXT_PATHS=()
    for _e in "${{_EXT_NAMES[@]}}"; do
        [[ -n "$_e" ]] && _EXT_PATHS+=("{self.paths.extensions_dir}/$_e")
    done
    if (( ${{#_EXT_PATHS[@]}} )); then
        _joined=$(IFS=,; echo "${{_EXT_PATHS[*]}}")
        _EXT_ARGS+=("--load-extension=$_joined")
    fi
fi
exec {shlex.quote(chromium)} --class="$NAME" "${{_FLAGS[@]}}" "${{_CUSTOM_FLAGS[@]}}" "${{_EXT_ARGS[@]}}" \\
    --user-data-dir={shlex.quote(str(self.paths.config_dir.parent))}/"${{NAME}}-app" --app="$URL"
'''
        wrapper_path.write_text(body, encoding="utf-8")
        wrapper_path.chmod(0o755)

    def _write_desktop(self, app: WebApp) -> None:
        wrapper = self.paths.wrapper_dir / f"{app.name}-app"
        desktop = self.paths.desktop_dir / f"{app.name}.desktop"
        icon = app.icon or "applications-internet"
        body = "\n".join(
            (
                "[Desktop Entry]",
                "Version=1.0",
                "Type=Application",
                f"Name={_desktop_value(app.name)}",
                f"Comment={_desktop_value(app.name)} webapp",
                f"Exec={_desktop_value(str(wrapper))}",
                f"Icon={_desktop_value(icon)}",
                "Categories=Network;Qt;",
                "Terminal=false",
                "StartupNotify=true",
                f"StartupWMClass={_desktop_value(app.name)}",
                "",
            )
        )
        desktop.write_text(body, encoding="utf-8")
        desktop.chmod(0o755)

    def _refresh_desktop_database(self) -> None:
        command = shutil.which("update-desktop-database")
        if command:
            subprocess.run(
                [command, str(self.paths.desktop_dir)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
