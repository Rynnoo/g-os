"""Optional PySide6 desktop interface for G Mode."""

from __future__ import annotations

from pathlib import Path
import shlex
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .launcher import LaunchBlockedError, SessionLauncher
from .model import GModeProfile, ProfileRepository


class GModeWindow(QMainWindow):
    def __init__(self, profiles_dir: str | Path):
        super().__init__()
        self.setWindowTitle("G Mode")
        self.resize(920, 580)
        self._launcher = SessionLauncher()
        self._profiles: dict[str, GModeProfile] = {}

        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._profile_changed)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.dry_run = QCheckBox("Dry run (show the launch plan without opening apps)")
        self.dry_run.setChecked(True)
        self.check_button = QPushButton("Check apps")
        self.check_button.clicked.connect(self._check_selected)
        self.launch_button = QPushButton("Start G Mode")
        self.launch_button.clicked.connect(self._launch_selected)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Profiles"))
        left_layout.addWidget(self.profile_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        warning = QLabel(
            "G Mode v0.1 launches apps safely. Saved window placement and session "
            "toggles are not applied yet."
        )
        warning.setWordWrap(True)
        right_layout.addWidget(warning)
        right_layout.addWidget(self.details)
        right_layout.addWidget(self.dry_run)
        buttons = QHBoxLayout()
        buttons.addWidget(self.check_button)
        buttons.addStretch(1)
        buttons.addWidget(self.launch_button)
        right_layout.addLayout(buttons)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self._load_profiles(Path(profiles_dir))

    def _load_profiles(self, directory: Path) -> None:
        scan = ProfileRepository(directory).scan()
        for profile in scan.profiles:
            self._profiles[profile.profile_id] = profile
            item = QListWidgetItem(profile.name)
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            self.profile_list.addItem(item)
        if scan.failures:
            messages = "\n\n".join(
                f"{failure.path.name}: {failure.message}" for failure in scan.failures
            )
            QMessageBox.warning(self, "Some profiles could not be loaded", messages)
        if self.profile_list.count():
            self.profile_list.setCurrentRow(0)
        else:
            self.details.setPlainText(f"No valid profiles found in {directory}")
            self.check_button.setEnabled(False)
            self.launch_button.setEnabled(False)

    def _selected(self) -> GModeProfile | None:
        item = self.profile_list.currentItem()
        if item is None:
            return None
        return self._profiles.get(item.data(Qt.ItemDataRole.UserRole))

    def _profile_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        profile = self._selected()
        if profile is None:
            return
        placements = "\n".join(
            f"  • {item.app_id}: monitor {item.monitor + 1}, "
            f"({item.x:.2f}, {item.y:.2f}) {item.width:.2f}×{item.height:.2f}"
            for item in profile.window_layout.placements
        ) or "  (none)"
        self.details.setPlainText(
            f"{profile.name}\n\n{profile.description}\n\n"
            f"Launch order\n  " + " → ".join(profile.launch_order) + "\n\n"
            f"OBS\n  Profile: {profile.obs.profile}\n"
            f"  Collection: {profile.obs.scene_collection}\n"
            f"  Scene: {profile.obs.scene}\n\n"
            f"Saved layout (application not implemented in v0.1)\n{placements}\n\n"
            f"Startup timeout: {profile.startup_timeout_seconds} seconds"
        )

    def _check_selected(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        statuses = self._launcher.check_requirements(profile)
        lines = []
        for status in statuses:
            marker = "✓" if status.installed else "✗"
            requirement = "required" if status.required else "optional"
            lines.append(f"{marker} {status.name} ({requirement}) — {status.detail}")
        self.details.append("\n\nApp check\n" + "\n".join(lines))

    def _launch_selected(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        try:
            report = self._launcher.launch(profile, dry_run=self.dry_run.isChecked())
        except (LaunchBlockedError, OSError) as error:
            QMessageBox.critical(self, "G Mode could not start", str(error))
            return
        lines = [
            f"{result.app_id}: {shlex.join(result.argv)}"
            + (" [dry run]" if result.dry_run else f" [PID {result.pid}]")
            for result in report.results
        ]
        lines.extend(f"Note: {notice}" for notice in report.notices)
        self.details.append("\n\nLaunch result\n" + "\n".join(lines))


def run_gui(profiles_dir: str | Path) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = GModeWindow(profiles_dir)
    window.show()
    return app.exec()
