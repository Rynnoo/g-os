from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
GSTORE_ROOT = REPO_ROOT / "apps" / "g-store"
if str(GSTORE_ROOT) not in sys.path:
    sys.path.insert(0, str(GSTORE_ROOT))

from gstore.installer import (  # noqa: E402
    FlatpakInstaller,
    InstallNotAllowed,
    Operation,
    SubprocessRunner,
)
from gstore.model import (  # noqa: E402
    CatalogValidationError,
    load_catalog,
    parse_catalog,
)
from gstore.security import APPROVED_FLATPAK_TARGETS  # noqa: E402


CATALOG_PATH = REPO_ROOT / "catalog" / "apps.json"


def raw_catalog() -> dict[str, object]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


class CatalogTests(unittest.TestCase):
    def test_initial_catalog_contains_all_requested_apps(self) -> None:
        catalog = load_catalog(CATALOG_PATH)
        self.assertEqual(catalog.schema_version, 1)
        self.assertEqual(
            {app.id for app in catalog.apps},
            {
                "obs-studio",
                "chatterino",
                "bottles",
                "google-chrome",
                "livesplit-complete",
                "scu",
                "autosplit64",
                "nsmbw-autosplitter",
                "gcord",
                "retrospy",
                "nintendospy",
            },
        )

    def test_only_fixed_flatpak_targets_are_installable(self) -> None:
        catalog = load_catalog(CATALOG_PATH)
        installable = {app.id: app.install.ref for app in catalog.apps if app.installable}
        self.assertEqual(installable, dict(APPROVED_FLATPAK_TARGETS))
        self.assertTrue(all(not app.installable for app in catalog.apps[3:]))

    def test_search_includes_planned_entries(self) -> None:
        catalog = load_catalog(CATALOG_PATH)
        self.assertEqual([app.id for app in catalog.search("classic timer")], ["livesplit-complete"])
        self.assertIn("retrospy", {app.id for app in catalog.search("controller")})
        self.assertEqual(catalog.search(""), catalog.apps)

    def test_rejects_arbitrary_backend(self) -> None:
        raw = raw_catalog()
        raw["apps"][0]["install"]["backend"] = "command"
        with self.assertRaisesRegex(CatalogValidationError, "backend"):
            parse_catalog(raw)

    def test_rejects_ref_substitution_even_when_ref_is_otherwise_allowed(self) -> None:
        raw = raw_catalog()
        raw["apps"][0]["install"]["ref"] = "com.usebottles.bottles"
        with self.assertRaisesRegex(CatalogValidationError, "approved target"):
            parse_catalog(raw)

    def test_rejects_command_field(self) -> None:
        raw = raw_catalog()
        raw["apps"][0]["install"]["command"] = "touch /tmp/should-not-run"
        with self.assertRaisesRegex(CatalogValidationError, "unknown field"):
            parse_catalog(raw)

    def test_planned_entry_cannot_hide_install_data(self) -> None:
        raw = raw_catalog()
        raw["apps"][3]["install"] = {
            "backend": "flatpak",
            "remote": "flathub",
            "ref": "com.obsproject.Studio",
        }
        with self.assertRaisesRegex(CatalogValidationError, "cannot contain install"):
            parse_catalog(raw)

    def test_rejects_duplicate_ids(self) -> None:
        raw = raw_catalog()
        duplicate = deepcopy(raw["apps"][0])
        raw["apps"].append(duplicate)
        with self.assertRaisesRegex(CatalogValidationError, "duplicate ID"):
            parse_catalog(raw)

    def test_bad_json_has_helpful_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaisesRegex(CatalogValidationError, "not valid JSON"):
                load_catalog(path)


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_catalog(CATALOG_PATH)
        self.installer = FlatpakInstaller()

    def test_builds_fixed_install_and_remove_argv(self) -> None:
        obs = self.catalog.get("obs-studio")
        self.assertEqual(
            self.installer.command_for(Operation.INSTALL, obs),
            (
                "/usr/bin/flatpak",
                "install",
                "--system",
                "--assumeyes",
                "flathub",
                "com.obsproject.Studio",
            ),
        )
        self.assertEqual(
            self.installer.command_for(Operation.REMOVE, obs),
            (
                "/usr/bin/flatpak",
                "uninstall",
                "--system",
                "--assumeyes",
                "com.obsproject.Studio",
            ),
        )

    def test_install_plan_uses_only_fixed_system_flathub_remote(self) -> None:
        obs = self.catalog.get("obs-studio")
        self.assertEqual(
            self.installer.command_plan_for(Operation.INSTALL, obs),
            (
                (
                    "/usr/bin/flatpak",
                    "install",
                    "--system",
                    "--assumeyes",
                    "flathub",
                    "com.obsproject.Studio",
                ),
            ),
        )

    def test_planned_app_never_reaches_runner(self) -> None:
        chrome = self.catalog.get("google-chrome")
        with self.assertRaisesRegex(InstallNotAllowed, "not currently installable"):
            self.installer.command_for(Operation.INSTALL, chrome)

    def test_unknown_operation_is_rejected(self) -> None:
        obs = self.catalog.get("obs-studio")
        with self.assertRaisesRegex(InstallNotAllowed, "unsupported operation"):
            self.installer.command_for("launch-a-shell", obs)

    @patch("gstore.installer.subprocess.run")
    def test_subprocess_runner_explicitly_disables_shell(self, run_mock) -> None:
        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = "ok"
        run_mock.return_value.stderr = ""
        runner = SubprocessRunner(timeout_seconds=5)

        result = runner.run(
            ("/usr/bin/flatpak", "info", "--system", "com.obsproject.Studio")
        )

        self.assertEqual(result, (0, "ok", ""))
        _, kwargs = run_mock.call_args
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(
            run_mock.call_args.args[0],
            ["/usr/bin/flatpak", "info", "--system", "com.obsproject.Studio"],
        )


class CommandLineTests(unittest.TestCase):
    def test_help_does_not_import_optional_pyside(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(GSTORE_ROOT / "main.py"), "--help"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--dry-run", completed.stdout)

    def test_dry_run_prints_plans_without_running_them(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(GSTORE_ROOT / "main.py"),
                "--catalog",
                str(CATALOG_PATH),
                "--dry-run",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "AVAILABLE  obs-studio: /usr/bin/flatpak install --system",
            completed.stdout,
        )
        self.assertNotIn("remote-add", completed.stdout)
        self.assertIn("PLANNED    google-chrome: no command", completed.stdout)


if __name__ == "__main__":
    unittest.main()
