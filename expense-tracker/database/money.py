"""Helpers for converting between rupees (what people type and read)
and paise (the whole numbers we store in the database).

We never use float for money: 0.1 + 0.2 isn't exactly 0.3 in floats.
Decimal does exact decimal maths instead.
"""

from decimal import Decimal, InvalidOperation

from database.db import MSG_AMOUNT, ValidationError


def rupees_to_paise(value):
    """Turn a rupee amount like "123.45", "1,250" or 99 into paise (12345).

    Commas and spaces are ignored. Raises ValidationError if the value
    isn't a positive amount with at most 2 decimal places.
    """
    if isinstance(value, bool) or value is None:
        raise ValidationError(MSG_AMOUNT)

    if isinstance(value, str):
        text = "".join(value.split()).replace(",", "")
        if not text:
            raise ValidationError(MSG_AMOUNT)
    elif isinstance(value, float):
        # str() first, so 0.1 becomes "0.1" rather than 0.1000000000000000055...
        text = str(value)
    elif isinstance(value, (int, Decimal)):
        text = value
    else:
        raise ValidationError(MSG_AMOUNT)

    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValidationError(MSG_AMOUNT) from None

    if not amount.is_finite() or amount <= 0:
        raise ValidationError(MSG_AMOUNT)
    if amount.as_tuple().exponent < -2:  # more than 2 decimal places
        raise ValidationError(MSG_AMOUNT)

    return int(amount * 100)


def paise_to_rupees(paise):
    """Format paise for display with Indian digit grouping.

    12345 -> "₹123.45", 1245000 -> "₹12,450.00", 10000000 -> "₹1,00,000.00"
    """
    sign = "-" if paise < 0 else ""
    rupees, remainder = divmod(abs(paise), 100)
    digits = str(rupees)

    # Indian grouping: the last 3 digits, then groups of 2 (1,00,000).
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])

    return f"{sign}₹{digits}.{remainder:02d}"
