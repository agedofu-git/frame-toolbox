# 6つの診断画面と安全な操作を提供するデスクトップUI。
# I/OはバックエンドとWorkerへ委譲し、GUIをブロックしない。
import copy
import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from frame_toolbox.backends.base import StatusBackend
from frame_toolbox.config import AppConfig, ConfigStore, NetworkThresholds
from frame_toolbox.models.status import ActionResult, Snapshot
from frame_toolbox.services.diagnostics_service import DiagnosticReport, DiagnosticsService
from frame_toolbox.ui.presentation import health_label, status_rows
from frame_toolbox.ui.theme import STYLESHEET
from frame_toolbox.ui.widgets.status_panel import StatusPanel
from frame_toolbox.ui.worker import TaskWorker
from frame_toolbox.utils.logging import set_debug_logging

LOG = logging.getLogger("frame_toolbox.ui")


def plain_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class MainWindow(QMainWindow):
    def __init__(self, backend: StatusBackend, config: AppConfig, store: ConfigStore,
                 diagnostics: DiagnosticsService, reports_root: Path, *, mock: bool = False) -> None:
        super().__init__()
        self.backend, self.config, self.store = backend, config, store
        self.diagnostics, self.reports_root = diagnostics, reports_root
        self.snapshot: Snapshot | None = None
        self.worker: TaskWorker | None = None
        self.result_callback: Callable[[object], None] | None = None
        self.close_pending = False
        self.setWindowTitle("Frame Toolbox · v0.1" + (" · Mock Mode" if mock else ""))
        self.resize(1080, 840)
        self.setMinimumSize(760, 560)
        self.setStyleSheet(STYLESHEET)
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(22, 18, 22, 14)
        root.setSpacing(14)
        header = QHBoxLayout()
        title = plain_label("Frame Toolbox")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        mode = plain_label("MOCK · Simulated data" if mock else "USER MODE · Diagnostics")
        mode.setObjectName("mode")
        header.addWidget(mode)
        root.addLayout(header)
        subtitle = plain_label("System status, network checks and diagnostics for SteamOS")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs, 1)
        self.panels: dict[str, StatusPanel] = {}
        self.overview_panels: dict[str, StatusPanel] = {}
        overview, layout = self._page("Overview")
        self.overview_status = plain_label("UNKNOWN · Waiting for first refresh")
        layout.addWidget(self.overview_status)
        grid = QGridLayout()
        for i, section in enumerate(("System", "Network", "VR", "Audio")):
            panel = StatusPanel(section)
            self.overview_panels[section] = panel
            grid.addWidget(panel, i // 2, i % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.warnings = plain_label("Warnings: waiting for data")
        layout.addWidget(self.warnings)
        layout.addStretch()
        for name in ("Network", "VR", "Audio"):
            _, page_layout = self._page(name)
            panel = StatusPanel(name)
            self.panels[name] = panel
            page_layout.addWidget(panel)
            if name == "VR":
                plan = backend.restart_backend.plan()
                page_layout.addWidget(plain_label("Restart SteamVR: " + (plan.description if plan.available else plan.reason)))
            if name == "Audio":
                page_layout.addWidget(plain_label("Mic volume is configured gain. v0.1 never records the microphone or changes audio settings."))
            page_layout.addStretch()
        self._build_diagnostics()
        self._build_settings()
        actions = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.restart_button = QPushButton("Restart SteamVR")
        self.collect_button = QPushButton("Collect Diagnostics")
        self.refresh_button.clicked.connect(self.refresh)
        self.restart_button.clicked.connect(self.restart)
        self.collect_button.clicked.connect(self.collect_diagnostics)
        for button in (self.refresh_button, self.restart_button, self.collect_button):
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)
        self.setCentralWidget(container)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._configure_timer()
        self._enable_actions()
        self.statusBar().showMessage(store.last_error or "Ready")
        QTimer.singleShot(0, self.refresh)

    def _page(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, title)
        return page, layout

    def _build_diagnostics(self) -> None:
        _, layout = self._page("Diagnostics")
        layout.addWidget(plain_label(
            "Reports contain IP addresses, SSID, hostname, process IDs and audio device names. "
            "Review the files before sharing. No home directory scan or microphone capture is performed."
        ))
        self.report_path = QLineEdit(str(self.reports_root))
        self.report_path.setReadOnly(True)
        path_row = QHBoxLayout()
        path_row.addWidget(self.report_path, 1)
        self.choose_report_button = QPushButton("Choose folder…")
        self.choose_report_button.clicked.connect(self.choose_report_directory)
        path_row.addWidget(self.choose_report_button)
        layout.addLayout(path_row)
        self.include_journal = QCheckBox("Include related user journal (current boot, up to 200 lines)")
        layout.addWidget(self.include_journal)
        layout.addWidget(plain_label("Journal collection is optional. Common secret patterns are redacted, but arbitrary log contents cannot be guaranteed safe for sharing."))
        self.report_result = QPlainTextEdit("Use Collect Diagnostics to refresh status and generate a ZIP.\n\nFiles: system.txt, network.txt, processes.txt, audio.txt, toolbox.log, summary.json")
        self.report_result.setReadOnly(True)
        layout.addWidget(self.report_result, 1)

    def _build_settings(self) -> None:
        _, layout = self._page("Settings")
        form = QFormLayout()
        self.pc_ip = QLineEdit(self.config.pc_ip)
        self.pc_ip.setPlaceholderText("192.168.1.20 or IPv6 · empty disables PC ping")
        self.interval = QSpinBox()
        self.interval.setRange(0, 3600)
        self.interval.setSpecialValueText("Off")
        self.interval.setSuffix(" seconds")
        self.interval.setValue(self.config.auto_refresh_seconds)
        self.debug = QCheckBox("Enable debug logging")
        self.debug.setChecked(self.config.debug_logging)
        self.process_names = QLineEdit(", ".join(self.config.vr_process_names))
        self.signal_threshold = QDoubleSpinBox()
        self.signal_threshold.setRange(-120, -10)
        self.signal_threshold.setSuffix(" dBm")
        self.signal_threshold.setValue(self.config.thresholds.weak_signal_dbm)
        self.percent_threshold = QSpinBox()
        self.percent_threshold.setRange(0, 100)
        self.percent_threshold.setSuffix("%")
        self.percent_threshold.setValue(self.config.thresholds.weak_signal_percent)
        self.bitrate_threshold = QDoubleSpinBox()
        self.bitrate_threshold.setRange(0.1, 100000)
        self.bitrate_threshold.setSuffix(" Mbps")
        self.bitrate_threshold.setValue(self.config.thresholds.low_bitrate_mbps)
        for name, widget in [
            ("PC IP address", self.pc_ip), ("Auto refresh (0 or 5–3600)", self.interval),
            ("Logging", self.debug), ("VR process names", self.process_names),
            ("Weak signal", self.signal_threshold), ("Weak NM signal", self.percent_threshold),
            ("Low TX bitrate", self.bitrate_threshold),
        ]:
            form.addRow(name, widget)
        layout.addLayout(form)
        layout.addWidget(plain_label("Thresholds are generic heuristics, not validated Steam Frame requirements. Settings affect this application only."))
        layout.addWidget(plain_label(f"Config: {self.store.path}"))
        self.save_button = QPushButton("Save settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)
        self.settings_status = plain_label(self.store.last_error or "Settings are stored in your user directory.")
        layout.addWidget(self.settings_status)
        layout.addStretch()

    @Slot()
    def choose_report_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Diagnostics output folder", str(self.reports_root))
        if selected:
            self.reports_root = Path(selected)
            self.report_path.setText(selected)

    @Slot()
    def save_settings(self) -> None:
        config = AppConfig(
            self.pc_ip.text(), self.interval.value(), self.debug.isChecked(),
            [name.strip() for name in self.process_names.text().split(",")],
            NetworkThresholds(self.signal_threshold.value(), self.percent_threshold.value(),
                              self.bitrate_threshold.value()),
        )
        try:
            self.store.save(config)
        except (ValueError, OSError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Cannot save settings. Check directory permissions."
            self.settings_status.setText(message)
            QMessageBox.warning(self, "Settings not saved", message)
            return
        self.config = config
        self.pc_ip.setText(config.pc_ip)
        set_debug_logging(config.debug_logging)
        self._configure_timer()
        self.settings_status.setText("Settings saved. Refreshing with the new settings…")
        LOG.info("Settings saved")
        self.refresh()

    def _configure_timer(self) -> None:
        self.timer.stop()
        if self.config.auto_refresh_seconds:
            self.timer.start(self.config.auto_refresh_seconds * 1000)

    def _enable_actions(self) -> None:
        idle = self.worker is None
        self.refresh_button.setEnabled(idle)
        self.collect_button.setEnabled(idle)
        plan = self.backend.restart_backend.plan()
        self.restart_button.setEnabled(idle and plan.available)
        self.restart_button.setToolTip(plan.description if plan.available else plan.reason)
        self.save_button.setEnabled(idle)
        self.choose_report_button.setEnabled(idle)
        self.include_journal.setEnabled(idle)

    def _run_task(self, label: str, operation: Callable[[], object], callback: Callable[[object], None]) -> None:
        if self.worker is not None or self.close_pending:
            return
        self.worker = TaskWorker(operation, self)
        self.result_callback = callback
        self.worker.succeeded.connect(self._on_result)
        self.worker.failed.connect(self._on_failure)
        self.worker.finished.connect(self._on_finished)
        self._enable_actions()
        self.statusBar().showMessage(f"{label} · Running in background…")
        self.worker.start()

    @Slot(object)
    def _on_result(self, result: object) -> None:
        if self.result_callback:
            self.result_callback(result)

    @Slot(str)
    def _on_failure(self, message: str) -> None:
        self.statusBar().showMessage(message)
        self.report_result.setPlainText(message)
        if not self.close_pending:
            QMessageBox.warning(self, "Operation failed", message)

    @Slot()
    def _on_finished(self) -> None:
        worker = self.worker
        self.worker = None
        self.result_callback = None
        if worker:
            worker.deleteLater()
        self._enable_actions()
        if self.close_pending:
            QTimer.singleShot(0, self.close)

    @Slot()
    def refresh(self) -> None:
        config = copy.deepcopy(self.config)
        self._run_task("Refresh", lambda: self.backend.collect(config), self._show_snapshot)

    def _show_snapshot(self, result: object) -> None:
        if not isinstance(result, Snapshot):
            return
        self.snapshot = result
        rows = status_rows(result)
        overview_keys = {
            "System": list(rows["System"]),
            "Network": ["Assessment", "Connection", "Band", "Signal", "TX link bitrate", "Gateway ping", "PC ping"],
            "VR": ["SteamVR", *[p.name for p in result.vr.processes], "OpenXR"],
            "Audio": ["Output", "Input", "Microphone mute", "Mic level"],
        }
        if result.network.connection_type == "Ethernet":
            overview_keys["Network"].append("Ethernet link speed")
        for name, panel in self.overview_panels.items():
            panel.update_rows({key: rows[name][key] for key in overview_keys[name]})
        for name, panel in self.panels.items():
            panel.update_rows(rows[name])
        self.overview_status.setText(f"{'MOCK · ' if result.mock else ''}Network: {health_label(result.network.health)} · Updated {result.collected_at}")
        warnings = result.network.warnings + result.errors
        if self.store.last_error:
            warnings.append(self.store.last_error)
        self.warnings.setText("Warnings\n" + ("\n".join(warnings) if warnings else "None detected. Unavailable values may remain."))
        self.statusBar().showMessage("Refresh complete" + (" · Some services unavailable" if result.errors else ""))

    @Slot()
    def restart(self) -> None:
        plan = self.backend.restart_backend.plan()
        if not plan.available:
            self.statusBar().showMessage(plan.reason)
            return
        answer = QMessageBox.question(
            self, "Confirm SteamVR restart", f"{plan.description}\n\nTimeout: {plan.timeout_seconds:g} seconds.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        LOG.info("SteamVR restart requested after user confirmation")
        self._run_task("Restart SteamVR", self.backend.restart_backend.restart, self._show_restart)

    def _show_restart(self, result: object) -> None:
        if isinstance(result, ActionResult):
            LOG.log(logging.INFO if result.success else logging.WARNING, "Restart success=%s", result.success)
            self.statusBar().showMessage(result.message)
            if not result.success:
                QMessageBox.warning(self, "Restart unavailable", result.message)

    @Slot()
    def collect_diagnostics(self) -> None:
        config = copy.deepcopy(self.config)
        include = self.include_journal.isChecked()
        root = self.reports_root

        def collect() -> tuple[Snapshot, DiagnosticReport]:
            snapshot = self.backend.collect(config)
            return snapshot, self.diagnostics.collect(snapshot, root, include_journal=include)

        self._run_task("Collect Diagnostics", collect, self._show_report)

    def _show_report(self, result: object) -> None:
        snapshot, report = result
        self._show_snapshot(snapshot)
        self.report_result.setPlainText(f"Diagnostics ZIP created\n\n{report.archive}\n\nUncompressed report\n{report.directory}\n\nReview the report before sharing. Mock data is marked in summary.json.")
        self.tabs.setCurrentIndex(4)
        self.statusBar().showMessage("Diagnostics ZIP created")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None:
            # terminate()は使わず期限付き診断が終わるまでイベントループを保つ。
            self.close_pending = True
            self.timer.stop()
            self.statusBar().showMessage("Closing after the current background operation finishes…")
            event.ignore()
            return
        self.timer.stop()
        event.accept()
