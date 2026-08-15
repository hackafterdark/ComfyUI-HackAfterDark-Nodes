import unittest
import torch
from stochastic_noise import AfterDarkStochasticNoise, FILM_PRESETS

class TestAfterDarkFilmGrainNode(unittest.TestCase):
    def setUp(self):
        self.node = AfterDarkStochasticNoise()
        # Create a dummy image tensor [Batch=1, Height=64, Width=64, Channels=3]
        self.input_image = torch.full((1, 64, 64, 3), 0.5, dtype=torch.float32)
        self.default_format = "35mm (24x36 - Standard Grain)"

    def test_zero_bypass(self):
        (out,) = self.node.apply_noise(
            self.input_image,
            film_preset="None (Manual)",
            film_format=self.default_format,
            noise_level=0.0,
            grain_size=1.0,
            noise_type="gaussian",
            channel_mode="monochromatic",
            micro_jitter=0.0,
            chromatic_aberration=0.0,
            luminance_weight=False,
            seed=0
        )
        self.assertTrue(torch.equal(out, self.input_image))

    def test_noise_types(self):
        noise_types = ["gaussian", "poisson", "multiplicative", "laplacian"]
        for nt in noise_types:
            (out,) = self.node.apply_noise(
                self.input_image,
                film_preset="None (Manual)",
                film_format=self.default_format,
                noise_level=0.03,
                noise_type=nt,
                seed=42
            )
            self.assertEqual(out.shape, self.input_image.shape)
            self.assertTrue((out >= 0.0).all() and (out <= 1.0).all())

    def test_film_presets(self):
        for preset_name in FILM_PRESETS.keys():
            (out,) = self.node.apply_noise(
                self.input_image,
                film_preset=preset_name,
                film_format=self.default_format,
                noise_level=0.025,
                seed=42
            )
            self.assertEqual(out.shape, self.input_image.shape)
            self.assertTrue((out >= 0.0).all() and (out <= 1.0).all())

    def test_seed_reproducibility(self):
        (out1,) = self.node.apply_noise(
            self.input_image,
            film_preset="Kodak Tri-X 400 (B&W Silver Halide)",
            film_format=self.default_format,
            noise_level=0.02,
            seed=42
        )
        (out2,) = self.node.apply_noise(
            self.input_image,
            film_preset="Kodak Tri-X 400 (B&W Silver Halide)",
            film_format=self.default_format,
            noise_level=0.02,
            seed=42
        )
        (out3,) = self.node.apply_noise(
            self.input_image,
            film_preset="Kodak Tri-X 400 (B&W Silver Halide)",
            film_format=self.default_format,
            noise_level=0.02,
            seed=999
        )
        self.assertTrue(torch.equal(out1, out2))
        self.assertFalse(torch.equal(out1, out3))

if __name__ == "__main__":
    unittest.main()
