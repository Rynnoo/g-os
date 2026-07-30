"""Safe application resolution, requirement checks, and session launching."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import PurePosixPath
import subprocess
from typing import Callable, Mapping, Sequence

from .model import GModeProfile


@dataclass(frozen=True, slots=True)
class AppTarget:
    """A trusted launch target defined by G-OS, never by a user profile."""

    kind: str
    identifier: str

    def command(self) -> tuple[str, ...]:
        if self.kind == "flatpak":
            # Flatpak otherwise prefers a per-user installation with the same
            # ID. Force the root-protected installation verified by G Mode.
            return ("/usr/bin/flatpak", "run", "--system", self.identifier)
        if self.kind == "native":
            return (self.identifier,)
        raise ValueError(f"Unsupported launch target kind: {self.kind}")


@dataclass(frozen=True, slots=True)
class AppSpec:
    catalog_id: str
    name: str
    targets: tuple[AppTarget, ...]


DEFAULT_APP_REGISTRY: Mapping[str, AppSpec] = {
    "obs-studio": AppSpec(
        "obs-studio",
        "OBS Studio",
        (
            AppTarget("flatpak", "com.obsproject.Studio"),
            AppTarget("native", "/usr/bin/obs"),
        ),
    ),
    "chatterino": AppSpec(
        "chatterino",
        "Chatterino",
        (
            AppTarget("flatpak", "com.chatterino.chatterino"),
            AppTarget("native", "/usr/bin/chatterino"),
        ),
    ),
    "bottles": AppSpec(
        "bottles",
        "Bottles",
        (
            AppTarget("flatpak", "com.usebottles.bottles"),
            AppTarget("native", "/usr/bin/bottles"),
        ),
    ),
    "google-chrome": AppSpec(
        "google-chrome",
        "Google Chrome",
        (
            AppTarget("native", "/usr/bin/google-chrome-stable"),
            AppTarget("native", "/usr/bin/google-chrome"),
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class RequirementStatus:
    app_id: str
    name: str
    required: bool
    installed: bool
    supported: bool
    detail: str
    target: AppTarget | None = None


@dataclass(frozen=True, slots=True)
class PlannedLaunch:
    app_id: str
    name: str
    target: AppTarget
    argv: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LaunchResult:
    app_id: str
    argv: tuple[str, ...]
    dry_run: bool
    pid: int | None


@dataclass(frozen=True, slots=True)
class LaunchReport:
    results: tuple[LaunchResult, ...]
    notices: tuple[str, ...]


class LaunchBlockedError(RuntimeError):
    pass


Probe = Callable[[AppTarget], tuple[bool, str]]
PopenFactory = Callable[..., subprocess.Popen[bytes]]


class SessionLauncher:
    def __init__(
        self,
        registry: Mapping[str, AppSpec] = DEFAULT_APP_REGISTRY,
        probe: Probe | None = None,
        popen_factory: PopenFactory = subprocess.Popen,
    ):
        self.registry = registry
        self._probe = probe or probe_target
        self._popen = popen_factory

    def check_requirements(self, profile: GModeProfile) -> tuple[RequirementStatus, ...]:
        statuses: list[RequirementStatus] = []
        for requirement in profile.apps:
            spec = self.registry.get(requirement.app_id)
            if spec is None:
                statuses.append(
                    RequirementStatus(
                        requirement.app_id,
                        requirement.app_id,
                        requirement.required,
                        False,
                        False,
                        "No safe launcher is registered yet",
                    )
                )
                continue
            failed_details: list[str] = []
            selected: AppTarget | None = None
            for target in spec.targets:
                installed, detail = self._probe(target)
                if installed:
                    selected = target
                    failed_details = [detail]
                    break
                failed_details.append(detail)
            statuses.append(
                RequirementStatus(
                    requirement.app_id,
                    spec.name,
                    requirement.required,
                    selected is not None,
                    True,
                    failed_details[-1] if selected else "; ".join(failed_details),
                    selected,
                )
            )
        return tuple(statuses)

    def plan(
        self,
        profile: GModeProfile,
        statuses: Sequence[RequirementStatus] | None = None,
        *,
        dry_run: bool,
    ) -> tuple[PlannedLaunch, ...]:
        status_by_id = {status.app_id: status for status in (statuses or ())}
        requirement_by_id = {item.app_id: item for item in profile.apps}
        plans: list[PlannedLaunch] = []
        for app_id in profile.launch_order:
            status = status_by_id.get(app_id)
            spec = self.registry.get(app_id)
            if spec is None:
                requirement = requirement_by_id[app_id]
                if dry_run or not requirement.required:
                    continue
                raise LaunchBlockedError(f"{app_id}: no safe launcher is registered")
            if status and status.target:
                target = status.target
            elif dry_run:
                target = spec.targets[0]
            else:
                # A missing optional app is skipped. Required missing apps are
                # rejected before this method is called.
                continue
            argv = list(target.command())
            if app_id == "obs-studio":
                argv.extend(
                    (
                        "--profile",
                        profile.obs.profile,
                        "--collection",
                        profile.obs.scene_collection,
                        "--scene",
                        profile.obs.scene,
                    )
                )
            plans.append(PlannedLaunch(app_id, spec.name, target, tuple(argv)))
        return tuple(plans)

    def launch(self, profile: GModeProfile, *, dry_run: bool = False) -> LaunchReport:
        statuses = self.check_requirements(profile)
        missing = [
            status
            for status in statuses
            if status.required and (not status.supported or not status.installed)
        ]
        if missing and not dry_run:
            details = "; ".join(f"{item.name}: {item.detail}" for item in missing)
            raise LaunchBlockedError(f"Required apps are unavailable: {details}")

        plans = self.plan(profile, statuses, dry_run=dry_run)
        results: list[LaunchResult] = []
        for item in plans:
            if dry_run:
                results.append(LaunchResult(item.app_id, item.argv, True, None))
                continue
            # shell=False is explicit: profile content can never be evaluated
            # by a command shell. argv is sourced from the trusted registry.
            process = self._popen(item.argv, shell=False, start_new_session=True)
            results.append(LaunchResult(item.app_id, item.argv, False, process.pid))

        notices = (
            "Window placements are saved but layout application is not implemented in v0.1.",
            "Session toggles are recorded for the future session controller and are not applied in v0.1.",
            f"Startup timeout is {profile.startup_timeout_seconds} seconds; window readiness waiting is not implemented in v0.1.",
        )
        return LaunchReport(tuple(results), notices)


def probe_target(target: AppTarget) -> tuple[bool, str]:
    """Check a trusted native command or Flatpak ID without launching it."""

    if target.kind == "native":
        # Targets are Linux paths even when validation/tests run on a Windows
        # development host, so use POSIX path semantics deliberately.
        if not PurePosixPath(target.identifier).is_absolute():
            return False, "Native launch target is not an absolute trusted path"
        installed = os.path.isfile(target.identifier) and os.access(target.identifier, os.X_OK)
        return (
            (True, f"Found {target.identifier}")
            if installed
            else (False, f"Executable {target.identifier!r} not found")
        )
    if target.kind == "flatpak":
        flatpak = "/usr/bin/flatpak"
        if not (os.path.isfile(flatpak) and os.access(flatpak, os.X_OK)):
            return False, f"Trusted Flatpak executable {flatpak!r} not found"
        try:
            completed = subprocess.run(
                (flatpak, "info", "--system", target.identifier),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f"Could not query Flatpak: {error}"
        if completed.returncode == 0:
            return True, f"Flatpak {target.identifier} is installed"
        return False, f"Flatpak {target.identifier} is not installed"
    return False, f"Unsupported launch type {target.kind!r}"
