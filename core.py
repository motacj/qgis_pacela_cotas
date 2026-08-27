"""Cálculos geométricos independientes de QGIS.

Este módulo se mantiene sin dependencias de PyQGIS para poder verificar la
geometría básica con pruebas unitarias normales.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, pi, sin
from typing import Callable, Iterable, List, Sequence, Tuple

Point = Tuple[float, float]
Segment = Tuple[Point, Point]
DEFAULT_TEXT_POINTS = 8.0


@dataclass(frozen=True)
class DimensionGeometry:
    """Geometría auxiliar correspondiente a un lado de un anillo."""

    dimension: Segment
    reference_start: Segment
    reference_end: Segment
    tick_start: Segment
    tick_end: Segment
    length: float
    angle: float


def points_equal(first: Point, second: Point, tolerance: float = 1.0e-9) -> bool:
    return hypot(first[0] - second[0], first[1] - second[1]) <= tolerance


def open_ring(points: Iterable[Point]) -> List[Point]:
    """Devuelve el anillo sin repetir el primer punto al final."""
    result = list(points)
    if len(result) > 1 and points_equal(result[0], result[-1]):
        result.pop()
    return result


def map_height_from_points(text_points: float, reference_scale: float) -> float:
    """Convierte puntos tipográficos a metros de terreno a una escala."""
    if text_points <= 0 or reference_scale <= 0:
        raise ValueError("La altura y la escala deben ser positivas")
    millimetres_on_paper = text_points * 25.4 / 72.0
    return millimetres_on_paper * reference_scale / 1000.0


def outside_label_point(
    vertex: Point,
    distance: float,
    is_inside: Callable[[Point], bool],
    centroid: Point,
    samples: int = 72,
) -> Point:
    """Busca un punto de rótulo exterior a la distancia indicada del vértice.

    Primero ensaya la dirección radial desde el centroide y luego gira a ambos
    lados hasta encontrar una dirección que quede fuera del polígono.
    """
    if distance <= 0:
        raise ValueError("La distancia del rótulo debe ser positiva")
    if samples < 8:
        raise ValueError("Se necesitan al menos ocho direcciones de búsqueda")

    radial_x = vertex[0] - centroid[0]
    radial_y = vertex[1] - centroid[1]
    if hypot(radial_x, radial_y) <= 1.0e-12:
        base_angle = 0.0
    else:
        base_angle = atan2(radial_y, radial_x)

    angles = [base_angle]
    step = 2.0 * pi / samples
    for index in range(1, samples // 2 + 1):
        angles.append(base_angle + index * step)
        angles.append(base_angle - index * step)

    for angle in angles:
        candidate = (
            vertex[0] + cos(angle) * distance,
            vertex[1] + sin(angle) * distance,
        )
        if not is_inside(candidate):
            return candidate

    # Caso degenerado: conserva el desplazamiento radial solicitado.
    return vertex[0] + cos(base_angle) * distance, vertex[1] + sin(base_angle) * distance


def readable_angle(dx: float, dy: float) -> float:
    """Ángulo en grados que mantiene el texto legible de izquierda a derecha."""
    angle = degrees(atan2(dy, dx))
    if angle > 90.0:
        angle -= 180.0
    elif angle <= -90.0:
        angle += 180.0
    return angle


def _point_plus(point: Point, vector: Point, factor: float) -> Point:
    return point[0] + vector[0] * factor, point[1] + vector[1] * factor


def dimension_for_edge(
    start: Point,
    end: Point,
    offset: float,
    reference_extension: float,
    tick_length: float,
    is_inside: Callable[[Point], bool],
    centroid: Point,
) -> DimensionGeometry:
    """Construye cota, referencias y trazos para un lado.

    Se ensayan las dos normales y se elige la que sale del material del
    polígono. El centroide sirve como desempate para geometrías complejas.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = hypot(dx, dy)
    if length <= 1.0e-12:
        raise ValueError("No se puede acotar un segmento de longitud nula")

    tangent = (dx / length, dy / length)
    normal_a = (-tangent[1], tangent[0])
    midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    probe_distance = max(min(max(offset, reference_extension) * 0.1, length * 0.1), 1.0e-6)
    probe_a = _point_plus(midpoint, normal_a, probe_distance)
    normal_b = (-normal_a[0], -normal_a[1])
    probe_b = _point_plus(midpoint, normal_b, probe_distance)

    inside_a = is_inside(probe_a)
    inside_b = is_inside(probe_b)
    if inside_a != inside_b:
        normal = normal_b if inside_a else normal_a
    else:
        to_centroid = (centroid[0] - midpoint[0], centroid[1] - midpoint[1])
        normal = normal_a if normal_a[0] * to_centroid[0] + normal_a[1] * to_centroid[1] < 0 else normal_b

    dim_start = _point_plus(start, normal, offset)
    dim_end = _point_plus(end, normal, offset)
    ref_start_end = _point_plus(dim_start, normal, reference_extension)
    ref_end_end = _point_plus(dim_end, normal, reference_extension)

    # Trazo oblicuo a 45 grados respecto de la línea de cota.
    slash = (tangent[0] + normal[0], tangent[1] + normal[1])
    slash_norm = hypot(slash[0], slash[1])
    slash = (slash[0] / slash_norm, slash[1] / slash_norm)
    tick_half = tick_length / 2.0

    def tick(center: Point) -> Segment:
        return (
            _point_plus(center, slash, -tick_half),
            _point_plus(center, slash, tick_half),
        )

    return DimensionGeometry(
        dimension=(dim_start, dim_end),
        reference_start=(start, ref_start_end),
        reference_end=(end, ref_end_end),
        tick_start=tick(dim_start),
        tick_end=tick(dim_end),
        length=length,
        angle=readable_angle(dx, dy),
    )


def spanish_number(value: float, decimals: int = 2) -> str:
    """Formatea con punto de millares y coma decimal."""
    raw = f"{value:,.{decimals}f}"
    return raw.replace(",", "#").replace(".", ",").replace("#", ".")


def validate_ring(points: Sequence[Point]) -> None:
    if len(open_ring(points)) < 3:
        raise ValueError("El anillo debe tener al menos tres vértices")
