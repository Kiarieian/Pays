"""Unit tests for phone normalization."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.daraja import normalize_phone


class TestNormalizePhone:
    def test_07XXXXXXXX_format(self):
        assert normalize_phone("0712345678") == "254712345678"

    def test_07XXXXXXXX_with_plus(self):
        assert normalize_phone("+254712345678") == "254712345678"

    def test_07XXXXXXXX_with_spaces(self):
        assert normalize_phone("071 234 5678") == "254712345678"

    def test_2547XXXXXXXX_format(self):
        assert normalize_phone("254712345678") == "254712345678"

    def test_2541XXXXXXXX_format(self):
        assert normalize_phone("254112345678") == "254112345678"

    def test_7XXXXXXXX_format(self):
        assert normalize_phone("712345678") == "254712345678"

    def test_1XXXXXXXX_format(self):
        assert normalize_phone("112345678") == "254112345678"

    def test_invalid_too_short(self):
        with pytest.raises(ValueError, match="Invalid phone number"):
            normalize_phone("0712345")

    def test_invalid_no_country(self):
        with pytest.raises(ValueError, match="Invalid phone number"):
            normalize_phone("912345678")

    def test_invalid_letters(self):
        with pytest.raises(ValueError, match="Invalid phone number"):
            normalize_phone("071234abcd")
