from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import CardConfig
from .renderer import AssetPack, CardRenderer, save_card_image


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("STS2 Card Maker Desktop")
        self.resize(1280, 900)

        self.assets = AssetPack()
        self.renderer = CardRenderer(self.assets)
        self.config = CardConfig()
        self.rendered = None

        self._build_ui()
        self._apply_pool_rules()
        self._render_preview()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QGridLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)

        left_container = QWidget()
        left = QVBoxLayout()
        left.setContentsMargins(6, 6, 6, 6)
        left.setSpacing(6)
        left_container.setLayout(left)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_container)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(360)
        left_scroll.setMaximumWidth(430)
        layout.addWidget(left_scroll, 0, 0)

        note = QLabel('Official site: <a href="https://slaythespire2.gg">slaythespire2.gg</a>')
        note.setOpenExternalLinks(True)
        left.addWidget(note)

        card_box = QGroupBox("Card Settings")
        form = QFormLayout(card_box)
        form.setContentsMargins(8, 8, 8, 8)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(5)

        self.character = QComboBox()
        self.character.addItems(["ironclad", "silent", "defect", "necrobinder", "regent", "colorless", "quest", "status", "curse", "event", "token"])
        self.character.currentTextChanged.connect(self._on_change)

        self.card_type = QComboBox()
        self.card_type.addItems(["attack", "skill", "power"])
        self.card_type.currentTextChanged.connect(self._on_change)

        self.rarity = QComboBox()
        self.rarity.addItems(["basic", "common", "uncommon", "rare", "status", "curse", "event", "quest", "ancient"])
        self.rarity.currentTextChanged.connect(self._on_change)

        self.card_name = QLineEdit("Strike")
        self.card_name.textChanged.connect(self._on_change)

        self.cost = QLineEdit("1")
        self.cost.textChanged.connect(self._on_change)

        self.desc = QPlainTextEdit("Deal {6} damage.")
        self.desc.setFixedHeight(88)
        self.desc.textChanged.connect(self._on_change)

        self.upgraded = QCheckBox("Upgraded (+, green title)")
        self.upgraded.stateChanged.connect(self._on_change)

        self.cost_green = QCheckBox("Cost number in green")
        self.cost_green.stateChanged.connect(self._on_change)

        form.addRow("Character", self.character)
        form.addRow("Type", self.card_type)
        form.addRow("Rarity", self.rarity)
        form.addRow("Card Name", self.card_name)
        form.addRow("Cost", self.cost)
        form.addRow("Description", self.desc)
        desc_helpers = QHBoxLayout()
        btn_green = QPushButton("Green Text")
        btn_green.setToolTip("Insert [green]text[/green]")
        btn_green.clicked.connect(lambda: self._insert_desc_token("[green]text[/green]"))
        btn_energy = QPushButton("Energy Icon")
        btn_energy.setToolTip("Insert {Energy:energyIcons()}")
        btn_energy.clicked.connect(lambda: self._insert_desc_token("{Energy:energyIcons()}"))
        btn_star = QPushButton("Star Icon")
        btn_star.setToolTip("Insert {singleStarIcon}")
        btn_star.clicked.connect(lambda: self._insert_desc_token("{singleStarIcon}"))
        btn_green.setMinimumHeight(26)
        btn_energy.setMinimumHeight(26)
        btn_star.setMinimumHeight(26)
        btn_green.setMaximumHeight(26)
        btn_energy.setMaximumHeight(26)
        btn_star.setMaximumHeight(26)
        desc_helpers.addWidget(btn_green)
        desc_helpers.addWidget(btn_energy)
        desc_helpers_2 = QHBoxLayout()
        desc_helpers_2.addWidget(btn_star)
        desc_helpers_2.addStretch(1)
        form.addRow("", desc_helpers)
        form.addRow("", desc_helpers_2)
        form.addRow("", self.upgraded)
        form.addRow("", self.cost_green)

        left.addWidget(card_box)

        tune_box = QGroupBox("Layout Tune")
        tune_form = QFormLayout(tune_box)
        tune_form.setContentsMargins(8, 8, 8, 8)
        tune_form.setHorizontalSpacing(8)
        tune_form.setVerticalSpacing(5)
        self.canvas_offset_y = QSpinBox(); self.canvas_offset_y.setRange(-100, 200); self.canvas_offset_y.setValue(self.renderer.layout.canvas_offset_y)
        self.cost_y_offset = QSpinBox(); self.cost_y_offset.setRange(-50, 80); self.cost_y_offset.setValue(self.renderer.layout.cost_y_offset)
        self.banner_y = QSpinBox(); self.banner_y.setRange(-100, 200); self.banner_y.setValue(self.renderer.layout.banner_y_normal)
        self.title_y = QSpinBox(); self.title_y.setRange(-100, 200); self.title_y.setValue(self.renderer.layout.title_y_normal)
        self.desc_center_y = QSpinBox(); self.desc_center_y.setRange(450, 700); self.desc_center_y.setValue(self.renderer.layout.desc_center_y)
        for w in [self.canvas_offset_y, self.cost_y_offset, self.banner_y, self.title_y, self.desc_center_y]:
            w.valueChanged.connect(self._on_change)

        tune_form.addRow("Canvas Offset Y", self.canvas_offset_y)
        tune_form.addRow("Cost Y Offset", self.cost_y_offset)
        tune_form.addRow("Banner Y", self.banner_y)
        tune_form.addRow("Title Y", self.title_y)
        tune_form.addRow("Description Center Y", self.desc_center_y)
        left.addWidget(tune_box)

        btns = QHBoxLayout()
        self.pick_image = QPushButton("Select Portrait")
        self.pick_image.clicked.connect(self._pick_portrait)
        self.export_btn = QPushButton("Export PNG/WebP")
        self.export_btn.clicked.connect(self._export_image)
        btns.addWidget(self.pick_image)
        btns.addWidget(self.export_btn)
        left.addLayout(btns)

        self.portrait_label = QLabel("Portrait: (none)")
        self.portrait_label.setWordWrap(True)
        self.portrait_label.setMaximumHeight(36)
        left.addWidget(self.portrait_label)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(680, 840)
        layout.addWidget(self.preview, 0, 1)

    def _apply_pool_rules(self) -> None:
        ch = self.character.currentText()
        lock = ch in {"quest", "status", "curse"}
        self.card_type.setEnabled(not lock)
        self.rarity.setEnabled(not lock)
        if ch == "quest":
            self.card_type.setCurrentText("skill")
            self.rarity.setCurrentText("quest")
        elif ch == "status":
            self.card_type.setCurrentText("skill")
            self.rarity.setCurrentText("status")
        elif ch == "curse":
            self.card_type.setCurrentText("skill")
            self.rarity.setCurrentText("curse")

    def _on_change(self, *_args) -> None:
        self._apply_pool_rules()
        self.config.character = self.character.currentText()
        self.config.card_type = self.card_type.currentText()
        self.config.rarity = self.rarity.currentText()
        self.config.card_name = self.card_name.text()
        self.config.cost = self.cost.text()
        self.config.description = self.desc.toPlainText()
        self.config.upgraded = self.upgraded.isChecked()
        self.config.cost_green = self.cost_green.isChecked()

        self.renderer.layout.canvas_offset_y = self.canvas_offset_y.value()
        self.renderer.layout.cost_y_offset = self.cost_y_offset.value()
        self.renderer.layout.banner_y_normal = self.banner_y.value()
        self.renderer.layout.banner_y_ancient = self.banner_y.value()
        self.renderer.layout.title_y_normal = self.title_y.value()
        self.renderer.layout.title_y_ancient = self.title_y.value()
        self.renderer.layout.desc_center_y = self.desc_center_y.value()

        self._render_preview()

    def _insert_desc_token(self, token: str) -> None:
        cursor = self.desc.textCursor()
        cursor.insertText(token)
        self.desc.setTextCursor(cursor)
        self._on_change()

    def _pick_portrait(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select portrait", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        self.config.portrait_path = Path(path)
        self.portrait_label.setText(f"Portrait: {path}")
        self._render_preview()

    def _render_preview(self) -> None:
        try:
            self.rendered = self.renderer.render(self.config)
            qimg = ImageQt(self.rendered)
            pix = QPixmap.fromImage(qimg)
            self._set_preview_pixmap(pix)
        except Exception as exc:
            QMessageBox.critical(self, "Render failed", str(exc))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if self.rendered is not None:
            qimg = ImageQt(self.rendered)
            pix = QPixmap.fromImage(qimg)
            self._set_preview_pixmap(pix)

    def _set_preview_pixmap(self, pix: QPixmap) -> None:
        target = self.preview.size()
        if pix.width() <= target.width() and pix.height() <= target.height():
            self.preview.setPixmap(pix)
            return
        self.preview.setPixmap(pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _export_image(self) -> None:
        if self.rendered is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export card", "custom-card.png", "PNG (*.png);;WebP (*.webp)")
        if not path:
            return
        save_card_image(self.rendered, Path(path))
        QMessageBox.information(self, "Done", f"Saved to: {path}")


def run() -> None:
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()
