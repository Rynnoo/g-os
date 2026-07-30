from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
G_MODE_ROOT = REPO_ROOT / "apps" / "g-mode"
G_STORE_ROOT = REPO_ROOT / "apps" / "g-store"
PROFILES_DIR = REPO_ROOT / "profiles"
CATALOG_PATH = REPO_ROOT / "catalog" / "apps.json"

for package_root in (G_MODE_ROOT, G_STORE_ROOT):
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

from gmode.launcher import DEFAULT_APP_REGISTRY  # noqa: E402
from gmode.model import ProfileRepository, load_profile  # noqa: E402
from gstore.model import load_catalog  # noqa: E402
from gstore.security import APPROVED_FLATPAK_TARGETS  # noqa: E402


class GStoreGModeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog(CATALOG_PATH)
        cls.catalog_by_id = {app.id: app for app in cls.catalog.apps}

    def test_every_profile_loads_through_g_mode_model(self) -> None:
        scan = ProfileRepository(PROFILES_DIR).scan()

        self.assertTrue(scan.profiles, "expected at least one G Mode profile")
        self.assertEqual(
            scan.failures,
            (),
            "invalid G Mode profiles: "
            + "; ".join(f"{failure.path.name}: {failure.message}" for failure in scan.failures),
        )

    def test_every_profile_app_id_exists_in_g_store_catalog(self) -> None:
        scan = ProfileRepository(PROFILES_DIR).scan()
        self.assertEqual(scan.failures, ())

        missing = {
            (profile.profile_id, app_id)
            for profile in scan.profiles
            for app_id in profile.app_ids
            if app_id not in self.catalog_by_id
        }
        self.assertEqual(missing, set())

    def test_basic_profile_required_apps_are_installable_and_launchable(self) -> None:
        profile = load_profile(PROFILES_DIR / "basic-streaming.json")

        self.assertEqual(profile.name, "Basic Streaming Setup")
        self.assertEqual(
            set(profile.required_app_ids),
            {"obs-studio", "chatterino"},
        )
        self.assertEqual(profile.window_layout.application_status, "not_implemented")

        for app_id in profile.required_app_ids:
            with self.subTest(app_id=app_id):
                self.assertTrue(self.catalog_by_id[app_id].installable)
                self.assertIn(app_id, DEFAULT_APP_REGISTRY)
                self.assertTrue(DEFAULT_APP_REGISTRY[app_id].targets)

    def test_available_flatpak_refs_agree_across_store_and_mode(self) -> None:
        catalog_refs = {
            app.id: app.install.ref
            for app in self.catalog.apps
            if app.installable and app.install is not None
        }
        registry_refs = {
            app_id: target.identifier
            for app_id, spec in DEFAULT_APP_REGISTRY.items()
            for target in spec.targets
            if target.kind == "flatpak" and app_id in APPROVED_FLATPAK_TARGETS
        }

        self.assertEqual(catalog_refs, dict(APPROVED_FLATPAK_TARGETS))
        self.assertEqual(registry_refs, dict(APPROVED_FLATPAK_TARGETS))


if __name__ == "__main__":
    unittest.main()
