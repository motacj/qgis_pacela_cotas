"""Implementación principal de Acotación de parcela GIS."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from qgis.PyQt.QtCore import QStandardPaths, QVariant
from qgis.PyQt.QtGui import QColor, QFont, QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QMessageBox
from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsLineSymbol,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsProject,
    QgsRendererCategory,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)

from .core import (
    DEFAULT_TEXT_POINTS,
    dimension_for_edge,
    map_height_from_points,
    open_ring,
    outside_label_point,
    spanish_number,
)
from .dialog import SettingsDialog


PLUGIN_TITLE = "Acotación de parcela GIS"
OUTPUT_FILENAME = "Pacela_result_cotas.gpkg"
TEXT_POINTS = DEFAULT_TEXT_POINTS


class PacelaResultCotasPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icon = QIcon(os.path.join(self.plugin_dir, "icon.png"))
        self.action = QAction(icon, "Acotar parcela seleccionada", self.iface.mainWindow())
        self.action.setObjectName("PacelaResultCotasAction")
        self.action.setToolTip("Crea cotas, vértices, coordenadas y superficie de una parcela")
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu(PLUGIN_TITLE, self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginVectorMenu(PLUGIN_TITLE, self.action)
            self.action.deleteLater()
            self.action = None

    def run(self):
        source_layer = self.iface.activeLayer()
        validation_error = self._validate_selection(source_layer)
        if validation_error:
            QMessageBox.warning(self.iface.mainWindow(), PLUGIN_TITLE, validation_error)
            return

        source_feature = source_layer.selectedFeatures()[0]
        default_path = self._default_output_path()
        dialog = SettingsDialog(
            source_layer.name(),
            source_feature.id(),
            default_path,
            source_layer.fields(),
            self.iface.mainWindow(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        config = dialog.values()

        try:
            result = self._create_result(source_layer, source_feature, config)
            self._load_and_style(config["path"], result["run_id"])
        except Exception as exc:  # La interfaz debe informar sin cerrar QGIS.
            QMessageBox.critical(
                self.iface.mainWindow(),
                PLUGIN_TITLE,
                "No se pudo crear la acotación.\n\n" + str(exc),
            )
            return

        QMessageBox.information(
            self.iface.mainWindow(),
            PLUGIN_TITLE,
            "Acotación creada correctamente.\n\n"
            f"Vértices: {result['vertex_count']}\n"
            f"Superficie GIS: {spanish_number(result['area'], 2)} m²\n"
            f"Base de datos: {config['path']}",
        )

    def _validate_selection(self, layer):
        if not isinstance(layer, QgsVectorLayer):
            return "Activa una capa vectorial de polígonos."
        if (
            QgsWkbTypes.geometryType(layer.wkbType())
            != QgsWkbTypes.GeometryType.PolygonGeometry
        ):
            return "La capa activa debe ser de tipo polígono o multipolígono."
        if layer.selectedFeatureCount() != 1:
            return "Selecciona exactamente una parcela en la capa activa."
        if not layer.crs().isValid():
            return "La capa no tiene un sistema de referencia válido."
        return None

    def _default_output_path(self):
        project = QgsProject.instance()
        folder = project.homePath()
        if not folder:
            folder = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation
            )
        return os.path.join(folder, OUTPUT_FILENAME)

    @staticmethod
    def _is_metric_projected(crs):
        return crs.isValid() and not crs.isGeographic() and crs.mapUnits() == Qgis.DistanceUnit.Meters

    def _metric_geometry(self, source_layer, source_feature):
        source_crs = source_layer.crs()
        target_crs = source_crs
        if not self._is_metric_projected(target_crs):
            project_crs = QgsProject.instance().crs()
            if not self._is_metric_projected(project_crs):
                raise ValueError(
                    "La capa y el proyecto deben usar un CRS proyectado en metros. "
                    "Para el plano aportado se recomienda ETRS89 / UTM huso 30N (EPSG:25830)."
                )
            target_crs = project_crs

        geometry = source_feature.geometry()
        if geometry is None or geometry.isEmpty():
            raise ValueError("La parcela seleccionada no tiene geometría.")
        geometry = QgsGeometry(geometry)
        geometry.convertToStraightSegment()
        if source_crs != target_crs:
            transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
            geometry.transform(transform)
        if not geometry.isGeosValid():
            geometry = geometry.makeValid()
        if (
            geometry.isEmpty()
            or QgsWkbTypes.geometryType(geometry.wkbType())
            != QgsWkbTypes.GeometryType.PolygonGeometry
        ):
            raise ValueError("La geometría no es un polígono válido después de su reparación.")
        if not geometry.isMultipart() and not geometry.convertToMultiType():
            raise ValueError("No se pudo normalizar la parcela como multipolígono.")
        return geometry, target_crs

    def _create_result(self, source_layer, source_feature, config):
        output_path = os.path.abspath(config["path"])
        output_folder = os.path.dirname(output_path)
        if not os.path.isdir(output_folder):
            os.makedirs(output_folder, exist_ok=True)

        geometry, crs = self._metric_geometry(source_layer, source_feature)
        area = geometry.area()
        if area <= 0:
            raise ValueError("La parcela tiene una superficie nula.")

        run_id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        text_map_height = map_height_from_points(TEXT_POINTS, config["reference_scale"])
        reference_extension = text_map_height
        tick_length = text_map_height / 2.0
        dimension_offset = max(config["offset"], 2.0 * text_map_height)
        vertex_label_distance = 1.25 * text_map_height

        parcel_layer = self._memory_layer(
            "MultiPolygon",
            "parcela_acotada",
            crs,
            [
                QgsField("run_id", QVariant.String, len=32),
                QgsField("capa_orig", QVariant.String, len=254),
                QgsField("fid_orig", QVariant.LongLong),
                QgsField("superf_m2", QVariant.Double, len=20, prec=3),
                QgsField("crs", QVariant.String, len=64),
                QgsField("fecha_utc", QVariant.String, len=32),
            ],
        )
        parcel_feature = QgsFeature(parcel_layer.fields())
        parcel_feature.setGeometry(geometry)
        parcel_feature.setAttributes(
            [run_id, source_layer.name(), source_feature.id(), area, crs.authid() or crs.description(), timestamp]
        )
        if not parcel_layer.dataProvider().addFeature(parcel_feature):
            raise RuntimeError("No se pudo preparar la geometría de la parcela.")

        dimension_layer = self._memory_layer(
            "LineString",
            "lineas_cota",
            crs,
            [
                QgsField("run_id", QVariant.String, len=32),
                QgsField("tipo", QVariant.String, len=16),
                QgsField("lado", QVariant.Int),
                QgsField("v_inicio", QVariant.Int),
                QgsField("v_fin", QVariant.Int),
                QgsField("long_m", QVariant.Double, len=20, prec=4),
                QgsField("texto", QVariant.String, len=64),
                QgsField("angulo", QVariant.Double, len=10, prec=4),
                QgsField("escala", QVariant.Double, len=12, prec=0),
            ],
        )
        vertex_layer = self._memory_layer(
            "Point",
            "tabla_vertices",
            crs,
            [
                QgsField("run_id", QVariant.String, len=32),
                QgsField("vertice", QVariant.Int),
                QgsField("parte", QVariant.Int),
                QgsField("anillo", QVariant.Int),
                QgsField("x", QVariant.Double, len=20, prec=3),
                QgsField("y", QVariant.Double, len=20, prec=3),
                QgsField("texto", QVariant.String, len=16),
            ],
        )
        vertex_label_layer = self._memory_layer(
            "Point",
            "rotulos_vertices",
            crs,
            [
                QgsField("run_id", QVariant.String, len=32),
                QgsField("vertice", QVariant.Int),
                QgsField("texto", QVariant.String, len=16),
                QgsField("dist_m", QVariant.Double, len=20, prec=4),
            ],
        )
        surface_layer = self._memory_layer(
            "Point",
            "texto_superficie",
            crs,
            [
                QgsField("run_id", QVariant.String, len=32),
                QgsField("superf_m2", QVariant.Double, len=20, prec=3),
                QgsField("campo_orig", QVariant.String, len=128),
                QgsField("valor_orig", QVariant.String, len=512),
                QgsField("ubicacion", QVariant.String, len=16),
                QgsField("texto", QVariant.String, len=1024),
            ],
        )

        centroid_geom = geometry.centroid()
        if centroid_geom.isEmpty() or not geometry.contains(centroid_geom):
            centroid_geom = geometry.pointOnSurface()
        centroid_point = centroid_geom.asPoint()
        centroid = (centroid_point.x(), centroid_point.y())

        polygons = geometry.asMultiPolygon() if geometry.isMultipart() else [geometry.asPolygon()]
        vertex_number = 1
        side_number = 1
        for part_index, polygon in enumerate(polygons, start=1):
            for ring_index, qgs_ring in enumerate(polygon, start=1):
                ring = open_ring((point.x(), point.y()) for point in qgs_ring)
                if len(ring) < 3:
                    continue
                numbers = list(range(vertex_number, vertex_number + len(ring)))
                for number, point in zip(numbers, ring):
                    feature = QgsFeature(vertex_layer.fields())
                    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))
                    feature.setAttributes(
                        [run_id, number, part_index, ring_index, point[0], point[1], str(number)]
                    )
                    if not vertex_layer.dataProvider().addFeature(feature):
                        raise RuntimeError(f"No se pudo preparar el vértice {number}.")

                    def is_inside(point_to_test):
                        return geometry.contains(
                            QgsGeometry.fromPointXY(QgsPointXY(point_to_test[0], point_to_test[1]))
                        )

                    label_point = outside_label_point(
                        point,
                        vertex_label_distance,
                        is_inside,
                        centroid,
                    )
                    label_feature = QgsFeature(vertex_label_layer.fields())
                    label_feature.setGeometry(
                        QgsGeometry.fromPointXY(QgsPointXY(label_point[0], label_point[1]))
                    )
                    label_feature.setAttributes(
                        [run_id, number, str(number), vertex_label_distance]
                    )
                    if not vertex_label_layer.dataProvider().addFeature(label_feature):
                        raise RuntimeError(f"No se pudo preparar el rótulo del vértice {number}.")

                for index, start in enumerate(ring):
                    end = ring[(index + 1) % len(ring)]

                    def is_inside(point):
                        return geometry.contains(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))

                    try:
                        dim = dimension_for_edge(
                            start,
                            end,
                            dimension_offset,
                            reference_extension,
                            tick_length,
                            is_inside,
                            centroid,
                        )
                    except ValueError:
                        continue

                    start_number = numbers[index]
                    end_number = numbers[(index + 1) % len(numbers)]
                    dimension_text = spanish_number(dim.length, config["decimals"])
                    geometries = (
                        ("dimension", dim.dimension, dim.length, dimension_text),
                        ("referencia", dim.reference_start, None, ""),
                        ("referencia", dim.reference_end, None, ""),
                        ("trazo", dim.tick_start, None, ""),
                        ("trazo", dim.tick_end, None, ""),
                    )
                    for kind, segment, length_value, text_value in geometries:
                        feature = QgsFeature(dimension_layer.fields())
                        feature.setGeometry(self._line_geometry(segment))
                        feature.setAttributes(
                            [
                                run_id,
                                kind,
                                side_number,
                                start_number,
                                end_number,
                                length_value,
                                text_value,
                                dim.angle,
                                config["reference_scale"],
                            ]
                        )
                        if not dimension_layer.dataProvider().addFeature(feature):
                            raise RuntimeError(f"No se pudo preparar la geometría del lado {side_number}.")
                    side_number += 1
                vertex_number += len(ring)

        if vertex_number == 1:
            raise ValueError("No se encontraron vértices válidos en la parcela.")

        field_name, field_value, field_line = self._surface_field_text(
            source_layer, source_feature, config.get("surface_field", "")
        )
        area_line = f"Sup. GIS={spanish_number(area, 2)} m²"
        area_text = f"{field_line}\n{area_line}" if field_line else area_line
        surface_point, surface_location, leader_segment = self._surface_placement(
            geometry,
            centroid,
            area_text,
            text_map_height,
        )
        if leader_segment is not None:
            leader_feature = QgsFeature(dimension_layer.fields())
            leader_feature.setGeometry(self._line_geometry(leader_segment))
            leader_feature.setAttributes(
                [run_id, "llamada", None, None, None, None, "", 0.0, config["reference_scale"]]
            )
            if not dimension_layer.dataProvider().addFeature(leader_feature):
                raise RuntimeError("No se pudo preparar la llamada de superficie.")

        area_feature = QgsFeature(surface_layer.fields())
        area_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(surface_point[0], surface_point[1])))
        area_feature.setAttributes(
            [run_id, area, field_name, field_value, surface_location, area_text]
        )
        if not surface_layer.dataProvider().addFeature(area_feature):
            raise RuntimeError("No se pudo preparar el texto de superficie.")

        for layer in (
            parcel_layer,
            dimension_layer,
            vertex_layer,
            vertex_label_layer,
            surface_layer,
        ):
            self._write_or_append(layer, output_path)

        return {"run_id": run_id, "vertex_count": vertex_number - 1, "area": area}

    @staticmethod
    def _memory_layer(geometry_type, name, crs, fields):
        layer = QgsVectorLayer(geometry_type, name, "memory")
        if not layer.isValid():
            raise RuntimeError(f"No se pudo crear la capa temporal {name}.")
        layer.setCrs(crs)
        layer.dataProvider().addAttributes(fields)
        layer.updateFields()
        return layer

    @staticmethod
    def _line_geometry(segment):
        return QgsGeometry.fromPolylineXY(
            [QgsPointXY(segment[0][0], segment[0][1]), QgsPointXY(segment[1][0], segment[1][1])]
        )

    @staticmethod
    def _surface_field_text(source_layer, source_feature, field_name):
        if not field_name:
            return "", "", ""
        field_index = source_layer.fields().indexOf(field_name)
        if field_index < 0:
            return "", "", ""
        field = source_layer.fields().at(field_index)
        value = source_feature[field_name]
        value_text = "" if value is None or str(value).upper() == "NULL" else str(value)
        alias = field.alias() or field.name()
        return field.name(), value_text, f"{alias}: {value_text}"

    @staticmethod
    def _surface_placement(geometry, centroid, text, text_map_height):
        lines = text.splitlines() or [text]
        width = max(max(len(line), 1) * text_map_height * 0.56 for line in lines)
        height = max(len(lines), 1) * text_map_height * 1.20
        half_width = width / 2.0
        half_height = height / 2.0
        box_points = [
            QgsPointXY(centroid[0] - half_width, centroid[1] - half_height),
            QgsPointXY(centroid[0] + half_width, centroid[1] - half_height),
            QgsPointXY(centroid[0] + half_width, centroid[1] + half_height),
            QgsPointXY(centroid[0] - half_width, centroid[1] + half_height),
            QgsPointXY(centroid[0] - half_width, centroid[1] - half_height),
        ]
        label_box = QgsGeometry.fromPolygonXY([box_points])
        if geometry.contains(label_box):
            return centroid, "interior", None

        bounds = geometry.boundingBox()
        label_center = (
            bounds.xMaximum() + text_map_height + half_width,
            centroid[1],
        )
        leader_end = (label_center[0] - half_width, label_center[1])
        return label_center, "exterior", (centroid, leader_end)

    def _write_or_append(self, memory_layer, output_path):
        layer_name = memory_layer.name()
        uri = f"{output_path}|layername={layer_name}"
        existing = QgsVectorLayer(uri, layer_name, "ogr") if os.path.exists(output_path) else None

        if existing is not None and existing.isValid():
            required = {field.name() for field in memory_layer.fields()}
            available = {field.name() for field in existing.fields()}
            missing_fields = [
                field for field in memory_layer.fields() if field.name() not in available
            ]
            if missing_fields:
                if not existing.dataProvider().addAttributes(missing_fields):
                    names = ", ".join(field.name() for field in missing_fields)
                    raise RuntimeError(
                        f"No se pudieron añadir estos campos a {layer_name}: {names}."
                    )
                existing.updateFields()
            features = []
            for source in memory_layer.getFeatures():
                target = QgsFeature(existing.fields())
                target.setGeometry(source.geometry())
                for field_name in required:
                    target[field_name] = source[field_name]
                features.append(target)
            ok, _ = existing.dataProvider().addFeatures(features)
            if not ok:
                raise RuntimeError(f"No se pudieron añadir registros a {layer_name}.")
            existing.updateExtents()
            return

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_name
        options.fileEncoding = "UTF-8"
        if os.path.exists(output_path):
            options.actionOnExistingFile = (
                QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
            )
        else:
            options.actionOnExistingFile = (
                QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
            )
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            memory_layer,
            output_path,
            QgsProject.instance().transformContext(),
            options,
        )
        if result[0] != QgsVectorFileWriter.WriterError.NoError:
            details = result[1] if len(result) > 1 else "error desconocido"
            raise RuntimeError(f"No se pudo crear {layer_name}: {details}")

    def _load_and_style(self, output_path, run_id):
        project = QgsProject.instance()
        group = project.layerTreeRoot().addGroup(f"Cotas parcela {run_id[:8]}")
        loaded = {}
        for layer_name, display_name in (
            ("parcela_acotada", "Parcela acotada"),
            ("lineas_cota", "Líneas de cota"),
            ("tabla_vertices", "Tabla de coordenadas de vértice"),
            ("rotulos_vertices", "Números de vértice"),
            ("texto_superficie", "Superficie GIS"),
        ):
            uri = f"{output_path}|layername={layer_name}"
            layer = QgsVectorLayer(uri, display_name, "ogr")
            if not layer.isValid():
                raise RuntimeError(f"Se creó la base, pero QGIS no pudo abrir {layer_name}.")
            layer.setSubsetString(f"\"run_id\" = '{run_id}'")
            self._apply_style(layer, layer_name)
            project.addMapLayer(layer, False)
            group.addLayer(layer)
            loaded[layer_name] = layer

        extent = loaded["parcela_acotada"].extent()
        for layer_name in ("lineas_cota", "rotulos_vertices", "texto_superficie"):
            layer_extent = loaded[layer_name].extent()
            if not layer_extent.isEmpty():
                extent.combineExtentWith(layer_extent)
        if not extent.isEmpty():
            margin = max(extent.width(), extent.height()) * 0.15
            extent.grow(margin)
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()
        self.iface.showAttributeTable(loaded["tabla_vertices"])

    def _apply_style(self, layer, layer_name):
        if layer_name == "parcela_acotada":
            symbol = QgsFillSymbol.createSimple(
                {
                    "color": "0,102,255,30",
                    "outline_color": "0,76,230,255",
                    "outline_width": "0.55",
                }
            )
            layer.renderer().setSymbol(symbol)
        elif layer_name == "lineas_cota":
            categories = []
            for value, label, color, width in (
                ("dimension", "Línea de cota", "25,25,25", "0.38"),
                ("referencia", "Línea de referencia", "45,45,45", "0.28"),
                ("trazo", "Trazo de terminación", "25,25,25", "0.45"),
                ("llamada", "Llamada de superficie", "25,25,25", "0.32"),
            ):
                symbol = QgsLineSymbol.createSimple({"line_color": color, "line_width": width})
                categories.append(QgsRendererCategory(value, symbol, label))
            layer.setRenderer(QgsCategorizedSymbolRenderer("tipo", categories))
            self._set_labels(layer, "texto", Qgis.LabelPlacement.Line, bold=False, buffer=True)
        elif layer_name == "tabla_vertices":
            marker = layer.renderer().symbol()
            marker.setColor(QColor(0, 76, 230))
            marker.setSize(1.8)
            layer.setLabelsEnabled(False)
        elif layer_name == "rotulos_vertices":
            marker = layer.renderer().symbol()
            marker.setSize(0.0)
            self._set_labels(layer, "texto", Qgis.LabelPlacement.OverPoint, bold=True, buffer=True)
        elif layer_name == "texto_superficie":
            marker = layer.renderer().symbol()
            marker.setSize(0.0)
            self._set_labels(layer, "texto", Qgis.LabelPlacement.OverPoint, bold=True, buffer=True)

        layer.triggerRepaint()
        # El GeoPackage admite guardar el estilo QGIS como estilo predeterminado.
        try:
            layer.saveStyleToDatabase("Pacela Cotas 1.1", "Estilo generado por el complemento", True, "")
        except Exception:
            pass

    @staticmethod
    def _set_labels(layer, field_name, placement, bold=False, buffer=False):
        settings = QgsPalLayerSettings()
        settings.enabled = True
        settings.fieldName = field_name
        settings.placement = placement
        settings.displayAll = True

        text_format = QgsTextFormat()
        font = QFont("Arial")
        font.setBold(bold)
        text_format.setFont(font)
        text_format.setSize(TEXT_POINTS)
        text_format.setSizeUnit(Qgis.RenderUnit.Points)
        text_format.setColor(QColor(20, 20, 20))
        if buffer:
            buffer_settings = QgsTextBufferSettings()
            buffer_settings.setEnabled(True)
            buffer_settings.setSize(0.8)
            buffer_settings.setColor(QColor(255, 255, 255))
            text_format.setBuffer(buffer_settings)
        settings.setFormat(text_format)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        layer.setLabelsEnabled(True)
