"""Database layer for Spendly.

Everything that talks to the SQLite database lives here. Pages (routes in
app.py) should call these functions instead of writing SQL themselves.

Money is always stored as whole paise (an int), e.g. Rs 123.45 -> 12345.
Dates are stored as text in the form YYYY-MM-DD.
"""

import re
import sqlite3
from datetime import date, timedelta

from flask import current_app, g
from werkzeug.security import check_password_hash, generate_password_hash


# ------------------------------------------------------------------ #
# Constants                                                           #
# ------------------------------------------------------------------ #

# The only categories an expense can have. Use this everywhere instead of
# typing the list again.
CATEGORIES = ("Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other")

# A simple pattern for "something@something.something" with no spaces.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_AMOUNT_PAISE = 100_000_000  # Rs 10,00,000
MAX_DESCRIPTION = 200
MAX_NAME = 100
MIN_PASSWORD = 8
MAX_RECENT = 50
MAX_MONTHS = 24

DEMO_NAME = "Demo User"
DEMO_EMAIL = "demo@spendly.local"
DEMO_PASSWORD = "demo1234"  # local development only, never use in production

# User-facing error messages, kept in one place.
MSG_NAME = "Please enter your name (up to 100 characters)."
MSG_EMAIL = "Please enter a valid email address."
MSG_DUPLICATE_EMAIL = "An account with this email already exists."
MSG_PASSWORD = "Password must be at least 8 characters."
MSG_AMOUNT = "Please enter an amount between ₹0.01 and ₹10,00,000."
MSG_CATEGORY = "Please choose a valid category."
MSG_DATE = "Please enter a valid date (not in the future)."
MSG_RANGE_DATE = "Please enter a valid date."
MSG_RANGE_ORDER = "Start date must be before end date."
MSG_DESCRIPTION = "Description must be 200 characters or fewer."
MSG_LIMIT = "Limit must be between 1 and 50."
MSG_MONTHS = "Months must be between 1 and 24."


# ------------------------------------------------------------------ #
# Errors                                                              #
# ------------------------------------------------------------------ #

class ValidationError(ValueError):
    """Input is invalid. The message is safe to show to the user."""


class DuplicateEmailError(ValidationError):
    """A user with this email already exists."""


# ------------------------------------------------------------------ #
# Schema                                                              #
# ------------------------------------------------------------------ #

# The category list in the CHECK below is built from CATEGORIES (fixed
# constants, never user input), so the list is only written once.
_CATEGORY_SQL = ", ".join(f"'{name}'" for name in CATEGORIES)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount_paise  INTEGER NOT NULL CHECK (amount_paise > 0 AND amount_paise <= 100000000),
    category      TEXT    NOT NULL CHECK (category IN ({_CATEGORY_SQL})),
    expense_date  TEXT    NOT NULL,
    description   TEXT    CHECK (description IS NULL OR length(description) <= 200),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_date
    ON expenses (user_id, expense_date);
"""


# ------------------------------------------------------------------ #
# Connection and setup                                                #
# ------------------------------------------------------------------ #

def get_db():
    """Return the database connection for the current request.

    The connection is opened the first time it's needed and then reused
    until the request ends. Rows behave like dicts (row["name"]), and
    foreign keys are switched on so deleting a user deletes their expenses.
    """
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(e=None):
    """Close the connection at the end of the request, if one was opened."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    """Create the tables and index if they don't exist yet.

    Safe to run as often as you like: it never deletes data.
    """
    get_db().executescript(SCHEMA)


def seed_db():
    """Add a demo user and sample expenses for development.

    Does nothing if the demo user already exists, so it's safe to run twice.
    Returns how many expenses were added (0 if nothing was added).
    """
    if get_user_by_email(DEMO_EMAIL) is not None:
        return 0

    today = date.today()
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (DEMO_NAME, DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD)),
        )
        user_id = cur.lastrowid
        rows = [
            (user_id, amount, category, (today - timedelta(days=days_ago)).isoformat(), text)
            for days_ago, amount, category, text in _SEED_EXPENSES
        ]
        db.executemany(
            "INSERT INTO expenses (user_id, amount_paise, category, expense_date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows)


# Fixed sample data: (days ago, amount in paise, category, description).
# Dates are worked out from today, so the data always covers the last
# 3 months but is otherwise identical on every run.
_SEED_EXPENSES = [
    (0, 18_000, "Food", "Lunch at office canteen"),
    (1, 12_000, "Transport", "Auto to station"),
    (3, 65_000, "Shopping", "T-shirt"),
    (4, 249_900, "Bills", "Broadband bill"),
    (6, 45_000, "Entertainment", "Movie tickets"),
    (8, 32_000, "Health", "Pharmacy"),
    (10, 92_000, "Food", "Dinner with friends"),
    (13, 50_000, "Transport", "Metro card recharge"),
    (17, 8_000, "Food", "Tea and snacks"),
    (21, 120_000, "Other", "Birthday gift"),
    (26, 189_000, "Bills", "Electricity bill"),
    (29, 15_000, "Entertainment", "Music subscription"),
    (33, 210_000, "Shopping", "Running shoes"),
    (37, 35_000, "Food", "Groceries"),
    (41, 150_000, "Health", "Doctor consultation"),
    (45, 28_000, "Transport", "Cab to airport"),
    (50, 450_000, "Bills", "Rent share - maintenance"),
    (54, 60_000, "Entertainment", "Concert entry"),
    (58, 110_000, "Food", "Weekend groceries"),
    (63, 70_000, "Other", "Donation"),
    (68, 9_900, "Food", "Breakfast"),
    (74, 85_000, "Shopping", "Kitchen supplies"),
    (79, 55_000, "Bills", "Mobile recharge"),
    (85, 40_000, "Health", "Gym day pass"),
]


# ------------------------------------------------------------------ #
# Private helpers                                                     #
# ------------------------------------------------------------------ #

def _write(sql, params=()):
    """Run one INSERT/UPDATE/DELETE and commit. Roll back if anything fails."""
    db = get_db()
    try:
        cur = db.execute(sql, params)
        db.commit()
        return cur
    except Exception:
        db.rollback()
        raise


def _parse_date(value):
    """Turn a 'YYYY-MM-DD' string into a date, or return None if it isn't one."""
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_name(name):
    if not isinstance(name, str):
        raise ValidationError(MSG_NAME)
    name = name.strip()
    if not 1 <= len(name) <= MAX_NAME:
        raise ValidationError(MSG_NAME)
    return name


def _validate_email(email):
    if not isinstance(email, str):
        raise ValidationError(MSG_EMAIL)
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValidationError(MSG_EMAIL)
    return email


def _validate_password(password):
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise ValidationError(MSG_PASSWORD)
    return password


def _validate_amount(amount_paise):
    # bool is a kind of int in Python (True == 1), so rule it out first.
    if isinstance(amount_paise, bool) or not isinstance(amount_paise, int):
        raise ValidationError(MSG_AMOUNT)
    if not 1 <= amount_paise <= MAX_AMOUNT_PAISE:
        raise ValidationError(MSG_AMOUNT)
    return amount_paise


def _validate_category(category):
    if category not in CATEGORIES:
        raise ValidationError(MSG_CATEGORY)
    return category


def _validate_expense_date(expense_date):
    parsed = _parse_date(expense_date)
    # Allow up to 1 day ahead so time-zone differences don't block anyone.
    if parsed is None or parsed > date.today() + timedelta(days=1):
        raise ValidationError(MSG_DATE)
    return expense_date


def _validate_description(description):
    if description is None:
        return None
    if not isinstance(description, str):
        raise ValidationError(MSG_DESCRIPTION)
    description = description.strip()
    if not description:
        return None
    if len(description) > MAX_DESCRIPTION:
        raise ValidationError(MSG_DESCRIPTION)
    return description


def _validate_range(start_date, end_date):
    start = _parse_date(start_date) if start_date is not None else None
    end = _parse_date(end_date) if end_date is not None else None
    if (start_date is not None and start is None) or (end_date is not None and end is None):
        raise ValidationError(MSG_RANGE_DATE)
    if start and end and start > end:
        raise ValidationError(MSG_RANGE_ORDER)


def _validate_expense(amount_paise, category, expense_date, description):
    """Check every expense field and return the cleaned values."""
    return (
        _validate_amount(amount_paise),
        _validate_category(category),
        _validate_expense_date(expense_date),
        _validate_description(description),
    )


def _date_filter(start_date, end_date):
    """Build the optional date part of a WHERE clause.

    Only fixed text is added to the SQL; the dates themselves always go in
    as ? parameters.
    """
    sql, params = "", []
    if start_date is not None:
        sql += " AND expense_date >= ?"
        params.append(start_date)
    if end_date is not None:
        sql += " AND expense_date <= ?"
        params.append(end_date)
    return sql, params


def _is_positive_int(value, maximum):
    return not isinstance(value, bool) and isinstance(value, int) and 1 <= value <= maximum


# ------------------------------------------------------------------ #
# Users                                                               #
# ------------------------------------------------------------------ #

def create_user(name, email, password):
    """Create a new user and return their id.

    The name and email are trimmed, the email is lowercased, and the
    password is stored only as a hash. Raises ValidationError for bad
    input and DuplicateEmailError if the email is already registered.
    """
    name = _validate_name(name)
    email = _validate_email(email)
    password = _validate_password(password)

    if get_user_by_email(email) is not None:
        raise DuplicateEmailError(MSG_DUPLICATE_EMAIL)

    try:
        cur = _write(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
    except sqlite3.IntegrityError as exc:
        # Someone else registered the same email at the same moment.
        if "UNIQUE" in str(exc):
            raise DuplicateEmailError(MSG_DUPLICATE_EMAIL) from None
        raise
    return cur.lastrowid


def get_user_by_id(user_id):
    """Return a user's id, name, email and created_at, or None if not found.

    The password hash is deliberately left out.
    """
    return get_db().execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def get_user_by_email(email):
    """Return the full user row (including the password hash) for an email.

    The lookup ignores letter case. Returns None if there's no such user.
    Only used for login checks; don't pass this row to templates.
    """
    if not isinstance(email, str):
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()


def verify_user(email, password):
    """Return the user if the email and password are both right, else None.

    It never says which of the two was wrong.
    """
    user = get_user_by_email(email)
    if user is None or not isinstance(password, str):
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


# ------------------------------------------------------------------ #
# Expenses                                                            #
# ------------------------------------------------------------------ #

def add_expense(user_id, amount_paise, category, expense_date, description=None):
    """Save a new expense for a user and return its id.

    amount_paise is a whole number of paise (Rs 123.45 -> 12345).
    An empty description is stored as NULL.
    """
    amount_paise, category, expense_date, description = _validate_expense(
        amount_paise, category, expense_date, description
    )
    cur = _write(
        "INSERT INTO expenses (user_id, amount_paise, category, expense_date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount_paise, category, expense_date, description),
    )
    return cur.lastrowid


def get_expense(expense_id, user_id):
    """Return one expense, or None if it doesn't exist or isn't this user's."""
    return get_db().execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()


def get_expenses(user_id, start_date=None, end_date=None, category=None):
    """Return a user's expenses, newest first.

    Optionally only between start_date and end_date (both days included)
    and/or only in one category.
    """
    _validate_range(start_date, end_date)
    date_sql, params = _date_filter(start_date, end_date)
    sql = "SELECT * FROM expenses WHERE user_id = ?" + date_sql
    params = [user_id] + params
    if category is not None:
        _validate_category(category)
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY expense_date DESC, id DESC"
    return get_db().execute(sql, params).fetchall()


def get_recent_expenses(user_id, limit=5):
    """Return a user's latest expenses (between 1 and 50 of them)."""
    if not _is_positive_int(limit, MAX_RECENT):
        raise ValidationError(MSG_LIMIT)
    return get_db().execute(
        "SELECT * FROM expenses WHERE user_id = ? "
        "ORDER BY expense_date DESC, id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def update_expense(expense_id, user_id, amount_paise, category, expense_date, description=None):
    """Change an expense. Returns True if updated, False if not found or not this user's."""
    amount_paise, category, expense_date, description = _validate_expense(
        amount_paise, category, expense_date, description
    )
    cur = _write(
        "UPDATE expenses SET amount_paise = ?, category = ?, expense_date = ?, "
        "description = ?, updated_at = datetime('now') "
        "WHERE id = ? AND user_id = ?",
        (amount_paise, category, expense_date, description, expense_id, user_id),
    )
    return cur.rowcount == 1


def delete_expense(expense_id, user_id):
    """Delete an expense. Returns True if deleted, False if not found or not this user's."""
    cur = _write(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    )
    return cur.rowcount == 1


# ------------------------------------------------------------------ #
# Analysis                                                            #
# ------------------------------------------------------------------ #

def get_total_spent(user_id, start_date=None, end_date=None):
    """Return the total a user spent, in paise (0 if nothing)."""
    _validate_range(start_date, end_date)
    date_sql, params = _date_filter(start_date, end_date)
    row = get_db().execute(
        "SELECT COALESCE(SUM(amount_paise), 0) FROM expenses WHERE user_id = ?" + date_sql,
        [user_id] + params,
    ).fetchone()
    return row[0]


def get_spending_by_category(user_id, start_date=None, end_date=None):
    """Return spending per category, biggest total first.

    Example: [{"category": "Bills", "total_paise": 450000, "count": 3}, ...]
    """
    _validate_range(start_date, end_date)
    date_sql, params = _date_filter(start_date, end_date)
    rows = get_db().execute(
        "SELECT category, SUM(amount_paise) AS total_paise, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ?" + date_sql + " "
        "GROUP BY category ORDER BY total_paise DESC, category ASC",
        [user_id] + params,
    ).fetchall()
    return [dict(row) for row in rows]


def _last_n_months(months):
    """Return 'YYYY-MM' labels for the last n months, oldest first, ending this month."""
    today = date.today()
    labels = []
    for back in range(months - 1, -1, -1):
        index = today.year * 12 + (today.month - 1) - back
        year, month = divmod(index, 12)
        labels.append(f"{year:04d}-{month + 1:02d}")
    return labels


def get_monthly_totals(user_id, months=6):
    """Return the total spent in each of the last `months` months (1 to 24).

    Oldest month first, this month last. Months with no spending show 0.
    Example: [{"month": "2026-06", "total_paise": 0}, ...]
    """
    if not _is_positive_int(months, MAX_MONTHS):
        raise ValidationError(MSG_MONTHS)
    labels = _last_n_months(months)
    rows = get_db().execute(
        "SELECT substr(expense_date, 1, 7) AS month, SUM(amount_paise) AS total_paise "
        "FROM expenses WHERE user_id = ? AND expense_date >= ? "
        "GROUP BY month",
        (user_id, labels[0] + "-01"),
    ).fetchall()
    totals = {row["month"]: row["total_paise"] for row in rows}
    return [{"month": label, "total_paise": totals.get(label, 0)} for label in labels]


def get_spending_summary(user_id, start_date=None, end_date=None):
    """Return a quick summary of a user's spending.

    Example: {"total_paise": 1245000, "count": 14,
              "average_paise": 88928, "top_category": "Bills"}
    The average is rounded down; top_category is None if there's nothing.
    """
    _validate_range(start_date, end_date)
    date_sql, params = _date_filter(start_date, end_date)
    row = get_db().execute(
        "SELECT COALESCE(SUM(amount_paise), 0), COUNT(*) FROM expenses WHERE user_id = ?" + date_sql,
        [user_id] + params,
    ).fetchone()
    total, count = row[0], row[1]
    by_category = get_spending_by_category(user_id, start_date, end_date)
    return {
        "total_paise": total,
        "count": count,
        "average_paise": total // count if count else 0,
        "top_category": by_category[0]["category"] if by_category else None,
    }
