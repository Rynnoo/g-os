#!/usr/bin/env python3
"""G Mode v0.1 entrypoint; headless commands do not require PySide6."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import sys

from gmode import ProfileRepository, __version__
from gmode.launcher import SessionLauncher


def default_profiles_dir() -> Path:
    configured = os.environ.get("G_OS_PROFILES_DIR")
    if configured:
        return Path(configured)
    installed = Path("/usr/share/g-os/profiles")
    if installed.is_dir():
        return installed
    return Path(__file__).resolve().parents[2] / "profiles"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="g-mode",
        description="Launch a validated G-OS speedrunning session profile.",
    )
    parser.add_argument("--version", action="version", version=f"G Mode {__version__}")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=default_profiles_dir(),
        help="profile directory (default: %(default)s)",
    )
    parser.add_argument("--profile", help="profile ID for a headless command")
    parser.add_argument(
        "--list",
        action="store_true",
        help="list valid profile IDs without opening the GUI",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check required applications without opening the GUI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the safe launch plan without opening applications",
    )
    return parser


def _choose_profile(scan, profile_id: str | None):
    if profile_id:
        for profile in scan.profiles:
            if profile.profile_id == profile_id:
                return profile
        raise ValueError(f"Profile {profile_id!r} was not found")
    if len(scan.profiles) == 1:
        return scan.profiles[0]
    if not scan.profiles:
        raise ValueError("No valid profiles were found")
    raise ValueError("More than one profile exists; choose one with --profile")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = ProfileRepository(args.profiles_dir)
    scan = repository.scan()
    if scan.failures:
        for failure in scan.failures:
            print(f"Profile error: {failure.path}: {failure.message}", file=sys.stderr)

    if args.list:
        for profile in scan.profiles:
            print(f"{profile.profile_id}\t{profile.name}")
        return 0 if scan.profiles else 1

    if args.check or args.dry_run:
        try:
            profile = _choose_profile(scan, args.profile)
        except ValueError as error:
            print(f"g-mode: {error}", file=sys.stderr)
            return 2
        launcher = SessionLauncher()
        statuses = launcher.check_requirements(profile)
        for status in statuses:
            state = "installed" if status.installed else "missing"
            requirement = "required" if status.required else "optional"
            print(f"[{state}] {status.app_id} ({requirement}): {status.detail}")
        if args.dry_run:
            report = launcher.launch(profile, dry_run=True)
            print("Launch plan (no applications were opened):")
            for result in report.results:
                print(f"  {result.app_id}: {shlex.join(result.argv)}")
            for notice in report.notices:
                print(f"  Note: {notice}")
            return 0
        missing_required = any(status.required and not status.installed for status in statuses)
        return 1 if missing_required else 0

    try:
        from gmode.gui import run_gui
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("PySide6"):
            print(
                "G Mode's graphical interface needs PySide6. "
                "Headless --list, --check, and --dry-run commands are still available.",
                file=sys.stderr,
            )
            return 2
        raise
    return run_gui(args.profiles_dir)


if __name__ == "__main__":
    raise SystemExit(main())
