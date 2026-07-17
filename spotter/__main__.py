"""Точка входа споттера."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audio.radio import RadioConfig
from .engine import Engine

DEFAULT_CONFIG = {
    "port": 20777,
    "swearing": True,
    "volume": 1.0,
    "memes": True,
    "meme_chance": 0.25,
    "radio": RadioConfig().to_dict(),
}


def base_dir() -> Path:
    """Рядом с exe, а в разработке - корень проекта."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[1]


def save_config(path: Path, cfg: dict) -> None:
    try:
        path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    except OSError:
        pass


def load_config(path: Path) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Конфиг битый ({exc}), беру настройки по умолчанию.")
    else:
        save_config(path, cfg)
    return cfg


class Tee:
    """Пишет и в консоль, и в файл лога.

    В собранном exe stdout может отсутствовать (например, если окно
    скрыто), поэтому на него не рассчитываем и молча переживаем сбой
    записи.
    """

    def __init__(self, stream, log_file) -> None:
        self.stream = stream
        self.log = log_file

    def write(self, text: str) -> int:
        if self.stream is not None:
            try:
                self.stream.write(text)
                self.stream.flush()
            except (OSError, ValueError):
                self.stream = None
        if self.log is not None:
            try:
                self.log.write(text)
                self.log.flush()
            except (OSError, ValueError):
                self.log = None
        return len(text)

    def flush(self) -> None:
        for s in (self.stream, self.log):
            if s is not None:
                try:
                    s.flush()
                except (OSError, ValueError):
                    pass


def main() -> int:
    # Без этого вывод копится в буфере и радио видно рывками.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError, OSError):
        pass

    root = base_dir()
    cfg = load_config(root / "config.json")

    ap = argparse.ArgumentParser(prog="spotter", description="Русский споттер для F1 25")
    ap.add_argument("--port", type=int, default=cfg["port"])
    ap.add_argument("--volume", type=float, default=cfg["volume"])
    ap.add_argument("--no-swear", action="store_true",
                    help="не использовать матерные дубли")
    ap.add_argument("--sounds", type=Path, default=root / "sounds")
    ap.add_argument("--log", type=Path, nargs="?", const=root / "spotter.log",
                    default=None, help="дублировать вывод в файл")
    ap.add_argument("--console", action="store_true",
                    help="без окна, выводить в консоль")
    ap.add_argument("--no-radio", action="store_true",
                    help="выключить эффект рации")
    args = ap.parse_args()

    radio = RadioConfig.from_dict(cfg.get("radio"))
    if args.no_radio:
        radio.enabled = False

    if not args.console:
        from .gui import run_gui
        return run_gui(root, cfg)

    log_file = None
    if args.log:
        try:
            log_file = open(args.log, "w", encoding="utf-8")
            sys.stdout = Tee(sys.stdout, log_file)
        except OSError as exc:
            print(f"Не могу писать лог в {args.log}: {exc}")

    swearing = cfg["swearing"] and not args.no_swear

    print("=" * 58)
    print("  РУССКИЙ СПОТТЕР для F1 25")
    print("=" * 58)

    if not args.sounds.exists():
        print(f"Нет папки со звуками: {args.sounds}")
        print("Запиши фразы через recorder.exe.")
        return 1

    engine = Engine(sounds_dir=args.sounds, port=args.port,
                    swearing=swearing, volume=args.volume, radio=radio)

    have, total = engine.player.available()
    print(f"  Звуки: {args.sounds}")
    print(f"  Записано фраз: {have} из {total}")
    print(f"  Мат: {'включен' if swearing else 'выключен'}")
    print(f"  Рация: {'включена' if radio.enabled else 'выключена'}")
    print(f"  Громкость: {args.volume:.1f}")
    print("=" * 58)
    if have == 0:
        print()
        print("  Ни одной фразы не записано - споттер будет молчать.")
        print("  Запусти recorder.exe и наговори банк.")
        print()
    print()
    print("  В игре: Настройки -> Телеметрия -> UDP Telemetry: ON")
    print(f"          UDP Port: {args.port}, UDP Format: F1 25")
    print()

    try:
        engine.run()
    except KeyboardInterrupt:
        print("\nВыход.")
    finally:
        engine.shutdown()
        if log_file is not None:
            log_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
