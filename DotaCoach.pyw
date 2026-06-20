from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

APP_TITLE = "Dota Coach AI"
WINDOWS_APP_ID = "DotaCoachAI.App"


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except Exception:
        pass


def _runtime_dir() -> Path:
    """Writable folder used for logs and as working directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _import_dir() -> Path:
    """Folder that contains source modules when not frozen."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return Path(__file__).resolve().parent


def _show_startup_error(message: str) -> None:
    """Show a Windows-friendly error when the app is launched without a console."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
    except Exception:
        try:
            print(message, file=sys.stderr)
        except Exception:
            pass


def _write_log(app_dir: Path) -> Path:
    log_path = app_dir / "startup_error.log"
    try:
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        log_path = Path.home() / "DotaCoach_startup_error.log"
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
    return log_path


def main() -> None:
    _set_windows_app_id()
    app_dir = _runtime_dir()
    import_dir = _import_dir()
    os.chdir(app_dir)
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

    try:
        from coach_ui import main as launch_ui

        launch_ui()
    except ModuleNotFoundError as exc:
        log_path = _write_log(app_dir)
        missing = exc.name or "неизвестный модуль"
        _show_startup_error(
            "Dota Coach AI не удалось запустить.\n\n"
            f"Не найден модуль: {missing}\n\n"
            "Скорее всего, зависимости ещё не установлены.\n"
            "Запусти setup_windows.bat один раз, потом попробуй снова.\n\n"
            f"Подробности сохранены здесь:\n{log_path}"
        )
    except Exception:
        log_path = _write_log(app_dir)
        _show_startup_error(
            "Dota Coach AI не удалось запустить.\n\n"
            f"Подробности сохранены здесь:\n{log_path}"
        )


if __name__ == "__main__":
    main()
