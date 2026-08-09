import unittest
from film_ar_size_selector import FilmARSizeSelector

class TestFilmARSizeSelector(unittest.TestCase):
    def setUp(self):
        self.selector = FilmARSizeSelector()

    def test_default_presets(self):
        w, h = self.selector.get_size("1024x1024 (Square / MF 6x6)")
        self.assertEqual((w, h), (1024, 1024))

        w, h = self.selector.get_size("896x1120 (4:5 Instagram Portrait)")
        self.assertEqual((w, h), (896, 1120))

        w, h = self.selector.get_size("864x1152 (3:4 Classic Photograph Portrait)")
        self.assertEqual((w, h), (864, 1152))

        w, h = self.selector.get_size("1152x864 (4:3 Classic Photograph Landscape)")
        self.assertEqual((w, h), (1152, 864))

    def test_header_selection_fallback(self):
        w, h = self.selector.get_size("--- Portrait ---")
        self.assertEqual((w, h), (1024, 1024))

        w, h = self.selector.get_size("--- Landscape ---")
        self.assertEqual((w, h), (1152, 864))

    def test_custom_override(self):
        # Override both width and height
        w, h = self.selector.get_size("1024x1024 (Square / MF 6x6)", custom_width=1440, custom_height=2560)
        self.assertEqual((w, h), (1440, 2560))

        # Override width only
        w, h = self.selector.get_size("896x1120 (4:5 Instagram Portrait)", custom_width=720, custom_height=0)
        self.assertEqual((w, h), (720, 1120))

        # Override height only
        w, h = self.selector.get_size("896x1120 (4:5 Instagram Portrait)", custom_width=0, custom_height=1440)
        self.assertEqual((w, h), (896, 1440))

    def test_custom_preset_mode(self):
        # Selected Custom preset with numeric inputs
        w, h = self.selector.get_size("Custom (Manual Override)", custom_width=1200, custom_height=1600)
        self.assertEqual((w, h), (1200, 1600))

        # Selected Custom preset with zero inputs (fallback)
        w, h = self.selector.get_size("Custom (Manual Override)", custom_width=0, custom_height=0)
        self.assertEqual((w, h), (1024, 1024))

if __name__ == "__main__":
    unittest.main()
