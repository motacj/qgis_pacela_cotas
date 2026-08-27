import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from qgis_pacela_cotas.core import (
    dimension_for_edge,
    map_height_from_points,
    open_ring,
    outside_label_point,
    spanish_number,
)


class CoreTests(unittest.TestCase):
    def test_text_height_at_scale_500(self):
        self.assertAlmostEqual(map_height_from_points(8.0, 500.0), 1.4111111111, places=8)

    def test_open_ring_removes_closing_vertex(self):
        self.assertEqual(open_ring([(0, 0), (1, 0), (1, 1), (0, 0)]), [(0, 0), (1, 0), (1, 1)])

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
            math.dist(result.tick_start[0], result.tick_start[1]), 0.5, places=8
        )

    def test_spanish_number(self):
        self.assertEqual(spanish_number(1514.13, 2), "1.514,13")

    def test_vertex_label_is_outside_and_at_requested_distance(self):
        def inside(point):
            return 0 < point[0] < 10 and 0 < point[1] < 5

        label = outside_label_point((10, 5), 2.0, inside, (5, 2.5))
        self.assertFalse(inside(label))
        self.assertAlmostEqual(math.dist((10, 5), label), 2.0, places=8)


if __name__ == "__main__":
    unittest.main()
