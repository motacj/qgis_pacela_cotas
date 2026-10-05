"""Pruebas unitarias de los cálculos geométricos independientes de QGIS."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

# GitHub Actions ejecuta las pruebas desde la raíz del repositorio. Añadimos
# su carpeta padre para que el directorio del repositorio pueda importarse
# como el paquete ``qgis_pacela_cotas`` tanto en CI como en local.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from qgis_pacela_cotas.core import (
    detect_arc_dimensions,
    dimension_for_edge,
    fit_circle,
    map_height_from_points,
    open_ring,
    outside_label_point,
    spanish_number,
)


class CircleFitTest(unittest.TestCase):
    def test_fits_large_utm_coordinates(self):
        center = (440000.0, 4470000.0)
        radius = 8.0
        points = [
            (
                center[0] + radius * math.cos(math.radians(angle)),
                center[1] + radius * math.sin(math.radians(angle)),
            )
            for angle in range(0, 91, 15)
        ]

        fit = fit_circle(points)

        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit.center[0], center[0], places=6)
        self.assertAlmostEqual(fit.center[1], center[1], places=6)
        self.assertAlmostEqual(fit.radius, radius, places=6)
        self.assertLess(fit.max_error, 1.0e-7)


class ArcDetectionTest(unittest.TestCase):
    @staticmethod
    def _arc_points(center, radius, start, end, step):
        return [
            (
                center[0] + radius * math.cos(math.radians(angle)),
                center[1] + radius * math.sin(math.radians(angle)),
            )
            for angle in range(start, end + 1, step)
        ]

    def test_groups_short_segments_into_one_radius(self):
        arc = self._arc_points((10.0, 10.0), 5.0, 0, 60, 10)
        ring = [(0.0, 0.0), arc[0], *arc[1:], (0.0, 20.0)]

        detected = detect_arc_dimensions(ring, 1.0, 0.01)

        self.assertEqual(len(detected), 1)
        self.assertEqual(len(detected[0].edge_indices), 6)
        self.assertAlmostEqual(detected[0].radius, 5.0, places=6)
        self.assertAlmostEqual(detected[0].sweep_degrees, 60.0, places=6)

    def test_does_not_treat_short_straight_segments_as_arc(self):
        ring = [
            (0.0, 0.0),
            (0.5, 0.0),
            (1.0, 0.0),
            (1.5, 0.0),
            (2.0, 0.0),
            (2.0, 3.0),
            (0.0, 3.0),
        ]

        self.assertEqual(detect_arc_dimensions(ring, 1.0, 0.03), [])

    def test_rejects_an_arc_when_segments_reach_the_limit(self):
        arc = self._arc_points((0.0, 0.0), 10.0, 0, 60, 10)

        self.assertEqual(detect_arc_dimensions(arc, 1.0, 0.03), [])

    def test_detects_a_complete_segmentized_circle(self):
        ring = self._arc_points((5.0, 7.0), 3.0, 0, 350, 10)

        detected = detect_arc_dimensions(ring, 1.0, 0.01)

        self.assertEqual(len(detected), 1)
        self.assertEqual(len(detected[0].edge_indices), 36)
        self.assertAlmostEqual(detected[0].radius, 3.0, places=6)
        self.assertAlmostEqual(detected[0].sweep_degrees, 360.0, places=6)

    def test_detects_an_arc_that_crosses_the_ring_start(self):
        arc = self._arc_points((10.0, 10.0), 5.0, 0, 60, 10)
        ring = [*arc[3:], (0.0, 20.0), (0.0, 0.0), *arc[:3]]

        detected = detect_arc_dimensions(ring, 1.0, 0.01)

        self.assertEqual(len(detected), 1)
        self.assertEqual(len(detected[0].edge_indices), 6)
        self.assertIn(0, detected[0].edge_indices)
        self.assertIn(len(ring) - 1, detected[0].edge_indices)


class ExistingCalculationsTest(unittest.TestCase):
    def test_text_height_and_spanish_number(self):
        self.assertAlmostEqual(map_height_from_points(8.0, 500.0), 1.4111111111)
        self.assertEqual(spanish_number(1234.5, 2), "1.234,50")

    def test_open_ring_removes_closing_vertex(self):
        self.assertEqual(
            open_ring([(0, 0), (1, 0), (1, 1), (0, 0)]),
            [(0, 0), (1, 0), (1, 1)],
        )

    def test_dimension_is_outside_rectangle(self):
        def inside(point):
            return 0 < point[0] < 10 and 0 < point[1] < 5

        result = dimension_for_edge(
            (0, 0),
            (10, 0),
            offset=2,
            reference_extension=1,
            tick_length=0.5,
            is_inside=inside,
            centroid=(5, 2.5),
        )

        self.assertEqual(result.dimension, ((0.0, -2.0), (10.0, -2.0)))
        self.assertAlmostEqual(result.length, 10.0)
        self.assertAlmostEqual(
            math.dist(result.tick_start[0], result.tick_start[1]),
            0.5,
            places=8,
        )

    def test_vertex_label_is_outside_and_at_requested_distance(self):
        def inside(point):
            return 0 < point[0] < 10 and 0 < point[1] < 5

        label = outside_label_point((10, 5), 2.0, inside, (5, 2.5))

        self.assertFalse(inside(label))
        self.assertAlmostEqual(math.dist((10, 5), label), 2.0, places=8)


if __name__ == "__main__":
    unittest.main()
