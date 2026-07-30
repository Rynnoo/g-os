"""Optional PySide6 desktop interface for G Store."""

from __future__ import annotations

import sys

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .installer import FlatpakInstaller, InstallNotAllowed, Operation
from .model import AppEntry, Catalog


class AppCard(QFrame):
    """A catalog card with its own asynchronous Flatpak process."""

    operation_finished = Signal(str, bool, str)

    def __init__(self, app_entry: AppEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_entry = app_entry
        self.installer = FlatpakInstaller()
        self._installed = False
        self._operation: Operation | None = None
        self._process = QProcess(self)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)

        self.setObjectName("appCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(7)

        heading_row = QHBoxLayout()
        name_label = QLabel(app_entry.name)
        name_label.setObjectName("appName")
        heading_row.addWidget(name_label)
        heading_row.addStretch(1)
        badge = QLabel("Available" if app_entry.installable else app_entry.status.title())
        badge.setObjectName("availableBadge" if app_entry.installable else "plannedBadge")
        heading_row.addWidget(badge)
        layout.addLayout(heading_row)

        summary = QLabel(app_entry.summary)
        summary.setObjectName("summary")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        description = QLabel(app_entry.description)
        description.setWordWrap(True)
        layout.addWidget(description)

        note = QLabel(app_entry.notes)
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)

        action_row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setObjectName("operationStatus")
        self.status_label.setWordWrap(True)
        action_row.addWidget(self.status_label, 1)
        self.action_button = QPushButton()
        self.action_button.setMinimumWidth(112)
        self.action_button.clicked.connect(self._on_action_clicked)
        action_row.addWidget(self.action_button)
        layout.addLayout(action_row)

        if app_entry.installable:
            self.action_button.setText("Checking…")
            self.action_button.setEnabled(False)
            self._start(Operation.CHECK)
        else:
            label = "Planned" if app_entry.status == "planned" else "Unavailable"
            self.action_button.setText(label)
            self.action_button.setEnabled(False)
            self.status_label.setText("Shown for roadmap visibility")

    def matches(self, query: str) -> bool:
        terms = (term.casefold() for term in query.split() if term)
        return all(term in self.app_entry.searchable_text for term in terms)

    def _on_action_clicked(self) -> None:
        self._start(Operation.REMOVE if self._installed else Operation.INSTALL)

    def _start(self, operation: Operation) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        try:
            command = self.installer.command_for(operation, self.app_entry)
        except InstallNotAllowed as exc:
            self.status_label.setText(str(exc))
            return

        if operation is Operation.INSTALL:
            self.action_button.setText("Installing…")
        elif operation is Operation.REMOVE:
            self.action_button.setText("Removing…")
        else:
            self.action_button.setText("Checking…")
        self.action_button.setEnabled(False)
        self.status_label.setText("")
        self._operation = operation
        self._process.start(command[0], list(command[1:]))

    def _set_ready_button(self) -> None:
        self.action_button.setEnabled(True)
        self.action_button.setText("Remove" if self._installed else "Install")

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            return
        operation = self._operation
        self._operation = None
        self.action_button.setText("Unavailable")
        self.action_button.setEnabled(False)
        message = "Flatpak is not available on this system"
        self.status_label.setText(message)
        if operation is not None:
            self.operation_finished.emit(self.app_entry.id, False, message)

    def _on_process_finished(
        self, exit_code: int, _exit_status: QProcess.ExitStatus
    ) -> None:
        operation = self._operation
        if operation is None:
            return
        self._operation = None
        stderr = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        ).strip()
        ok = exit_code == 0

        if operation is Operation.CHECK:
            self._installed = ok
            self.status_label.setText("Installed" if ok else "Not installed")
        elif ok:
            self._installed = operation is Operation.INSTALL
            self.status_label.setText(
                "Installed successfully" if self._installed else "Removed successfully"
            )
        else:
            verb = "Install" if operation is Operation.INSTALL else "Remove"
            detail = " ".join(stderr.split())[:240] or "Flatpak returned an error"
            self.status_label.setText(f"{verb} failed: {detail}")

        self._set_ready_button()
        self.operation_finished.emit(
            self.app_entry.id, ok, self.status_label.text()
        )


class GStoreWindow(QMainWindow):
    def __init__(self, catalog: Catalog) -> None:
        super().__init__()
        self.catalog = catalog
        self.cards: list[AppCard] = []
        self.setWindowTitle("G Store")
        self.resize(940, 760)

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        title = QLabel("G Store")
        title.setObjectName("title")
        outer.addWidget(title)
        subtitle = QLabel(
            "Speedrunning software, without the command line. "
            "Planned apps stay visible while G-OS finishes testing them."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        available_count = sum(app.installable for app in catalog.apps)
        count_label = QLabel(
            f"{available_count} ready to install  •  "
            f"{len(catalog.apps) - available_count} on the roadmap"
        )
        count_label.setObjectName("countLabel")
        outer.addWidget(count_label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search apps, tools, and categories")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._filter_cards)
        outer.addWidget(self.search_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        list_widget = QWidget()
        self.list_layout = QVBoxLayout(list_widget)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(12)
        for app_entry in catalog.apps:
            card = AppCard(app_entry)
            self.cards.append(card)
            self.list_layout.addWidget(card)
        self.no_results = QLabel("No apps match that search.")
        self.no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results.setObjectName("noResults")
        self.no_results.hide()
        self.list_layout.addWidget(self.no_results)
        self.list_layout.addStretch(1)
        scroll.setWidget(list_widget)
        outer.addWidget(scroll, 1)

        self.setCentralWidget(central)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f5f6f8; color: #20232a; }
            QLabel#title { font-size: 30px; font-weight: 700; color: #2c58c9; }
            QLabel#subtitle { font-size: 15px; color: #555d6d; }
            QLabel#countLabel { color: #6b7280; }
            QLineEdit { background: white; border: 1px solid #ccd1dc;
                        border-radius: 8px; padding: 10px 12px; font-size: 15px; }
            QFrame#appCard { background: white; border: 1px solid #dfe3eb;
                             border-radius: 10px; }
            QLabel#appName { font-size: 18px; font-weight: 700; }
            QLabel#summary { font-weight: 600; color: #394150; }
            QLabel#note { color: #626b7a; }
            QLabel#operationStatus { color: #4e596b; }
            QLabel#availableBadge { background: #dff6e7; color: #176b37;
                                    border-radius: 7px; padding: 4px 8px; }
            QLabel#plannedBadge { background: #eceef3; color: #596173;
                                  border-radius: 7px; padding: 4px 8px; }
            QPushButton { background: #2c58c9; color: white; border: none;
                          border-radius: 7px; padding: 9px 16px; font-weight: 600; }
            QPushButton:hover { background: #2147ae; }
            QPushButton:disabled { background: #d8dce5; color: #747c8a; }
            QLabel#noResults { color: #697181; padding: 30px; }
            """
        )

    def _filter_cards(self, query: str) -> None:
        visible_count = 0
        for card in self.cards:
            visible = card.matches(query)
            card.setVisible(visible)
            visible_count += int(visible)
        self.no_results.setVisible(visible_count == 0)


def run_gui(catalog: Catalog, argv: list[str] | None = None) -> int:
    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(argv if argv is not None else sys.argv)
    application.setApplicationName("G Store")
    application.setOrganizationName("G-OS")
    window = GStoreWindow(catalog)
    window.show()
    return application.exec() if owns_application else 0
