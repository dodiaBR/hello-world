import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from huelayer.cli import main, swap_instructions
from huelayer.filament import Filament, auto_stack, load_library, resolve
from huelayer.heightmap import PrintSettings, heights_from_counts, layer_counts
from huelayer.optimize import (
    PixelStats, choose_filaments, optimize_swaps, srgb_to_lab, stack_error, stack_from_layers,
)
from huelayer.simulate import TRANSMISSION_AT_TD, layer_opacity, render
from huelayer.stl import heightmap_triangles

BLACK = Filament("Preto", (0, 0, 0), 0.6)
WHITE = Filament("Branco", (1, 1, 1), 2.0)
RED = Filament("Vermelho", (1, 0, 0), 1.5)


class FilamentTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(Filament.parse("Branco:#FFFFFF:2.5"), Filament("Branco", (1, 1, 1), 2.5))

    def test_parse_rejects_garbage(self):
        with self.assertRaises(ValueError):
            Filament.parse("Branco")

    def test_auto_stack_orders_dark_to_light(self):
        stack = auto_stack([WHITE, BLACK, RED], 0.5, 2.0)
        self.assertEqual([s.filament for s in stack], [BLACK, RED, WHITE])
        self.assertEqual([s.start_z for s in stack], [0.0, 1.0, 1.5])


    def test_resolve_by_name_or_spec(self):
        library = load_library()
        self.assertEqual(resolve("branco", library).name, "Branco")
        self.assertEqual(resolve("X:#000000:1", library), Filament("X", (0, 0, 0), 1.0))
        with self.assertRaises(ValueError):
            resolve("Roxo Neon", library)


class HeightmapTest(unittest.TestCase):
    settings = PrintSettings(first_layer=0.2, layer_height=0.1, base_height=0.4, max_height=1.0)

    def test_dark_is_base_and_light_is_max(self):
        heights = heights_from_counts(layer_counts(np.array([0.0, 1.0]), self.settings), self.settings)
        np.testing.assert_allclose(heights, [0.4, 1.0])

    def test_invert(self):
        settings = PrintSettings(**{**self.settings.__dict__, "invert": True})
        heights = heights_from_counts(layer_counts(np.array([0.0, 1.0]), settings), settings)
        np.testing.assert_allclose(heights, [1.0, 0.4])

    def test_gamma_gives_more_height_range_to_light_tones(self):
        settings = PrintSettings(**{**self.settings.__dict__, "gamma": 2.0, "max_height": 0.8})
        heights = heights_from_counts(layer_counts(np.array([0.0, 0.5, 1.0]), settings), settings)
        np.testing.assert_allclose(heights, [0.4, 0.5, 0.8])  # sem gamma, 0.5 daria 0.6

    def test_layer_index_starts_after_swap_height(self):
        self.assertEqual(self.settings.layer_index(0.0), 0)
        self.assertEqual(self.settings.layer_index(0.2), 1)
        self.assertEqual(self.settings.layer_index(0.25), 1)
        self.assertEqual(self.settings.layer_index(0.3), 2)


class SimulateTest(unittest.TestCase):
    def test_thin_layers_compose_like_one_thick_layer(self):
        thin = 1 - (1 - layer_opacity(0.1, 1.0)) ** 10
        self.assertAlmostEqual(thin, layer_opacity(1.0, 1.0))
        self.assertAlmostEqual(layer_opacity(1.0, 1.0), 1 - TRANSMISSION_AT_TD)

    def test_more_white_layers_get_brighter(self):
        settings = PrintSettings(first_layer=0.1, layer_height=0.1)
        stack = auto_stack([BLACK, WHITE], 0.1, 0.1)  # branco a partir da 2ª camada
        image = render(np.array([[1, 5, 30]]), stack, settings)
        self.assertEqual(image[0, 0].tolist(), [0, 0, 0])
        self.assertTrue(0 < image[0, 1, 0] < image[0, 2, 0] < 1)


class OptimizeTest(unittest.TestCase):
    settings = PrintSettings(first_layer=0.1, layer_height=0.1, base_height=0.1, max_height=2.0)

    def test_lab_reference_points(self):
        np.testing.assert_allclose(srgb_to_lab(np.array([1.0, 1.0, 1.0])), [100, 0, 0], atol=0.05)
        np.testing.assert_allclose(srgb_to_lab(np.array([0.0, 0.0, 0.0])), [0, 0, 0], atol=1e-9)

    def test_grouped_error_matches_per_pixel_error(self):
        rng = np.random.default_rng(1)
        counts = rng.integers(1, 15, (6, 7))
        target = rng.random((6, 7, 3))
        stack = stack_from_layers([BLACK, RED, WHITE], [4, 9], self.settings)
        brute = ((srgb_to_lab(render(counts, stack, self.settings)) - srgb_to_lab(target)) ** 2).sum(-1).mean()
        self.assertAlmostEqual(stack_error(stack, PixelStats.from_image(counts, target), self.settings), brute)

    def test_optimize_recovers_the_stack_that_made_the_image(self):
        counts = np.tile(np.arange(1, 21), (3, 1))
        truth = stack_from_layers([BLACK, RED, WHITE], [5, 13], self.settings)
        stats = PixelStats.from_image(counts, render(counts, truth, self.settings))
        stack, error = optimize_swaps([BLACK, RED, WHITE], stats, self.settings)
        self.assertAlmostEqual(error, 0, places=6)
        self.assertEqual([s.start_z for s in stack], [s.start_z for s in truth])

    def test_choose_filaments_picks_the_colors_in_the_image(self):
        library = load_library()
        by_name = {f.name: f for f in library}
        counts = np.tile(np.arange(1, 21), (3, 1))
        truth = stack_from_layers([by_name["Preto"], by_name["Verde"], by_name["Amarelo"]], [6, 14], self.settings)
        stats = PixelStats.from_image(counts, render(counts, truth, self.settings))
        stack, _ = choose_filaments(library, 3, stats, self.settings, required=[by_name["Preto"]])
        self.assertEqual([s.filament.name for s in stack], ["Preto", "Verde", "Amarelo"])

    def test_rejects_more_filaments_than_layers(self):
        stats = PixelStats.from_image(np.array([[1, 2]]), np.zeros((1, 2, 3)))
        with self.assertRaises(ValueError):
            optimize_swaps([BLACK, RED, WHITE], stats, self.settings)


class StlTest(unittest.TestCase):
    def test_mesh_is_watertight_with_outward_normals(self):
        heights = np.array([[1.0, 2.0, 1.5], [0.5, 1.0, 3.0]])
        triangles = heightmap_triangles(heights, 0.5)

        edges = Counter()
        for triangle in triangles.round(6):
            points = [tuple(p) for p in triangle]
            for a, b in zip(points, points[1:] + points[:1]):
                edges[(a, b)] += 1
        # Fechado e orientado: cada aresta dirigida aparece uma vez, e sua inversa também.
        self.assertTrue(all(count == 1 and edges[(b, a)] == 1 for (a, b), count in edges.items()))

        # Volume com sinal positivo (normais para fora) e igual ao volume do relevo.
        v0, v1, v2 = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        volume = np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6
        expected = sum(
            heights[r : r + 2, c : c + 2].mean() * 0.25 for r in range(1) for c in range(2)
        )
        self.assertGreater(volume, 0)
        # Cada quad é dividido em 2 triângulos, então o volume não é exatamente a média dos 4 cantos.
        self.assertAlmostEqual(volume, expected, delta=0.1)


class CliTest(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            gradient = np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (32, 1))
            image = Path(directory, "gradiente.png")
            Image.fromarray(np.stack([gradient] * 3, -1)).save(image)
            prefix = Path(directory, "out", "peca")

            main([str(image), "-f", "Preto:#000000:0.6", "-f", "Branco:#FFFFFF:2.0",
                  "--width-mm", "20", "--resolution-mm", "0.5", "-o", str(prefix)])

            with Image.open(f"{prefix}_preview.png") as preview:
                self.assertEqual(preview.size, (40, 20))
            stl = Path(f"{prefix}.stl").read_bytes()
            triangle_count = int.from_bytes(stl[80:84], "little")
            self.assertEqual(len(stl), 84 + 50 * triangle_count)
            self.assertIn("troque para Branco", Path(f"{prefix}_trocas.txt").read_text())

    def test_end_to_end_auto(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory, "laranja.png")
            ramp = np.linspace(0, 1, 64)[None, :, None] * np.array([1.0, 0.5, 0.1])
            Image.fromarray((np.tile(ramp, (16, 1, 1)) * 255).astype(np.uint8)).save(image)
            prefix = Path(directory, "peca")
            main([str(image), "--auto", "3", "-f", "Preto", "--width-mm", "20",
                  "--resolution-mm", "0.5", "-o", str(prefix)])
            instructions = Path(f"{prefix}_trocas.txt").read_text()
            self.assertTrue(instructions.startswith("Comece com: Preto"))
            self.assertEqual(instructions.count("troque para"), 2)

    def test_swap_above_top_is_reported(self):
        settings = PrintSettings()
        stack = auto_stack([BLACK, WHITE], 0.48, 10.0)
        self.assertIn("ignorado", swap_instructions(stack, settings, total_layers=5))


if __name__ == "__main__":
    unittest.main()
