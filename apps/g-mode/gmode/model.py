"""Profile data model and strict JSON validation for G Mode.

This module deliberately has no GUI or third-party dependencies.  It can be
used by the image build, command-line checks, and unit tests on Python 3.11+.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_LAYOUT_STATUS = "not_implemented"


class ProfileValidationError(ValueError):
    """Raised when one or more fields in a profile are invalid."""

    def __init__(self, issues: Sequence[str]):
        self.issues = tuple(issues)
        super().__init__("Invalid G Mode profile:\n- " + "\n- ".join(self.issues))


@dataclass(frozen=True, slots=True)
class AppRequirement:
    app_id: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class ObsSettings:
    profile: str
    scene_collection: str
    scene: str


@dataclass(frozen=True, slots=True)
class MonitorPlacement:
    """A rectangle expressed relative to the selected monitor's work area."""

    app_id: str
    monitor: int
    x: float
    y: float
    width: float
    height: float
    state: str = "normal"


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    """Saved layout intent.

    G Mode v0.1 records placements but does not apply them.  Keeping the
    status explicit prevents the UI from implying that window placement has
    already been implemented.
    """

    application_status: str
    placements: tuple[MonitorPlacement, ...]

    @property
    def is_application_implemented(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class SessionToggles:
    do_not_disturb: bool
    inhibit_sleep: bool
    pause_updates: bool
    performance_mode: bool
    close_apps_on_stop: bool


@dataclass(frozen=True, slots=True)
class GModeProfile:
    schema_version: int
    profile_id: str
    name: str
    description: str
    apps: tuple[AppRequirement, ...]
    launch_order: tuple[str, ...]
    obs: ObsSettings
    window_layout: LayoutPlan
    startup_timeout_seconds: int
    session: SessionToggles

    @property
    def app_ids(self) -> tuple[str, ...]:
        return tuple(app.app_id for app in self.apps)

    @property
    def required_app_ids(self) -> tuple[str, ...]:
        return tuple(app.app_id for app in self.apps if app.required)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GModeProfile":
        issues: list[str] = []
        root = _mapping(raw, "$", issues)
        _keys(
            root,
            "$",
            required={
                "schema_version",
                "id",
                "name",
                "apps",
                "launch_order",
                "obs",
                "window_layout",
                "startup_timeout_seconds",
                "session",
            },
            optional={"description"},
            issues=issues,
        )

        schema_version = _integer(root.get("schema_version"), "$.schema_version", issues)
        if schema_version != 1:
            issues.append("$.schema_version must be 1")

        profile_id = _identifier(root.get("id"), "$.id", issues)
        name = _nonempty_string(root.get("name"), "$.name", issues)
        description = _string(root.get("description", ""), "$.description", issues)

        apps_raw = _list(root.get("apps"), "$.apps", issues)
        apps: list[AppRequirement] = []
        seen_apps: set[str] = set()
        for index, value in enumerate(apps_raw):
            path = f"$.apps[{index}]"
            item = _mapping(value, path, issues)
            _keys(item, path, {"id"}, {"required"}, issues)
            app_id = _identifier(item.get("id"), f"{path}.id", issues)
            required = _boolean(item.get("required", True), f"{path}.required", issues)
            if app_id in seen_apps:
                issues.append(f"{path}.id duplicates app ID {app_id!r}")
            seen_apps.add(app_id)
            apps.append(AppRequirement(app_id=app_id, required=required))
        if not apps:
            issues.append("$.apps must contain at least one app")

        order_raw = _list(root.get("launch_order"), "$.launch_order", issues)
        launch_order: list[str] = []
        seen_order: set[str] = set()
        for index, value in enumerate(order_raw):
            app_id = _identifier(value, f"$.launch_order[{index}]", issues)
            if app_id in seen_order:
                issues.append(f"$.launch_order[{index}] duplicates app ID {app_id!r}")
            elif app_id and app_id not in seen_apps:
                issues.append(
                    f"$.launch_order[{index}] references undeclared app ID {app_id!r}"
                )
            seen_order.add(app_id)
            launch_order.append(app_id)
        if not launch_order:
            issues.append("$.launch_order must contain at least one app ID")

        obs_raw = _mapping(root.get("obs"), "$.obs", issues)
        _keys(obs_raw, "$.obs", {"profile", "scene_collection", "scene"}, set(), issues)
        obs = ObsSettings(
            profile=_nonempty_string(obs_raw.get("profile"), "$.obs.profile", issues),
            scene_collection=_nonempty_string(
                obs_raw.get("scene_collection"), "$.obs.scene_collection", issues
            ),
            scene=_nonempty_string(obs_raw.get("scene"), "$.obs.scene", issues),
        )
        if "obs-studio" not in seen_apps:
            issues.append("$.apps must declare 'obs-studio' when OBS settings are present")

        layout_raw = _mapping(root.get("window_layout"), "$.window_layout", issues)
        _keys(
            layout_raw,
            "$.window_layout",
            {"application_status", "placements"},
            set(),
            issues,
        )
        application_status = _string(
            layout_raw.get("application_status"),
            "$.window_layout.application_status",
            issues,
        )
        if application_status != _LAYOUT_STATUS:
            issues.append(
                "$.window_layout.application_status must be 'not_implemented' in G Mode v0.1"
            )
        placements_raw = _list(
            layout_raw.get("placements"), "$.window_layout.placements", issues
        )
        placements: list[MonitorPlacement] = []
        placed_apps: set[str] = set()
        for index, value in enumerate(placements_raw):
            path = f"$.window_layout.placements[{index}]"
            item = _mapping(value, path, issues)
            _keys(
                item,
                path,
                {"app_id", "monitor", "x", "y", "width", "height"},
                {"state"},
                issues,
            )
            app_id = _identifier(item.get("app_id"), f"{path}.app_id", issues)
            monitor = _integer(item.get("monitor"), f"{path}.monitor", issues)
            x = _number(item.get("x"), f"{path}.x", issues)
            y = _number(item.get("y"), f"{path}.y", issues)
            width = _number(item.get("width"), f"{path}.width", issues)
            height = _number(item.get("height"), f"{path}.height", issues)
            state = _string(item.get("state", "normal"), f"{path}.state", issues)
            if app_id not in seen_apps:
                issues.append(f"{path}.app_id references undeclared app ID {app_id!r}")
            if app_id in placed_apps:
                issues.append(f"{path}.app_id has more than one placement")
            placed_apps.add(app_id)
            if monitor < 0:
                issues.append(f"{path}.monitor must be zero or greater")
            if not 0 <= x <= 1:
                issues.append(f"{path}.x must be between 0 and 1")
            if not 0 <= y <= 1:
                issues.append(f"{path}.y must be between 0 and 1")
            if not 0 < width <= 1:
                issues.append(f"{path}.width must be greater than 0 and at most 1")
            if not 0 < height <= 1:
                issues.append(f"{path}.height must be greater than 0 and at most 1")
            if x + width > 1.000001:
                issues.append(f"{path}.x + width must not exceed 1")
            if y + height > 1.000001:
                issues.append(f"{path}.y + height must not exceed 1")
            if state not in {"normal", "maximized", "fullscreen"}:
                issues.append(f"{path}.state must be normal, maximized, or fullscreen")
            placements.append(
                MonitorPlacement(app_id, monitor, x, y, width, height, state)
            )

        timeout = _integer(
            root.get("startup_timeout_seconds"), "$.startup_timeout_seconds", issues
        )
        if not 1 <= timeout <= 300:
            issues.append("$.startup_timeout_seconds must be between 1 and 300")

        session_raw = _mapping(root.get("session"), "$.session", issues)
        toggle_names = {
            "do_not_disturb",
            "inhibit_sleep",
            "pause_updates",
            "performance_mode",
            "close_apps_on_stop",
        }
        _keys(session_raw, "$.session", toggle_names, set(), issues)
        session = SessionToggles(
            do_not_disturb=_boolean(
                session_raw.get("do_not_disturb"), "$.session.do_not_disturb", issues
            ),
            inhibit_sleep=_boolean(
                session_raw.get("inhibit_sleep"), "$.session.inhibit_sleep", issues
            ),
            pause_updates=_boolean(
                session_raw.get("pause_updates"), "$.session.pause_updates", issues
            ),
            performance_mode=_boolean(
                session_raw.get("performance_mode"), "$.session.performance_mode", issues
            ),
            close_apps_on_stop=_boolean(
                session_raw.get("close_apps_on_stop"),
                "$.session.close_apps_on_stop",
                issues,
            ),
        )

        if issues:
            raise ProfileValidationError(issues)
        return cls(
            schema_version=schema_version,
            profile_id=profile_id,
            name=name,
            description=description,
            apps=tuple(apps),
            launch_order=tuple(launch_order),
            obs=obs,
            window_layout=LayoutPlan(application_status, tuple(placements)),
            startup_timeout_seconds=timeout,
            session=session,
        )


@dataclass(frozen=True, slots=True)
class ProfileLoadFailure:
    path: Path
    message: str


@dataclass(frozen=True, slots=True)
class ProfileScan:
    profiles: tuple[GModeProfile, ...]
    failures: tuple[ProfileLoadFailure, ...]


class ProfileRepository:
    """Load all JSON profiles from one directory without hiding bad files."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def scan(self) -> ProfileScan:
        profiles: list[GModeProfile] = []
        failures: list[ProfileLoadFailure] = []
        if not self.directory.is_dir():
            return ProfileScan((), (ProfileLoadFailure(self.directory, "directory not found"),))
        for path in sorted(self.directory.glob("*.json")):
            try:
                profiles.append(load_profile(path))
            except (OSError, json.JSONDecodeError, ProfileValidationError) as error:
                failures.append(ProfileLoadFailure(path, str(error)))
        profiles.sort(key=lambda profile: (profile.name.casefold(), profile.profile_id))
        return ProfileScan(tuple(profiles), tuple(failures))


def load_profile(path: str | Path) -> GModeProfile:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, Mapping):
        raise ProfileValidationError(("$ must be a JSON object",))
    return GModeProfile.from_dict(raw)


def _keys(
    value: Mapping[str, Any],
    path: str,
    required: set[str],
    optional: set[str],
    issues: list[str],
) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - optional)
    for key in missing:
        issues.append(f"{path} is missing required field {key!r}")
    for key in unknown:
        issues.append(f"{path} contains unknown field {key!r}")


def _mapping(value: Any, path: str, issues: list[str]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    issues.append(f"{path} must be an object")
    return {}


def _list(value: Any, path: str, issues: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    issues.append(f"{path} must be an array")
    return []


def _string(value: Any, path: str, issues: list[str]) -> str:
    if isinstance(value, str):
        if _CONTROL_PATTERN.search(value):
            issues.append(f"{path} must not contain control characters")
        return value
    issues.append(f"{path} must be a string")
    return ""


def _nonempty_string(value: Any, path: str, issues: list[str]) -> str:
    result = _string(value, path, issues)
    if isinstance(value, str) and not value.strip():
        issues.append(f"{path} must not be blank")
    return result


def _identifier(value: Any, path: str, issues: list[str]) -> str:
    result = _string(value, path, issues)
    if isinstance(value, str) and not _ID_PATTERN.fullmatch(value):
        issues.append(
            f"{path} must use lowercase letters, digits, dots, underscores, or hyphens"
        )
    return result


def _boolean(value: Any, path: str, issues: list[str]) -> bool:
    if type(value) is bool:
        return value
    issues.append(f"{path} must be true or false")
    return False


def _integer(value: Any, path: str, issues: list[str]) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    issues.append(f"{path} must be an integer")
    return 0


def _number(value: Any, path: str, issues: list[str]) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
        if not math.isfinite(result):
            issues.append(f"{path} must be finite")
            return 0.0
        return result
    issues.append(f"{path} must be a number")
    return 0.0
