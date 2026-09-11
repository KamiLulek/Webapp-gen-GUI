from __future__ import annotations

import argparse
import json

from .backend import WebAppManager


def main() -> int:
    parser = argparse.ArgumentParser(description="KDE/Chromium web app manager")
    parser.add_argument("--list", "-list", action="store_true", help="list configured apps")
    parser.add_argument("--info", "-info", metavar="NAME", help="show app details")
    args = parser.parse_args()
    manager = WebAppManager()
    if args.list:
        for app in manager.list_apps():
            print(app.name)
        return 0
    if args.info:
        app = manager.load_app(args.info)
        print(json.dumps(app.__dict__, ensure_ascii=False, indent=2))
        return 0
    from .gui import run_gui
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
