"""Tests for the rupee/paise helpers in database/money.py."""

from decimal import Decimal

import pytest

from database.db import ValidationError
from database.money import paise_to_rupees, rupees_to_paise


@pytest.mark.parametrize(
    "value, expected",
    [
        ("123.45", 12345),
        ("1,250", 125000),
        ("1,00,000.50", 10000050),
        (" 5 ", 500),
        ("0.01", 1),
        ("10.5", 1050),
        (99, 9900),
        (0.1, 10),
        (Decimal("2.25"), 225),
    ],
)
def test_rupees_to_paise_valid(value, expected):
    assert rupees_to_paise(value) == expected


@pytest.mark.parametrize(
    "value",
    ["abc", "0", "-5", "1.234", "", "   ", "nan", "inf", "12..5", None, True, False, [1]],
)
def test_rupees_to_paise_invalid(value):
    with pytest.raises(ValidationError):
        rupees_to_paise(value)


@pytest.mark.parametrize(
    "paise, expected",
    [
        (0, "₹0.00"),
        (5, "₹0.05"),
        (12345, "₹123.45"),
        (99900, "₹999.00"),
        (100000, "₹1,000.00"),
        (1245000, "₹12,450.00"),
        (10000000, "₹1,00,000.00"),
        (100000000, "₹10,00,000.00"),
        (1234567890, "₹1,23,45,678.90"),
        (-12345, "-₹123.45"),
    ],
)
def test_paise_to_rupees(paise, expected):
    assert paise_to_rupees(paise) == expected
