"""Тесты генерации картинок: PNG-кодер, холст, разбор промпта, рендер."""

import struct
import unittest
import zlib

from mybot.imaging.canvas import Canvas, mix
from mybot.imaging.font import text_width
from mybot.imaging.png import encode_png
from mybot.imaging.prompt import parse, seed_from_text, tokenize
from mybot.imaging.translit import transliterate
from mybot.imaging.generator import render_scene, generate


class TestPNG(unittest.TestCase):
    def test_signature_and_chunks(self):
        px = [[255, 0, 0, 0, 255, 0]]  # 2x1: красный, зелёный
        data = encode_png(px, 2, 1)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", data[:24])
        self.assertTrue(data.rstrip().endswith(struct.pack(">I", 0) + b"IEND"
                                               + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)))

    def test_ihdr_dimensions(self):
        data = encode_png([[0, 0, 0] * 4], 4, 1)
        # IHDR данные начинаются после 8 (подпись) + 4 (длина) + 4 (тег)
        w, h = struct.unpack(">II", data[16:24])
        self.assertEqual((w, h), (4, 1))

    def test_roundtrip_pixels(self):
        # раскодируем обратно вручную, чтобы убедиться в корректности
        px = [[10, 20, 30, 40, 50, 60], [70, 80, 90, 100, 110, 120]]
        data = encode_png(px, 2, 2)
        # выдёргиваем IDAT
        idx = data.index(b"IDAT")
        length = struct.unpack(">I", data[idx - 4:idx])[0]
        comp = data[idx + 4:idx + 4 + length]
        raw = zlib.decompress(comp)
        # первый байт каждой строки — фильтр 0
        self.assertEqual(raw[0], 0)
        self.assertEqual(list(raw[1:7]), px[0])
        self.assertEqual(raw[7], 0)
        self.assertEqual(list(raw[8:14]), px[1])


class TestCanvas(unittest.TestCase):
    def test_set_get_pixel(self):
        c = Canvas(4, 4, (0, 0, 0))
        c.set_pixel(1, 2, (10, 20, 30))
        self.assertEqual(c.get_pixel(1, 2), (10, 20, 30))

    def test_out_of_bounds_is_safe(self):
        c = Canvas(3, 3)
        c.set_pixel(-1, 0, (255, 255, 255))
        c.set_pixel(100, 100, (255, 255, 255))  # не должно падать

    def test_alpha_blend(self):
        c = Canvas(1, 1, (0, 0, 0))
        c.set_pixel(0, 0, (100, 100, 100), alpha=0.5)
        self.assertEqual(c.get_pixel(0, 0), (50, 50, 50))

    def test_gradient(self):
        c = Canvas(1, 3)
        c.vertical_gradient((0, 0, 0), (60, 60, 60))
        self.assertEqual(c.get_pixel(0, 0), (0, 0, 0))
        self.assertEqual(c.get_pixel(0, 2), (60, 60, 60))

    def test_mix(self):
        self.assertEqual(mix((0, 0, 0), (100, 200, 50), 0.5), (50, 100, 25))


class TestPrompt(unittest.TestCase):
    def test_tokenize(self):
        self.assertEqual(tokenize("Закат, над морем!"), ["закат", "над", "морем"])

    def test_seed_is_deterministic(self):
        self.assertEqual(seed_from_text("привет"), seed_from_text("Привет "))

    def test_palette_detection(self):
        self.assertEqual(parse("звёздная ночь").palette.name, "night")
        self.assertEqual(parse("закат у моря").palette.name, "sunset")
        self.assertEqual(parse("зимний лес").palette.name, "winter")

    def test_object_detection(self):
        s = parse("горы и море, лодка")
        self.assertIn("mountains", s.objects)
        self.assertIn("sea", s.objects)
        self.assertIn("boat", s.objects)

    def test_inflected_forms(self):
        self.assertIn("city", parse("прогулка по городу").objects)
        self.assertIn("sea", parse("плыву по морю").objects)

    def test_no_false_positive(self):
        # «горы» не должно включать «город»; «небо» — не «небоскрёбы»
        self.assertNotIn("city", parse("высокие горы").objects)
        self.assertNotIn("city", parse("голубое небо").objects)

    def test_english_prompt(self):
        s = parse("forest and mountains at night")
        self.assertEqual(s.palette.name, "night")
        self.assertIn("trees", s.objects)
        self.assertIn("mountains", s.objects)


class TestTranslit(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(transliterate("Закат"), "Zakat")
        self.assertEqual(transliterate("море"), "more")

    def test_keeps_latin_and_punct(self):
        self.assertEqual(transliterate("city 2024!"), "city 2024!")


class TestRender(unittest.TestCase):
    def test_render_returns_canvas_of_size(self):
        scene = parse("закат над горами")
        c = render_scene(scene, 128, 96)
        self.assertEqual((c.width, c.height), (128, 96))

    def test_same_prompt_same_image(self):
        a = render_scene(parse("ночь и луна"), 64, 64).to_png_bytes()
        b = render_scene(parse("ночь и луна"), 64, 64).to_png_bytes()
        self.assertEqual(a, b)

    def test_different_prompts_differ(self):
        a = render_scene(parse("солнечный день"), 64, 64).to_png_bytes()
        b = render_scene(parse("звёздная ночь"), 64, 64).to_png_bytes()
        self.assertNotEqual(a, b)

    def test_generate_writes_valid_png(self):
        import os
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "mybot_test_gen.png")
        scene = generate("море и горы на закате", path, 96, 72)
        self.assertTrue(os.path.getsize(path) > 100)
        with open(path, "rb") as f:
            self.assertTrue(f.read(8) == b"\x89PNG\r\n\x1a\n")
        self.assertIn("sea", scene.objects)


if __name__ == "__main__":
    unittest.main()
