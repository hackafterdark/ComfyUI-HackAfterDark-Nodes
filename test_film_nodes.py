import unittest
import torch
from film_optics_artifacts import AfterDarkFilmOpticsArtifacts
from film_halation import AfterDarkFilmHalation
from film_color_split import AfterDarkFilmColorSplit

class TestNewFilmNodes(unittest.TestCase):
    def setUp(self):
        self.input_image = torch.full((1, 64, 64, 3), 0.5, dtype=torch.float32)

    def test_optics_artifacts_light_leak(self):
        node = AfterDarkFilmOpticsArtifacts()
        (out,) = node.apply_artifacts(
            self.input_image,
            light_leak_style="C-41 Orange Flare",
            leak_location="Top Right Corner",
            leak_intensity=0.40,
            vignette_amount=0.20,
            vignette_falloff=1.5,
            gate_border=0.05,
            seed=42
        )
        self.assertEqual(out.shape, self.input_image.shape)
        self.assertTrue((out >= 0.0).all() and (out <= 1.0).all())

    def test_optics_seed_variations(self):
        node = AfterDarkFilmOpticsArtifacts()
        (out1,) = node.apply_artifacts(self.input_image, light_leak_style="Rainbow Prism Flare", leak_location="Random / Scattered", seed=101)
        (out2,) = node.apply_artifacts(self.input_image, light_leak_style="Rainbow Prism Flare", leak_location="Random / Scattered", seed=202)
        # Verify that changing seed produces different spatial patterns
        self.assertFalse(torch.allclose(out1, out2))

    def test_film_halation(self):
        node = AfterDarkFilmHalation()
        # Create image with bright specular highlight in center
        img = self.input_image.clone()
        img[0, 30:34, 30:34, :] = 0.95

        (out,) = node.apply_halation(
            img,
            halation_intensity=0.50,
            threshold=0.80,
            bloom_radius=4.0,
            halation_tint="Red / Orange (CineStill 800T)"
        )
        self.assertEqual(out.shape, self.input_image.shape)
        self.assertTrue((out >= 0.0).all() and (out <= 1.0).all())

    def test_film_color_split(self):
        node = AfterDarkFilmColorSplit()
        (out,) = node.apply_color_split(
            self.input_image,
            shadow_tint="Teal / Cyan",
            shadow_intensity=0.25,
            highlight_tint="Golden Amber",
            highlight_intensity=0.25,
            balance=0.0,
            micro_contrast=0.20
        )
        self.assertEqual(out.shape, self.input_image.shape)
        self.assertTrue((out >= 0.0).all() and (out <= 1.0).all())

if __name__ == "__main__":
    unittest.main()
