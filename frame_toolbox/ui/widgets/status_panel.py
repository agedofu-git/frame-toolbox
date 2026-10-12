# キーと値を読みやすく表示する共通パネル。
# 生のシステム文字列をHTMLとして解釈せず表示する。
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel


class StatusPanel(QGroupBox):
    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.form = QFormLayout(self)
        self.form.setContentsMargins(18, 24, 18, 16)
        self.form.setVerticalSpacing(10)
        self.form.setHorizontalSpacing(18)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.values: dict[str, QLabel] = {}

    def update_rows(self, rows: dict[str, str]) -> None:
        if list(rows) != list(self.values):
            while self.form.rowCount():
                self.form.removeRow(0)
            self.values.clear()
            for key in rows:
                label = QLabel()
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                label.setWordWrap(True)
                self.form.addRow(key, label)
                self.values[key] = label
        for key, value in rows.items():
            self.values[key].setText(value)
