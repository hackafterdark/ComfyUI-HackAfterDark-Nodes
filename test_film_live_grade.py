# Copyright 2026 HackAfterDark
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import torch
import os
import tempfile
from film_live_grade import (
    HackAfterDarkLiveGrade,
    tensor_rgb_to_hsv,
    tensor_hsv_to_rgb
)


class TestFilmLiveGrade(unittest.TestCase):
    def setUp(self):
        self.node = HackAfterDarkLiveGrade()
        self.test_img = torch.rand((1, 64, 64, 3), dtype=torch.float32)

    def test_rgb_hsv_conversion_identity(self):
        # Test converting RGB to HSV and back to RGB
        rgb_orig = torch.tensor([
            [[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
             [[0.5, 0.5, 0.5], [0.2, 0.8, 0.4], [0.9, 0.1, 0.7]]]
        ], dtype=torch.float32)

        hsv = tensor_rgb_to_hsv(rgb_orig)
        rgb_reconstructed = tensor_hsv_to_rgb(hsv)

        self.assertTrue(torch.allclose(rgb_orig, rgb_reconstructed, atol=1e-4))

    def test_input_types(self):
        input_types = HackAfterDarkLiveGrade.INPUT_TYPES()
        self.assertIn("required", input_types)
        req = input_types["required"]
        self.assertIn("image", req)
        self.assertIn("lut_file", req)
        self.assertIn("lut_strength", req)
        self.assertIn("exposure", req)
        self.assertIn("contrast", req)
        self.assertIn("black_lift", req)
        self.assertIn("hue", req)
        self.assertIn("saturation", req)
        self.assertIn("tint_green_magenta", req)
        self.assertIn("tint_amber_blue", req)
        self.assertIn("micro_contrast", req)

    def test_tonality_exposure(self):
        # Exposure +1 EV should double RGB values prior to clipping
        img = torch.full((1, 16, 16, 3), 0.25, dtype=torch.float32)
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            exposure=1.0,
            enable_preview=False,
            clip_output=True
        )
        out_img = res["result"][0]
        self.assertTrue(torch.allclose(out_img, torch.full_like(out_img, 0.5), atol=1e-4))

    def test_tonality_contrast(self):
        # Contrast adjustment centered at 0.5
        img = torch.full((1, 16, 16, 3), 0.6, dtype=torch.float32)
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            contrast=1.5,
            enable_preview=False,
            clip_output=True
        )
        out_img = res["result"][0]
        # (0.6 - 0.5) * 1.5 + 0.5 = 0.65
        self.assertTrue(torch.allclose(out_img, torch.full_like(out_img, 0.65), atol=1e-4))

    def test_black_lift(self):
        img = torch.zeros((1, 16, 16, 3), dtype=torch.float32)
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            black_lift=0.1,
            enable_preview=False,
            clip_output=True
        )
        out_img = res["result"][0]
        self.assertTrue(torch.allclose(out_img, torch.full_like(out_img, 0.1), atol=1e-4))

    def test_hue_shift(self):
        # Red pixel (H=0). Shifting hue by 120 degrees should make it Green (H=1/3)
        img = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
        img[..., 0] = 1.0  # Red
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            hue=120.0,
            enable_preview=False,
            clip_output=True
        )
        out_img = res["result"][0]
        self.assertAlmostEqual(out_img[0, 0, 0, 0].item(), 0.0, places=3)
        self.assertAlmostEqual(out_img[0, 0, 0, 1].item(), 1.0, places=3)
        self.assertAlmostEqual(out_img[0, 0, 0, 2].item(), 0.0, places=3)

    def test_tint_correction(self):
        img = torch.full((1, 4, 4, 3), 0.5, dtype=torch.float32)
        # Magenta tint (+0.5 tint_green_magenta) -> increases Red & Blue, decreases Green
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            tint_green_magenta=0.4,
            enable_preview=False,
            clip_output=True
        )
        out_img = res["result"][0]
        r = out_img[0, 0, 0, 0].item()
        g = out_img[0, 0, 0, 1].item()
        b = out_img[0, 0, 0, 2].item()
        self.assertGreater(r, 0.5)
        self.assertLess(g, 0.5)
        self.assertGreater(b, 0.5)

    def test_preview_payload(self):
        img = torch.rand((1, 32, 32, 3), dtype=torch.float32)
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            enable_preview=True
        )
        self.assertIn("ui", res)
        self.assertIn("livegrade_images", res["ui"])
        self.assertEqual(len(res["ui"]["livegrade_images"]), 1)
        self.assertEqual(res["ui"]["livegrade_images"][0]["type"], "temp")

    def test_split_toning(self):
        # Test applying shadow tint (Teal / Cyan) to dark pixels
        img = torch.full((1, 8, 8, 3), 0.1, dtype=torch.float32)
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            shadow_tint="Teal / Cyan",
            shadow_intensity=0.5,
            enable_preview=False
        )
        out_img = res["result"][0]
        self.assertLess(out_img[0, 0, 0, 0].item(), 0.1) # Red reduced
        self.assertGreater(out_img[0, 0, 0, 1].item(), 0.1) # Green boosted
        self.assertGreater(out_img[0, 0, 0, 2].item(), 0.1) # Blue boosted

    def test_micro_contrast(self):
        # Test applying micro_contrast high-pass sharpening to textured image
        img = torch.zeros((1, 16, 16, 3), dtype=torch.float32)
        img[..., 7:9, 7:9, :] = 1.0 # High contrast center dot
        res = self.node.apply_live_grade(
            image=img,
            lut_file="None",
            micro_contrast=0.5,
            enable_preview=False
        )
        out_img = res["result"][0]
        self.assertEqual(out_img.shape, img.shape)

    def test_lut_application_with_cube(self):
        # Create a simple 2x2x2 identity cube LUT
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cube", delete=False) as tmp:
            tmp.write("TITLE \"Identity LUT\"\n")
            tmp.write("LUT_3D_SIZE 2\n")
            tmp.write("0.0 0.0 0.0\n")
            tmp.write("1.0 0.0 0.0\n")
            tmp.write("0.0 1.0 0.0\n")
            tmp.write("1.0 1.0 0.0\n")
            tmp.write("0.0 0.0 1.0\n")
            tmp.write("1.0 0.0 1.0\n")
            tmp.write("0.0 1.0 1.0\n")
            tmp.write("1.0 1.0 1.0\n")
            tmp_path = tmp.name

        try:
            img = torch.rand((1, 8, 8, 3), dtype=torch.float32)
            res = self.node.apply_live_grade(
                image=img,
                lut_file=tmp_path,
                strength=1.0,
                enable_preview=False
            )
            out_img = res["result"][0]
            self.assertEqual(out_img.shape, img.shape)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()

