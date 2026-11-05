"""Tests for the database layer in database/db.py.

Each test runs against its own empty temporary database (see conftest.py).
"""

from datetime import date, timedelta

import pytest

from database.db import (
    CATEGORIES,
    DuplicateEmailError,
    ValidationError,
    add_expense,
    create_user,
    delete_expense,
    get_db,
    get_expense,
    get_expenses,
    get_monthly_totals,
    get_recent_expenses,
    get_spending_by_category,
    get_spending_summary,
    get_total_spent,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
    verify_user,
)


def days_ago(n):
    """A 'YYYY-MM-DD' string for n days before today."""
    return (date.today() - timedelta(days=n)).isoformat()


def month_start(months_back):
    """The first day of the month `months_back` months before this one."""
    today = date.today()
    year, month = divmod(today.year * 12 + today.month - 1 - months_back, 12)
    return date(year, month + 1, 1)


def count_rows(table):
    return get_db().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ------------------------------------------------------------------ #
# Setup                                                               #
# ------------------------------------------------------------------ #

def test_init_db_creates_tables_and_index(app):
    names = {
        row["name"]
        for row in get_db().execute("SELECT name FROM sqlite_master").fetchall()
    }
    assert {"users", "expenses", "idx_expenses_user_date"} <= names


def test_init_db_twice_keeps_data(app, user):
    add_expense(user, 500, "Food", days_ago(1))
    init_db()
    init_db()
    assert count_rows("users") == 1
    assert count_rows("expenses") == 1


def test_foreign_keys_on_deleting_user_deletes_expenses(app, user):
    add_expense(user, 500, "Food", days_ago(1))
    db = get_db()
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    db.execute("DELETE FROM users WHERE id = ?", (user,))
    db.commit()
    assert count_rows("expenses") == 0


def test_seed_db_adds_demo_data_once(app):
    added = seed_db()
    assert added >= 20
    assert seed_db() == 0
    assert count_rows("users") == 1
    assert count_rows("expenses") == added

    demo = verify_user("demo@spendly.local", "demo1234")
    assert demo is not None
    assert demo["password_hash"] != "demo1234"

    expenses = get_expenses(demo["id"])
    assert {e["category"] for e in expenses} == set(CATEGORIES)
    oldest_allowed = (date.today() - timedelta(days=92)).isoformat()
    assert all(oldest_allowed <= e["expense_date"] <= days_ago(0) for e in expenses)


# ------------------------------------------------------------------ #
# Users                                                               #
# ------------------------------------------------------------------ #

def test_create_and_read_user(app):
    user_id = create_user("  Asha  ", "  Asha@Example.COM ", "secret123")
    by_id = get_user_by_id(user_id)
    assert by_id["name"] == "Asha"
    assert by_id["email"] == "asha@example.com"
    assert "password_hash" not in by_id.keys()

    for spelling in ("asha@example.com", "ASHA@EXAMPLE.COM", "Asha@Example.com"):
        assert get_user_by_email(spelling)["id"] == user_id


def test_unknown_user_returns_none(app):
    assert get_user_by_id(999) is None
    assert get_user_by_email("nobody@example.com") is None


def test_duplicate_email_any_case(app, user):
    with pytest.raises(DuplicateEmailError) as info:
        create_user("Someone", "TEST@example.com", "password999")
    assert str(info.value) == "An account with this email already exists."


def test_password_is_hashed(app, user):
    row = get_user_by_email("test@example.com")
    assert row["password_hash"] != "password123"
    assert "password123" not in row["password_hash"]
    assert len(row["password_hash"]) > 50


def test_verify_user(app, user):
    assert verify_user("test@example.com", "password123")["id"] == user
    assert verify_user("TEST@example.com", "password123")["id"] == user
    assert verify_user("test@example.com", "wrong-password") is None
    assert verify_user("nobody@example.com", "password123") is None
    assert verify_user(None, None) is None


@pytest.mark.parametrize(
    "name, email, password, message",
    [
        ("", "a@example.com", "password1", "Please enter your name (up to 100 characters)."),
        ("   ", "a@example.com", "password1", "Please enter your name (up to 100 characters)."),
        ("x" * 101, "a@example.com", "password1", "Please enter your name (up to 100 characters)."),
        ("Asha", "not-an-email", "password1", "Please enter a valid email address."),
        ("Asha", "a@b", "password1", "Please enter a valid email address."),
        ("Asha", "", "password1", "Please enter a valid email address."),
        ("Asha", "a@example.com", "short", "Password must be at least 8 characters."),
    ],
)
def test_create_user_rejects_bad_input(app, name, email, password, message):
    with pytest.raises(ValidationError) as info:
        create_user(name, email, password)
    assert str(info.value) == message
    assert count_rows("users") == 0


# ------------------------------------------------------------------ #
# Expenses                                                            #
# ------------------------------------------------------------------ #

def test_add_get_update_delete_expense(app, user):
    expense_id = add_expense(user, 12345, "Food", days_ago(2), "  Lunch  ")
    expense = get_expense(expense_id, user)
    assert expense["amount_paise"] == 12345
    assert expense["category"] == "Food"
    assert expense["expense_date"] == days_ago(2)
    assert expense["description"] == "Lunch"

    # Pretend it was last edited long ago, so we can see updated_at change.
    get_db().execute(
        "UPDATE expenses SET updated_at = '2000-01-01 00:00:00' WHERE id = ?", (expense_id,)
    )
    get_db().commit()

    assert update_expense(expense_id, user, 50000, "Bills", days_ago(1), "Power bill") is True
    expense = get_expense(expense_id, user)
    assert expense["amount_paise"] == 50000
    assert expense["category"] == "Bills"
    assert expense["description"] == "Power bill"
    assert expense["updated_at"] != "2000-01-01 00:00:00"

    assert delete_expense(expense_id, user) is True
    assert get_expense(expense_id, user) is None
    assert delete_expense(expense_id, user) is False
    assert update_expense(expense_id, user, 100, "Food", days_ago(1)) is False


def test_blank_description_is_stored_as_null(app, user):
    expense_id = add_expense(user, 100, "Other", days_ago(0), "   ")
    assert get_expense(expense_id, user)["description"] is None


def test_users_cannot_touch_each_others_expenses(app, user, other_user):
    their_expense = add_expense(other_user, 9900, "Shopping", days_ago(3), "Shoes")

    assert get_expense(their_expense, user) is None
    assert update_expense(their_expense, user, 1, "Food", days_ago(1)) is False
    assert delete_expense(their_expense, user) is False
    assert get_expenses(user) == []

    still_there = get_expense(their_expense, other_user)
    assert still_there["amount_paise"] == 9900
    assert still_there["category"] == "Shopping"


AMOUNT_MSG = "Please enter an amount between ₹0.01 and ₹10,00,000."
DATE_MSG = "Please enter a valid date (not in the future)."


@pytest.mark.parametrize(
    "amount, category, expense_date, description, message",
    [
        (0, "Food", "2025-01-10", None, AMOUNT_MSG),
        (-100, "Food", "2025-01-10", None, AMOUNT_MSG),
        (100_000_001, "Food", "2025-01-10", None, AMOUNT_MSG),
        (12.5, "Food", "2025-01-10", None, AMOUNT_MSG),
        (True, "Food", "2025-01-10", None, AMOUNT_MSG),
        ("100", "Food", "2025-01-10", None, AMOUNT_MSG),
        (100, "food", "2025-01-10", None, "Please choose a valid category."),
        (100, "Travel", "2025-01-10", None, "Please choose a valid category."),
        (100, "Food", "2025/01/10", None, DATE_MSG),
        (100, "Food", "10-01-2025", None, DATE_MSG),
        (100, "Food", "2025-13-01", None, DATE_MSG),
        (100, "Food", "2025-1-5", None, DATE_MSG),
        (100, "Food", None, None, DATE_MSG),
        (100, "Food", "2025-01-10", "x" * 201, "Description must be 200 characters or fewer."),
    ],
)
def test_add_expense_rejects_bad_input(app, user, amount, category, expense_date, description, message):
    with pytest.raises(ValidationError) as info:
        add_expense(user, amount, category, expense_date, description)
    assert str(info.value) == message
    assert count_rows("expenses") == 0


def test_expense_date_future_limit(app, user):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    day_after = (date.today() + timedelta(days=2)).isoformat()
    assert add_expense(user, 100, "Food", tomorrow)
    with pytest.raises(ValidationError):
        add_expense(user, 100, "Food", day_after)


def test_amount_limits_are_allowed(app, user):
    assert add_expense(user, 1, "Food", days_ago(0))
    assert add_expense(user, 100_000_000, "Other", days_ago(0))
    assert add_expense(user, 100, "Food", days_ago(0), "x" * 200)


def test_update_expense_validates(app, user):
    expense_id = add_expense(user, 100, "Food", days_ago(0))
    with pytest.raises(ValidationError):
        update_expense(expense_id, user, 0, "Food", days_ago(0))
    assert get_expense(expense_id, user)["amount_paise"] == 100


def test_get_expenses_sorting_and_filters(app, user):
    a = add_expense(user, 100, "Food", "2025-01-10")
    b = add_expense(user, 200, "Bills", "2025-02-15")
    c = add_expense(user, 300, "Food", "2025-02-15")
    d = add_expense(user, 400, "Health", "2025-03-01")

    assert [e["id"] for e in get_expenses(user)] == [d, c, b, a]
    # Both the start and end days are included.
    assert [e["id"] for e in get_expenses(user, "2025-01-10", "2025-02-15")] == [c, b, a]
    assert [e["id"] for e in get_expenses(user, start_date="2025-02-15")] == [d, c, b]
    assert [e["id"] for e in get_expenses(user, end_date="2025-01-31")] == [a]
    assert [e["id"] for e in get_expenses(user, category="Food")] == [c, a]
    assert [e["id"] for e in get_expenses(user, "2025-02-01", "2025-02-28", "Food")] == [c]


def test_get_expenses_rejects_bad_filters(app, user):
    with pytest.raises(ValidationError, match="Start date must be before end date."):
        get_expenses(user, "2025-03-01", "2025-01-01")
    with pytest.raises(ValidationError):
        get_expenses(user, start_date="not-a-date")
    with pytest.raises(ValidationError):
        get_expenses(user, category="Nope")


def test_get_recent_expenses(app, user):
    ids = [add_expense(user, 100 + n, "Food", days_ago(10 - n)) for n in range(5)]
    recent = get_recent_expenses(user, limit=2)
    assert [e["id"] for e in recent] == [ids[4], ids[3]]
    assert len(get_recent_expenses(user)) == 5
    for bad in (0, 51, -1, True, "5"):
        with pytest.raises(ValidationError):
            get_recent_expenses(user, limit=bad)


# ------------------------------------------------------------------ #
# Analysis                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def known_expenses(app, user, other_user):
    """A small, known set of expenses, plus one for another user to ignore."""
    add_expense(user, 1000, "Food", "2025-01-05")
    add_expense(user, 2000, "Bills", "2025-01-20")
    add_expense(user, 4000, "Bills", "2025-02-10")
    add_expense(user, 500, "Transport", "2025-02-11")
    add_expense(other_user, 99999, "Bills", "2025-01-20")


def test_get_total_spent(app, user, known_expenses):
    assert get_total_spent(user) == 7500
    assert get_total_spent(user, "2025-01-01", "2025-01-31") == 3000
    assert get_total_spent(user, start_date="2025-02-10") == 4500


def test_get_spending_by_category(app, user, known_expenses):
    assert get_spending_by_category(user) == [
        {"category": "Bills", "total_paise": 6000, "count": 2},
        {"category": "Food", "total_paise": 1000, "count": 1},
        {"category": "Transport", "total_paise": 500, "count": 1},
    ]
    assert get_spending_by_category(user, "2025-02-01", "2025-02-28") == [
        {"category": "Bills", "total_paise": 4000, "count": 1},
        {"category": "Transport", "total_paise": 500, "count": 1},
    ]


def test_category_ties_sort_alphabetically(app, user):
    add_expense(user, 500, "Transport", "2025-01-01")
    add_expense(user, 500, "Food", "2025-01-01")
    assert [c["category"] for c in get_spending_by_category(user)] == ["Food", "Transport"]


def test_get_spending_summary(app, user, known_expenses):
    assert get_spending_summary(user) == {
        "total_paise": 7500,
        "count": 4,
        "average_paise": 1875,
        "top_category": "Bills",
    }
    summary = get_spending_summary(user, "2025-01-01", "2025-01-31")
    assert summary == {"total_paise": 3000, "count": 2, "average_paise": 1500, "top_category": "Bills"}


def test_summary_average_rounds_down(app, user):
    for amount in (100, 100, 101):
        add_expense(user, amount, "Food", "2025-01-01")
    assert get_spending_summary(user)["average_paise"] == 100


def test_get_monthly_totals_includes_zero_months(app, user):
    two_months_back = month_start(2)
    add_expense(user, 1000, "Food", days_ago(0))
    add_expense(user, 2000, "Bills", two_months_back.isoformat())
    add_expense(user, 3000, "Bills", (two_months_back - timedelta(days=1)).isoformat())  # too old

    result = get_monthly_totals(user, months=3)
    assert [r["month"] for r in result] == [month_start(n).strftime("%Y-%m") for n in (2, 1, 0)]
    assert [r["total_paise"] for r in result] == [2000, 0, 1000]


def test_get_monthly_totals_default_and_limits(app, user):
    result = get_monthly_totals(user)
    assert len(result) == 6
    assert result[-1]["month"] == date.today().strftime("%Y-%m")
    assert len(get_monthly_totals(user, months=24)) == 24
    for bad in (0, 25, True, "6"):
        with pytest.raises(ValidationError):
            get_monthly_totals(user, months=bad)


def test_analysis_with_no_expenses(app, user):
    assert get_total_spent(user) == 0
    assert get_spending_by_category(user) == []
    assert all(m["total_paise"] == 0 for m in get_monthly_totals(user))
    assert get_spending_summary(user) == {
        "total_paise": 0,
        "count": 0,
        "average_paise": 0,
        "top_category": None,
    }
    assert get_expenses(user) == []
    assert get_recent_expenses(user) == []
