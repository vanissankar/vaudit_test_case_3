import os
import unittest

from engine.parser import clean_amount, is_date, extract_date, parse_date_obj
from main import get_ay_range, validate_and_process_pdf

class TestEngineRefinements(unittest.TestCase):
    def test_get_ay_range_valid(self):
        start, end = get_ay_range("2024-25")
        self.assertEqual(start.year, 2024)
        self.assertEqual(start.month, 4)
        self.assertEqual(end.year, 2025)
        self.assertEqual(end.month, 3)

    def test_get_ay_range_invalid(self):
        with self.assertRaises(ValueError):
            get_ay_range("24-25")

    def test_clean_amount_variants(self):
        self.assertAlmostEqual(clean_amount("1,234.50"), 1234.5)
        self.assertAlmostEqual(clean_amount("(1,234.50)"), 1234.5)
        self.assertAlmostEqual(clean_amount("1234"), 1234.0)
        self.assertEqual(clean_amount("abc"), 0.0)

    def test_is_date_matches(self):
        self.assertTrue(is_date("15/04/2024"))
        self.assertTrue(is_date("1st Jan 25"))
        self.assertFalse(is_date("not a date"))

    def test_extract_date_fallback(self):
        self.assertEqual(extract_date("Payment 10th April 2025 details"), "10th April 2025")

    def test_parse_date_obj_formats(self):
        self.assertEqual(parse_date_obj("31/12/2024").year, 2024)
        self.assertEqual(parse_date_obj("01-Jan-25").year, 2025)

    def test_validate_and_process_pdf_missing_file(self):
        err, meta, txns = validate_and_process_pdf("/tmp/does_not_exist_12345.pdf", (None, None))
        self.assertIsNotNone(err)
        self.assertEqual(err, "FILE_NOT_FOUND")
        self.assertIsNone(meta)
        self.assertEqual(txns, [])

if __name__ == "__main__":
    unittest.main()
