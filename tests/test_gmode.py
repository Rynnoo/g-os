from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "apps" / "g-mode"
PROFILES_DIR = ROOT / "profiles"
sys.path.insert(0, str(APP_DIR))

from gmode.launcher import (  # noqa: E402
    AppSpec,
    AppTarget,
    SessionLauncher,
    probe_target,
)
from gmode.model import GModeProfile, ProfileValidationError, load_profile  # noqa: E402


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = PROFILES_DIR / "nsmbw-starter.json"
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_starter_profile_contains_planned_catalog_ids(self) -> None:
        profile = load_profile(self.path)
        self.assertEqual(profile.profile_id, "nsmbw-starter")
        self.assertEqual(
            profile.app_ids,
            ("obs-studio", "livesplit-complete", "nsmbw-autosplitter", "google-chrome"),
        )
        self.assertEqual(profile.launch_order, profile.app_ids)
        self.assertEqual(profile.obs.scene, "Gameplay")
        self.assertEqual(profile.startup_timeout_seconds, 30)
        self.assertTrue(profile.session.inhibit_sleep)

    def test_layout_limitation_is_explicit(self) -> None:
        profile = load_profile(self.path)
        self.assertEqual(profile.window_layout.application_status, "not_implemented")
        self.assertFalse(profile.window_layout.is_application_implemented)
        self.assertTrue(profile.window_layout.placements)

    def test_duplicate_launch_id_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["launch_order"].append("obs-studio")
        with self.assertRaises(ProfileValidationError) as raised:
            GModeProfile.from_dict(raw)
        self.assertIn("duplicates app ID", str(raised.exception))

    def test_out_of_monitor_rectangle_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["window_layout"]["placements"][0]["x"] = 0.7
        raw["window_layout"]["placements"][0]["width"] = 0.5
        with self.assertRaises(ProfileValidationError) as raised:
            GModeProfile.from_dict(raw)
        self.assertIn("x + width must not exceed 1", str(raised.exception))

    def test_unknown_fields_are_rejected(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["launch_command"] = "dangerous shell text"
        with self.assertRaises(ProfileValidationError) as raised:
            GModeProfile.from_dict(raw)
        self.assertIn("unknown field 'launch_command'", str(raised.exception))

    def test_nonfinite_placement_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["window_layout"]["placements"][0]["x"] = float("nan")
        with self.assertRaises(ProfileValidationError) as raised:
            GModeProfile.from_dict(raw)
        self.assertIn("must be finite", str(raised.exception))

    def test_control_character_in_obs_argv_is_rejected(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["obs"]["scene"] = "Gameplay\x00--unsafe"
        with self.assertRaises(ProfileValidationError) as raised:
            GModeProfile.from_dict(raw)
        self.assertIn("must not contain control characters", str(raised.exception))


class LauncherTests(unittest.TestCase):
    @mock.patch("gmode.launcher.subprocess.run")
    @mock.patch("gmode.launcher.os.access", return_value=True)
    @mock.patch("gmode.launcher.os.path.isfile", return_value=True)
    def test_flatpak_probe_uses_root_protected_system_installation(
        self, _isfile: mock.Mock, _access: mock.Mock, run: mock.Mock
    ) -> None:
        run.return_value = mock.Mock(returncode=0)
        target = AppTarget("flatpak", "com.example.Safe")
        installed, _detail = probe_target(target)
        self.assertTrue(installed)
        argv = run.call_args.args[0]
        self.assertEqual(
            argv, ("/usr/bin/flatpak", "info", "--system", "com.example.Safe")
        )
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(
            target.command(),
            ("/usr/bin/flatpak", "run", "--system", "com.example.Safe"),
        )

    @mock.patch("gmode.launcher.os.access", return_value=True)
    @mock.patch("gmode.launcher.os.path.isfile", return_value=True)
    def test_native_probe_requires_absolute_trusted_path(
        self, _isfile: mock.Mock, _access: mock.Mock
    ) -> None:
        installed, detail = probe_target(AppTarget("native", "mutable-path-tool"))
        self.assertFalse(installed)
        self.assertIn("not an absolute trusted path", detail)

    def test_dry_run_never_spawns_and_adds_obs_selection(self) -> None:
        profile = load_profile(PROFILES_DIR / "nsmbw-starter.json")
        registry = {
            app_id: AppSpec(app_id, app_id, (AppTarget("native", f"safe-{app_id}"),))
            for app_id in profile.app_ids
        }
        popen = mock.Mock(side_effect=AssertionError("dry run spawned a process"))
        launcher = SessionLauncher(
            registry=registry,
            probe=lambda target: (False, f"{target.identifier} absent"),
            popen_factory=popen,
        )
        report = launcher.launch(profile, dry_run=True)
        self.assertEqual([item.app_id for item in report.results], list(profile.launch_order))
        obs = report.results[0]
        self.assertIn("--profile", obs.argv)
        self.assertIn("--collection", obs.argv)
        self.assertIn("--scene", obs.argv)
        popen.assert_not_called()

    def test_actual_launch_uses_argv_and_shell_false(self) -> None:
        profile = load_profile(PROFILES_DIR / "nsmbw-starter.json")
        registry = {
            app_id: AppSpec(app_id, app_id, (AppTarget("native", f"safe-{app_id}"),))
            for app_id in profile.app_ids
        }
        fake_process = mock.Mock(pid=1234)
        popen = mock.Mock(return_value=fake_process)
        launcher = SessionLauncher(
            registry=registry,
            probe=lambda target: (True, "installed"),
            popen_factory=popen,
        )
        report = launcher.launch(profile)
        self.assertEqual(len(report.results), len(profile.launch_order))
        self.assertEqual(popen.call_count, len(profile.launch_order))
        for call in popen.call_args_list:
            argv = call.args[0]
            self.assertIsInstance(argv, tuple)
            self.assertFalse(call.kwargs["shell"])
            self.assertTrue(call.kwargs["start_new_session"])

    def test_actual_launch_skips_unsupported_optional_app(self) -> None:
        raw = json.loads(
            (PROFILES_DIR / "nsmbw-starter.json").read_text(encoding="utf-8")
        )
        raw["apps"].append({"id": "optional-future-tool", "required": False})
        raw["launch_order"].append("optional-future-tool")
        profile = GModeProfile.from_dict(raw)
        registry = {
            app_id: AppSpec(app_id, app_id, (AppTarget("native", f"safe-{app_id}"),))
            for app_id in profile.app_ids
            if app_id != "optional-future-tool"
        }
        popen = mock.Mock(return_value=mock.Mock(pid=1234))
        launcher = SessionLauncher(
            registry=registry,
            probe=lambda target: (True, "installed"),
            popen_factory=popen,
        )

        report = launcher.launch(profile)

        self.assertNotIn("optional-future-tool", [item.app_id for item in report.results])
        self.assertEqual(popen.call_count, len(profile.launch_order) - 1)


class CommandLineTests(unittest.TestCase):
    def test_help_does_not_require_pyside(self) -> None:
        completed = subprocess.run(
            (sys.executable, str(APP_DIR / "main.py"), "--help"),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--dry-run", completed.stdout)

    def test_dry_run_does_not_require_pyside(self) -> None:
        completed = subprocess.run(
            (
                sys.executable,
                str(APP_DIR / "main.py"),
                "--profiles-dir",
                str(PROFILES_DIR),
                "--profile",
                "nsmbw-starter",
                "--dry-run",
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Launch plan (no applications were opened)", completed.stdout)
        self.assertIn("layout application is not implemented", completed.stdout)


if __name__ == "__main__":
    unittest.main()
