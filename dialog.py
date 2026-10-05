"""Cuadro de configuración del complemento."""

from __future__ import annotations

import os

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .core import DEFAULT_TEXT_POINTS, map_height_from_points


class SettingsDialog(QDialog):
    """Solicita únicamente los parámetros que dependen del plano."""

    def __init__(
        self,
        layer_name: str,
        feature_id: int,
        default_path: str,
        source_fields,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Acotar parcela seleccionada")
        self.setMinimumWidth(560)
        settings = QSettings()

        intro = QLabel(
            f"Capa: <b>{layer_name}</b> &nbsp; | &nbsp; Elemento seleccionado: <b>{feature_id}</b>"
        )
        intro.setWordWrap(True)

        fixed = QLabel(
            "Configuración fija: Arial 8 pt; trazo de terminación = 1/2 de la altura "
            "del texto; prolongación de referencias = 1 altura de texto; separación "
            "mínima de la cota = 2 alturas de texto. El reconocimiento de arcos "
            "requiere al menos tres tramos consecutivos."
        )
        fixed.setWordWrap(True)

        self.path_edit = QLineEdit(
            settings.value("PacelaResultCotas/outputPath", default_path, type=str)
        )
        browse = QPushButton("Examinar…")
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(1.0, 1_000_000.0)
        self.scale_spin.setDecimals(0)
        self.scale_spin.setValue(
            settings.value("PacelaResultCotas/referenceScale", 500.0, type=float)
        )
        self.scale_spin.setSuffix("  (1 : n)")

        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(0.01, 1_000_000.0)
        self.offset_spin.setDecimals(3)
        self.offset_spin.setValue(
            settings.value("PacelaResultCotas/offsetMetres", 4.0, type=float)
        )
        self.offset_spin.setSuffix(" m")

        self.minimum_offset_label = QLabel()
        self.scale_spin.valueChanged.connect(self._update_minimum_offset)

        self.surface_field_combo = QComboBox()
        self.surface_field_combo.addItem("(Ninguno)", "")
        for field in source_fields:
            alias = field.alias() or field.name()
            label = field.name() if alias == field.name() else f"{alias} [{field.name()}]"
            self.surface_field_combo.addItem(label, field.name())
        saved_field = settings.value("PacelaResultCotas/surfaceField", "", type=str)
        saved_index = self.surface_field_combo.findData(saved_field)
        self.surface_field_combo.setCurrentIndex(saved_index if saved_index >= 0 else 0)

        self.precision_spin = QSpinBox()
        self.precision_spin.setRange(0, 6)
        self.precision_spin.setValue(settings.value("PacelaResultCotas/decimals", 2, type=int))

        self.detect_arcs_check = QCheckBox(
            "Sustituir cadenas curvas de segmentos cortos por una cota radial"
        )
        self.detect_arcs_check.setChecked(
            settings.value("PacelaResultCotas/detectArcs", True, type=bool)
        )

        self.arc_segment_spin = QDoubleSpinBox()
        self.arc_segment_spin.setRange(0.01, 100.0)
        self.arc_segment_spin.setDecimals(3)
        self.arc_segment_spin.setValue(
            settings.value("PacelaResultCotas/arcMaximumSegment", 1.0, type=float)
        )
        self.arc_segment_spin.setSuffix(" m")

        self.arc_tolerance_spin = QDoubleSpinBox()
        self.arc_tolerance_spin.setRange(0.001, 1.0)
        self.arc_tolerance_spin.setDecimals(3)
        self.arc_tolerance_spin.setSingleStep(0.005)
        self.arc_tolerance_spin.setValue(
            settings.value("PacelaResultCotas/arcTolerance", 0.03, type=float)
        )
        self.arc_tolerance_spin.setSuffix(" m")

        self.detect_arcs_check.toggled.connect(self.arc_segment_spin.setEnabled)
        self.detect_arcs_check.toggled.connect(self.arc_tolerance_spin.setEnabled)
        self.arc_segment_spin.setEnabled(self.detect_arcs_check.isChecked())
        self.arc_tolerance_spin.setEnabled(self.detect_arcs_check.isChecked())

        form = QFormLayout()
        form.addRow("GeoPackage de salida:", path_row)
        form.addRow("Escala de referencia:", self.scale_spin)
        form.addRow("Separación parcela-cota:", self.offset_spin)
        form.addRow("Mínimo calculado:", self.minimum_offset_label)
        form.addRow("Decimales de las cotas:", self.precision_spin)
        form.addRow("Campo en texto de superficie:", self.surface_field_combo)
        form.addRow("Reconocimiento de arcos:", self.detect_arcs_check)
        form.addRow("Longitud máxima de cada tramo:", self.arc_segment_spin)
        form.addRow("Tolerancia del ajuste circular:", self.arc_tolerance_spin)

        note = QLabel(
            "Si el GeoPackage ya existe, se añadirán los nuevos resultados con un identificador "
            "de ejecución; no se borrarán las mediciones anteriores."
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(fixed)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self._update_minimum_offset()

    def _update_minimum_offset(self):
        minimum = 2.0 * map_height_from_points(DEFAULT_TEXT_POINTS, self.scale_spin.value())
        self.offset_spin.setMinimum(minimum)
        if self.offset_spin.value() < minimum:
            self.offset_spin.setValue(minimum)
        self.minimum_offset_label.setText(f"{minimum:.3f} m (2 × altura de texto)")

    def _browse(self):
        current = self.path_edit.text().strip()
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar base de datos de cotas",
            current,
            "GeoPackage (*.gpkg)",
        )
        if selected:
            if not selected.lower().endswith(".gpkg"):
                selected += ".gpkg"
            self.path_edit.setText(os.path.normpath(selected))

    def values(self):
        path = self.path_edit.text().strip()
        if path and not path.lower().endswith(".gpkg"):
            path += ".gpkg"
        return {
            "path": os.path.normpath(path) if path else "",
            "reference_scale": self.scale_spin.value(),
            "offset": self.offset_spin.value(),
            "decimals": self.precision_spin.value(),
            "surface_field": self.surface_field_combo.currentData() or "",
            "detect_arcs": self.detect_arcs_check.isChecked(),
            "arc_maximum_segment": self.arc_segment_spin.value(),
            "arc_tolerance": self.arc_tolerance_spin.value(),
        }

    def accept(self):
        values = self.values()
        if not values["path"]:
            self.path_edit.setFocus()
            return
        settings = QSettings()
        settings.setValue("PacelaResultCotas/outputPath", values["path"])
        settings.setValue("PacelaResultCotas/referenceScale", values["reference_scale"])
        settings.setValue("PacelaResultCotas/offsetMetres", values["offset"])
        settings.setValue("PacelaResultCotas/decimals", values["decimals"])
        settings.setValue("PacelaResultCotas/surfaceField", values["surface_field"])
        settings.setValue("PacelaResultCotas/detectArcs", values["detect_arcs"])
        settings.setValue(
            "PacelaResultCotas/arcMaximumSegment",
            values["arc_maximum_segment"],
        )
        settings.setValue("PacelaResultCotas/arcTolerance", values["arc_tolerance"])
        super().accept()
