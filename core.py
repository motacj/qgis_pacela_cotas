"""Cálculos geométricos independientes de QGIS.

Este módulo se mantiene sin dependencias de PyQGIS para poder verificar la
geometría básica con pruebas unitarias normales.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, pi, sin, sqrt
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

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


@dataclass(frozen=True)
class CircleFit:
    """Circunferencia ajustada por mínimos cuadrados a varios puntos."""

    center: Point
    radius: float
    max_error: float


@dataclass(frozen=True)
class ArcDimension:
    """Cadena de lados que puede sustituirse por una única cota radial."""

    edge_indices: Tuple[int, ...]
    center: Point
    radius: float
    point_on_arc: Point
    sweep_degrees: float
    max_error: float


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


def _solve_linear_3(matrix, values) -> Optional[Tuple[float, float, float]]:
    """Resuelve un sistema 3 × 3 con pivoteo parcial."""
    rows = [list(row) + [float(value)] for row, value in zip(matrix, values)]
    scale = max((abs(value) for row in rows for value in row[:-1]), default=1.0)
    epsilon = max(scale * 1.0e-12, 1.0e-15)

    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) <= epsilon:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for row in range(3):
            if row == column:
                continue
            factor = rows[row][column]
            rows[row] = [
                current - factor * pivot_value
                for current, pivot_value in zip(rows[row], rows[column])
            ]
    return rows[0][3], rows[1][3], rows[2][3]


def fit_circle(points: Sequence[Point]) -> Optional[CircleFit]:
    """Ajusta una circunferencia sin perder precisión con coordenadas UTM."""
    unique = open_ring(points)
    if len(unique) < 3:
        return None

    mean_x = sum(point[0] for point in unique) / len(unique)
    mean_y = sum(point[1] for point in unique) / len(unique)
    rows = []
    values = []
    for x, y in unique:
        local_x = x - mean_x
        local_y = y - mean_y
        rows.append((2.0 * local_x, 2.0 * local_y, 1.0))
        values.append(local_x * local_x + local_y * local_y)

    normal_matrix = [[0.0] * 3 for _ in range(3)]
    normal_values = [0.0] * 3
    for row, value in zip(rows, values):
        for first in range(3):
            normal_values[first] += row[first] * value
            for second in range(3):
                normal_matrix[first][second] += row[first] * row[second]

    solution = _solve_linear_3(normal_matrix, normal_values)
    if solution is None:
        return None
    center_x, center_y, constant = solution
    radius_squared = constant + center_x * center_x + center_y * center_y
    if radius_squared <= 1.0e-12:
        return None

    radius = sqrt(radius_squared)
    center = (mean_x + center_x, mean_y + center_y)
    max_error = max(
        abs(hypot(point[0] - center[0], point[1] - center[1]) - radius)
        for point in unique
    )
    return CircleFit(center=center, radius=radius, max_error=max_error)


def _fit_arc_candidate(
    ring: Sequence[Point],
    edge_indices: Sequence[int],
    tolerance: float,
    minimum_sweep_degrees: float,
) -> Optional[ArcDimension]:
    """Valida el ajuste circular y el sentido de giro de una cadena."""
    if not edge_indices:
        return None
    ring_size = len(ring)
    points = [ring[edge_indices[0]]]
    points.extend(ring[(index + 1) % ring_size] for index in edge_indices)
    circle = fit_circle(points)
    if circle is None or circle.max_error > tolerance:
        return None

    angles = [
        atan2(point[1] - circle.center[1], point[0] - circle.center[0])
        for point in points
    ]
    direction = 0
    sweep = 0.0
    for first, second in zip(angles, angles[1:]):
        delta = second - first
        while delta <= -pi:
            delta += 2.0 * pi
        while delta > pi:
            delta -= 2.0 * pi
        if abs(delta) <= 1.0e-9:
            return None
        current_direction = 1 if delta > 0 else -1
        if direction and current_direction != direction:
            return None
        direction = current_direction
        sweep += delta

    sweep_degrees = abs(degrees(sweep))
    if sweep_degrees < minimum_sweep_degrees or sweep_degrees > 360.01:
        return None

    point_on_arc = points[len(points) // 2]
    return ArcDimension(
        edge_indices=tuple(edge_indices),
        center=circle.center,
        radius=circle.radius,
        point_on_arc=point_on_arc,
        sweep_degrees=sweep_degrees,
        max_error=circle.max_error,
    )


def detect_arc_dimensions(
    ring: Sequence[Point],
    maximum_segment_length: float = 1.0,
    tolerance: float = 0.03,
    minimum_segments: int = 3,
    minimum_sweep_degrees: float = 10.0,
) -> List[ArcDimension]:
    """Agrupa cadenas cortas que siguen una misma circunferencia.

    Se requieren al menos tres segmentos consecutivos, todos estrictamente más
    cortos que el límite, un giro continuo en el mismo sentido y un error radial
    inferior a la tolerancia. Los demás lados se conservan como cotas lineales.
    """
    points = open_ring(ring)
    if maximum_segment_length <= 0 or tolerance <= 0:
        raise ValueError("Los límites de detección de arcos deben ser positivos")
    if minimum_segments < 3:
        raise ValueError("Se requieren al menos tres segmentos para reconocer un arco")
    if len(points) < minimum_segments + 1:
        return []

    size = len(points)
    lengths = [
        hypot(
            points[(index + 1) % size][0] - points[index][0],
            points[(index + 1) % size][1] - points[index][1],
        )
        for index in range(size)
    ]
    is_short = [0.0 < length < maximum_segment_length for length in lengths]
    if not any(is_short):
        return []

    if all(is_short):
        complete = _fit_arc_candidate(
            points,
            tuple(range(size)),
            tolerance,
            minimum_sweep_degrees,
        )
        if complete is not None:
            return [complete]
        runs = [list(range(size))]
    else:
        break_index = next(index for index, short in enumerate(is_short) if not short)
        runs = []
        current = []
        for step in range(1, size + 1):
            index = (break_index + step) % size
            if is_short[index]:
                current.append(index)
            elif current:
                runs.append(current)
                current = []
        if current:
            runs.append(current)

    result = []
    for run in runs:
        start = 0
        while start + minimum_segments <= len(run):
            best = None
            best_end = None
            for end in range(start + minimum_segments, len(run) + 1):
                candidate = _fit_arc_candidate(
                    points,
                    run[start:end],
                    tolerance,
                    minimum_sweep_degrees,
                )
                if candidate is not None:
                    best = candidate
                    best_end = end
            if best is None:
                start += 1
            else:
                result.append(best)
                start = best_end
    return result


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
    probe_distance = max(
        min(max(offset, reference_extension) * 0.1, length * 0.1),
        1.0e-6,
    )
    probe_a = _point_plus(midpoint, normal_a, probe_distance)
    normal_b = (-normal_a[0], -normal_a[1])
    probe_b = _point_plus(midpoint, normal_b, probe_distance)

    inside_a = is_inside(probe_a)
    inside_b = is_inside(probe_b)
    if inside_a != inside_b:
        normal = normal_b if inside_a else normal_a
    else:
        to_centroid = (centroid[0] - midpoint[0], centroid[1] - midpoint[1])
        dot_product = (
            normal_a[0] * to_centroid[0] + normal_a[1] * to_centroid[1]
        )
        normal = normal_a if dot_product < 0 else normal_b

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
