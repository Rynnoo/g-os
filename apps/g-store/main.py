#!/usr/bin/env python3
"""G Store application entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from gstore.installer import FlatpakInstaller, Operation
from gstore.model import CatalogValidationError, load_catalog


def default_catalog_path() -> Path:
    """Resolve the source-tree catalog, then the installed FHS location."""

    source_tree_path = Path(__file__).resolve().parents[2] / "catalog" / "apps.json"
    if source_tree_path.is_file():
        return source_tree_path
    return Path("/usr/share/g-os/catalog/apps.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="G-OS curated speedrunning app store")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=default_catalog_path(),
        help="catalog JSON path (strict validation and install allowlist still apply)",
    )
    parser.add_argument(
        "--validate-catalog",
        action="store_true",
        help="validate the catalog and exit without importing the GUI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print fixed install plans without importing the GUI or running commands",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
    except CatalogValidationError as exc:
        print(f"G Store catalog error: {exc}", file=sys.stderr)
        return 2

    if args.validate_catalog:
        available = sum(app.installable for app in catalog.apps)
        print(
            f"Catalog OK: {len(catalog.apps)} apps, "
            f"{available} currently installable"
        )
        return 0

    if args.dry_run:
        installer = FlatpakInstaller()
        for app in catalog.apps:
            if app.installable:
                plan = installer.command_plan_for(Operation.INSTALL, app)
                rendered_plan = " then ".join(" ".join(command) for command in plan)
                print(f"AVAILABLE  {app.id}: {rendered_plan}")
            else:
                print(f"{app.status.upper():9}  {app.id}: no command")
        return 0

    try:
        from gstore.gui import run_gui
    except ModuleNotFoundError as exc:
        if exc.name and (exc.name == "PySide6" or exc.name.startswith("PySide6.")):
            print(
                "G Store's graphical interface needs PySide6. "
                "Install the G-OS image package that provides python3-pyside6.",
                file=sys.stderr,
            )
            return 3
        raise
    return run_gui(catalog)


if __name__ == "__main__":
    raise SystemExit(main())
