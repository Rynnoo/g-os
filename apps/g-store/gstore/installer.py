"""Safe Flatpak command construction and optional synchronous execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import subprocess
from typing import Protocol, Sequence

from .model import AppEntry
from .security import AllowlistError, validate_flatpak_target


class Operation(str, Enum):
    CHECK = "check"
    INSTALL = "install"
    REMOVE = "remove"


class InstallNotAllowed(ValueError):
    """Raised when an entry or operation is outside the fixed install policy."""


@dataclass(frozen=True, slots=True)
class OperationResult:
    operation: Operation
    app_id: str
    commands: tuple[tuple[str, ...], ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def command(self) -> tuple[str, ...]:
        """The final attempted command, retained as a convenience for callers."""

        return self.commands[-1]


class Runner(Protocol):
    def run(self, command: Sequence[str]) -> tuple[int, str, str]: ...


class SubprocessRunner:
    """Run a prebuilt argv without invoking a command shell."""

    def __init__(self, timeout_seconds: float = 900.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, command: Sequence[str]) -> tuple[int, str, str]:
        argv = tuple(command)
        if not argv:
            raise ValueError("command must not be empty")
        try:
            completed = subprocess.run(
                list(argv),
                check=False,
                capture_output=True,
                text=True,
                shell=False,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError:
            return (127, "", f"{argv[0]} was not found")
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return (124, stdout, stderr or "operation timed out")
        return (completed.returncode, completed.stdout, completed.stderr)


class FlatpakInstaller:
    """Build and run only allowlisted system Flatpak operations."""

    # The G-OS image supplies Flatpak here. An absolute path prevents a
    # user-controlled PATH entry from shadowing the trusted executable.
    executable = "/usr/bin/flatpak"

    def __init__(self, runner: Runner | None = None) -> None:
        self.runner = runner or SubprocessRunner()

    def command_for(
        self, operation: Operation | str, app: AppEntry
    ) -> tuple[str, ...]:
        try:
            selected_operation = Operation(operation)
        except ValueError as exc:
            raise InstallNotAllowed(f"unsupported operation: {operation!r}") from exc

        if not app.installable or app.install is None:
            raise InstallNotAllowed(f"{app.name} is not currently installable")

        spec = app.install
        try:
            validate_flatpak_target(app.id, spec.backend, spec.remote, spec.ref)
        except AllowlistError as exc:
            raise InstallNotAllowed(str(exc)) from exc

        if selected_operation is Operation.CHECK:
            return (self.executable, "info", "--system", spec.ref)
        if selected_operation is Operation.INSTALL:
            # --assumeyes answers Flatpak's package questions while still
            # allowing the desktop Polkit agent to authorize a system change.
            return (
                self.executable,
                "install",
                "--system",
                "--assumeyes",
                spec.remote,
                spec.ref,
            )
        if selected_operation is Operation.REMOVE:
            # App data is deliberately retained; removal remains recoverable.
            return (
                self.executable,
                "uninstall",
                "--system",
                "--assumeyes",
                spec.ref,
            )
        raise InstallNotAllowed(f"unsupported operation: {selected_operation!r}")

    def command_plan_for(
        self, operation: Operation | str, app: AppEntry
    ) -> tuple[tuple[str, ...], ...]:
        """Build the complete fixed command plan behind one UI action."""

        try:
            selected_operation = Operation(operation)
        except ValueError as exc:
            raise InstallNotAllowed(f"unsupported operation: {operation!r}") from exc
        return (self.command_for(selected_operation, app),)

    def execute(
        self, operation: Operation | str, app: AppEntry
    ) -> OperationResult:
        try:
            selected_operation = Operation(operation)
        except ValueError as exc:
            raise InstallNotAllowed(f"unsupported operation: {operation!r}") from exc
        commands = self.command_plan_for(selected_operation, app)
        attempted_commands: list[tuple[str, ...]] = []
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        returncode = 0
        for command in commands:
            attempted_commands.append(command)
            returncode, stdout, stderr = self.runner.run(command)
            if stdout:
                stdout_parts.append(stdout)
            if stderr:
                stderr_parts.append(stderr)
            if returncode != 0:
                break
        return OperationResult(
            operation=selected_operation,
            app_id=app.id,
            commands=tuple(attempted_commands),
            returncode=returncode,
            stdout="\n".join(stdout_parts),
            stderr="\n".join(stderr_parts),
        )
