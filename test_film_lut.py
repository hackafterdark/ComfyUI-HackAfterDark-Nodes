import os
import unittest
import tempfile
import torch
from film_lut import AfterDarkFilmLUT, load_cube_lut

class TestAfterDarkFilmLUTNode(unittest.TestCase):
    def setUp(self):
        self.node = AfterDarkFilmLUT()
        self.input_image = torch.full((1, 32, 32, 3), 0.5, dtype=torch.float32)
        
        # Create a temporary .cube LUT file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cube_path = os.path.join(self.temp_dir.name, "identity.cube")
        
        cube_content = """# Identity LUT
TITLE "Identity"
LUT_3D_SIZE 2

0.0 0.0 0.0
1.0 0.0 0.0
0.0 1.0 0.0
1.0 1.0 0.0
0.0 0.0 1.0
1.0 0.0 1.0
0.0 1.0 1.0
1.0 1.0 1.0
"""
        with open(self.cube_path, "w") as f:
            f.write(cube_content)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_cube_lut(self):
        lut_tensor = load_cube_lut(self.cube_path)
        self.assertEqual(lut_tensor.shape, (1, 3, 2, 2, 2))

    def test_get_lut_files(self):
        lut_files = AfterDarkFilmLUT.get_lut_files()
        self.assertIsInstance(lut_files, list)

    def test_apply_lut_identity(self):
        (out,) = self.node.apply_lut(
            self.input_image,
            lut_file=self.cube_path,
            strength=1.0,
            contrast=1.0,
            black_lift=0.0,
            color_space="sRGB (Standard)",
            clip_output=True
        )
        self.assertEqual(out.shape, self.input_image.shape)
        self.assertTrue(torch.allclose(out, self.input_image, atol=0.05))

    def test_contrast_and_black_lift(self):
        (out,) = self.node.apply_lut(
            self.input_image,
            lut_file="None",
            strength=0.0,
            contrast=1.05,
            black_lift=0.02,
            clip_output=True
        )
        self.assertEqual(out.shape, self.input_image.shape)
        self.assertTrue((out >= 0.0).all() and (out <= 1.0).all())

    def test_strength_blend(self):
        (out_zero,) = self.node.apply_lut(
            self.input_image,
            lut_file=self.cube_path,
            strength=0.0,
            contrast=1.0,
            black_lift=0.0
        )
        self.assertTrue(torch.equal(out_zero, self.input_image))

if __name__ == "__main__":
    unittest.main()
