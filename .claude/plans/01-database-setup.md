# Plan 01: Database Setup (Spendly, Step 1)

> Source spec: `.claude/specs/01-database-setup.md`
> Branch: `feature/database-setup`
> First step after approval: save a copy of this plan to `.claude/plans/01-database-setup.md` (in the git root, next to `specs/`).

## Context

Spendly has no data layer yet: `database/db.py` is a 5-line comment stub and `app.py` only renders templates. Every later tutorial step (auth, expenses, dashboard) needs somewhere to store users and expenses. This step builds that layer: a SQLite database, the `users` and `expenses` tables, Python functions to read and write them safely, money helpers, two CLI commands, and tests. No pages change.

## What I found in the existing code

| File | Current state | What it means for this step |
|---|---|---|
| `database/db.py` | Comment stub only | Replace it completely |
| `database/__init__.py` | Empty | Leave it; it makes `database` an importable package |
| `app.py` | Defines `EMAIL_PATTERN` (line 8); `/contact` uses it (line 64) | Move the pattern into `db.py` and import it back, so `/contact` keeps working exactly as before |
| `app.py` | Route functions named **`add_expense`** (line 94) and **`delete_expense`** (line 104) | **Name clash.** `db.py` also has `add_expense` and `delete_expense`. So `app.py` must import only `EMAIL_PATTERN`, `close_db`, `init_db` and `seed_db`, never `from database.db import *` or the expense functions. |
| `expense-tracker/.gitignore` | Already ignores `expense_tracker.db` | No change needed |
| `.venv` | Python **3.10.11** | Use `datetime.timezone.utc`, not `datetime.UTC` (3.11+) |
| `requirements.txt` | Flask 3.1.3, Werkzeug 3.1.6, pytest, pytest-flask | Enough. No changes. |

## Files

All paths are relative to `expense-tracker/` (the Flask app folder) unless noted.

| File | Action |
|---|---|
| `database/db.py` | Replace stub with all database code |
| `database/money.py` | Create (rupee/paise helpers) |
| `app.py` | Small edits: config, teardown, CLI commands, start-up, import `EMAIL_PATTERN` |
| `tests/conftest.py` | Create (fixtures) |
| `tests/test_db.py` | Create |
| `tests/test_money.py` | Create |
| `pytest.ini` | **Create (not listed in the spec, see below)** |
| `../CLAUDE.md` | Update the `db.py` description and add the new commands |

**Why `pytest.ini`:** when you run plain `pytest` from `expense-tracker/`, Python can't find `app.py` from inside `tests/` unless we say where to look. A 3-line `pytest.ini` with `pythonpath = .` and `testpaths = tests` fixes this cleanly. The alternative is a `sys.path` hack inside `conftest.py`, which is harder to understand.

## Implementation, in build order

### 1. `database/db.py`

Organised into sections with banner comments, in this order:

**a. Constants and errors**
- `CATEGORIES = ("Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other")`
- `EMAIL_PATTERN` moved here unchanged from `app.py`
- `MAX_AMOUNT_PAISE = 100_000_000`, `MAX_DESCRIPTION = 200`, `MAX_NAME = 100`, `MIN_PASSWORD = 8`
- `ValidationError(ValueError)` and `DuplicateEmailError(ValidationError)`, exactly as in spec 7.1
- `SCHEMA`: the SQL from spec 5.4. The category `CHECK` list is **built from `CATEGORIES`** (joining quoted names) so the list is never typed twice. The names are fixed constants, never user input, so this doesn't break the "no SQL from strings" rule.

**b. Connection and setup**
- `get_db()`: if `"db"` isn't on `flask.g` yet, open `sqlite3.connect(current_app.config["DATABASE"])`, set `row_factory = sqlite3.Row`, run `PRAGMA foreign_keys = ON`, then store it on `g`. Return `g.db`.
- `close_db(e=None)`: `g.pop("db", None)` and close it if there is one.
- `init_db()`: `get_db().executescript(SCHEMA)`. All statements use `IF NOT EXISTS`, so it's safe to run again.
- `seed_db()`: see section 5 below.

**c. Private helpers** (start with `_` so they're clearly internal)
- `_write(sql, params)`: runs one write, commits, and returns the cursor. On any error it rolls back and re-raises. Every write function goes through it, which covers rule 10.2 #4 in one place.
- `_validate_amount`: must be an `int` and not a `bool` (in Python, `True` counts as an int, so check `bool` first), and between 1 and `MAX_AMOUNT_PAISE`.
- `_validate_category`, `_validate_date`, `_validate_description` and `_validate_range`, each using the exact messages from spec 10.1.
- `_validate_date`: parse with `date.fromisoformat` and also require the exact `YYYY-MM-DD` shape (length 10). Reject anything later than `date.today() + 1 day`.
- `_validate_description`: trim it; an empty result becomes `None`; more than 200 characters raises an error.
- `_validate_range(start, end)`: both are optional. Any given value must be a valid date, and `start <= end`.
- `_date_filter(start, end)`: builds the `AND expense_date >= ?` / `<= ?` fragments and their parameter list. Values always go in as `?` parameters; only the fixed fragment text is joined. The expense list and analysis queries reuse it.

**d. Users**
- `create_user(name, email, password)`: trim `name`, trim and lowercase `email`, validate all three, then `generate_password_hash(password)`. Check first whether the email already exists, and also catch `sqlite3.IntegrityError` (in case two signups race). Both raise `DuplicateEmailError`. Returns `cursor.lastrowid`.
- `get_user_by_id(user_id)`: selects `id, name, email, created_at` only, with **no `password_hash`** (rule 10.2 #6).
- `get_user_by_email(email)`: lowercases the input and selects `*`, including the hash, because login needs it.
- `verify_user(email, password)`: looks up by email, then `check_password_hash`. Returns the row only if both match, otherwise `None`. For a non-string email it returns `None` rather than crashing.

**e. Expenses** (every query has `WHERE ... user_id = ?`)
- `add_expense(...)`: validate the fields, insert, and return the new id.
- `get_expense(expense_id, user_id)`: `WHERE id = ? AND user_id = ?`.
- `get_expenses(user_id, start_date, end_date, category)`: validate the range, and the category if one is given. `ORDER BY expense_date DESC, id DESC`.
- `get_recent_expenses(user_id, limit=5)`: `limit` must be an int from 1 to 50 (raises `ValidationError` otherwise). Uses `LIMIT ?`.
- `update_expense(...)`: same validation as `add_expense`. `UPDATE ... SET ..., updated_at = datetime('now') WHERE id = ? AND user_id = ?`, returning `cursor.rowcount == 1`.
- `delete_expense(expense_id, user_id)`: `DELETE ... WHERE id = ? AND user_id = ?`, returning `rowcount == 1`.

**f. Analysis**
- `get_total_spent`: `SELECT COALESCE(SUM(amount_paise), 0)`, so it gives 0 instead of `None` when there are no expenses.
- `get_spending_by_category`: `GROUP BY category ORDER BY total_paise DESC, category ASC` (ties are sorted alphabetically, so results are always the same). Returns a list of plain dicts.
- `get_monthly_totals(user_id, months=6)`: `months` must be an int from 1 to 24.
  - Build the list of `YYYY-MM` labels in Python, going back from the current month (`date.today()`).
  - Query `strftime('%Y-%m', expense_date)` grouped totals from the first day of the oldest month onward.
  - Fill in any missing months with 0. Return them oldest first.
- `get_spending_summary`: one query for `total` and `count`; `average_paise = total // count` (rounded down, 0 if there are none); `top_category` is the first item from `get_spending_by_category`, or `None`.

### 2. `database/money.py`
- `rupees_to_paise(value)`:
  - Reject `bool` values.
  - For strings, remove commas and whitespace. Convert floats with `Decimal(str(value))`, so the conversion never relies on float maths.
  - Catch `InvalidOperation`. Reject NaN and infinity, values of zero or below, and anything with more than 2 decimal places (`-exponent > 2`).
  - Return `int(amount * 100)`.
  - Errors raise `ValidationError` (imported from `db.py`) with the amount message from spec 10.1.
- `paise_to_rupees(paise)`:
  - Split into rupees and paise with `divmod`.
  - Apply Indian grouping by hand: the last 3 digits, then groups of 2 (`1,00,000`).
  - Format as `₹{grouped}.{pp:02d}`, with a leading `-` for negative values.

### 3. `app.py` (minimal, nothing else touched)
- Add the imports: `os`, `click`, and `from database.db import EMAIL_PATTERN, close_db, init_db, seed_db`. Remove `import re` and the local `EMAIL_PATTERN` (lines 1 and 7–8).
- After `app = Flask(__name__)`, set `app.config["DATABASE"] = os.path.join(app.root_path, "expense_tracker.db")` and call `app.teardown_appcontext(close_db)`.
- Add a new `# CLI commands` banner section with:
  - `init-db`: prints `Database initialised.`
  - `seed-db`: runs `init_db()` then `seed_db()`, and prints either "Seeded demo user demo@spendly.local with N expenses." or "Demo data already present, nothing added."
- In `if __name__ == "__main__":`, run `with app.app_context(): init_db()` before `app.run(debug=True, port=5001)`.
- The database is never created at import time.

### 4. Tests
- **`conftest.py`**:
  - `app` fixture: set `TESTING`, point `DATABASE` at `tmp_path / "test.db"`, run `init_db()` inside an app context, yield the app, then restore the original config.
  - pytest-flask then gives each test an active request context automatically, so `get_db()` works inside tests.
  - `user` fixture: creates "Test User" and returns the id. `other_user` fixture: a second user, used for the ownership tests.
- **`test_db.py`**: one test (or a small parametrised group) per row of the spec 12 table.
  - Analysis tests insert known expenses with dates relative to `date.today()`, so they keep passing whatever the date is.
  - The month-boundary maths is tested by checking the labels and the zero-filled months.
- **`test_money.py`**: valid inputs (`"123.45"`, `"1,250"`, `99`, `" 5 "`); invalid inputs (`"abc"`, `"0"`, `"-5"`, `"1.234"`, `""`, `True`, `"nan"`); formatting (`12345`, `1245000`, `10000000`, `0`).

### 5. Seed data (`seed_db`)
- If `demo@spendly.local` already exists, return 0 and do nothing.
- Otherwise:
  - Create the demo user with `create_user`.
  - Insert a **fixed list of 24 expenses** stored in the code as `(days_ago, amount_paise, category, description)`. `days_ago` runs from 0 to about 85, covering all 7 categories with realistic amounts (Food ₹80–₹1,200, Bills ₹500–₹4,500, and so on).
  - Dates are worked out as `today - days_ago`, so the data always spans the "last 3 months" while staying the same every run.
  - Insert all of them in one transaction, so it either all works or nothing is added.
- Returns the number of expenses added.

### 6. `CLAUDE.md` (git root)
- Replace the "empty stub" description of `database/db.py` with a short summary: the tables, the money stored in paise, the function groups, and `money.py`.
- Add the `flask --app app init-db` / `seed-db` commands and the demo login.
- Update the Tests line, since tests now exist and `pytest.ini` is in place.
- Note: `CLAUDE.md` is currently **untracked**. I'll edit it but won't commit it unless you say so.

## Rules checklist I'll follow while coding
- Only `?` placeholders. The only joined SQL text is the fixed category list and fixed filter fragments; no user values ever go into the SQL text.
- Every expense query filters by `user_id`.
- Passwords are never stored, printed or logged in plain text, and `password_hash` is only returned by `get_user_by_email` and `verify_user`.
- Templates, CSS, placeholder routes, step numbers, port 5001 and `requirements.txt` stay unchanged.
- Every public function gets a short, plain-English docstring.

## Verification (run from `expense-tracker/` with the venv active)
1. `pytest -v`: everything passes.
2. Delete any `expense_tracker.db`, then run `flask --app app init-db`. Check the tables with the spec's `python -c "import sqlite3; ..."` one-liner (it should list `users`, `expenses` and `idx_expenses_user_date`).
3. Run `flask --app app seed-db` twice. The first run adds 24 expenses, the second adds nothing. Check with `select count(*) from expenses`.
4. Check that the demo user's `password_hash` starts with `scrypt:` and is not `demo1234`.
5. Delete the database file and run `python app.py`. It should start on port 5001 and create the DB. Open `/`, `/register`, `/login`, `/terms`, `/privacy` and `/contact`, and submit the contact form with a bad email: it should return 400 with "Please enter a valid email address.", as before. The placeholder routes should still show their "coming in Step N" text.
6. `git status` should not show `expense_tracker.db`, and `git diff main -- templates static requirements.txt` should be empty.
7. Go through the spec's section 13 definition of done and report pass or fail for each item.

## Commits (on `feature/database-setup`)
1. `Add database layer and money helpers` (`db.py`, `money.py`)
2. `Wire database into app and add CLI commands` (`app.py`)
3. `Add tests for database and money helpers` (`tests/`, `pytest.ini`)

I'll only push and open the PR into `main` after you confirm.
