# Spec 01: Database Setup

| | |
|---|---|
| **Feature** | Database layer for Spendly (users, expenses, spending analysis) |
| **Tutorial step** | Step 1, Database Setup |
| **Branch** | `feature/database-setup` (created from an up-to-date `main`) |
| **Status** | Ready to build |
| **Owner** | Shashank G |

---

## 1. Goal

Give Spendly a real database so that:

1. A **customer (user)** can be stored with their login details.
2. Each user's **expenses** can be stored, read, edited and deleted.
3. Each user's spending can be **analysed** (totals, by category, by month, by date range).

This step builds the **data layer only**: the database, the tables, and the Python functions that every later step will call. The pages (register, login, add expense, and so on) are connected to these functions in later steps.

---

## 2. Scope

### In scope

- SQLite database file and connection handling
- `users` and `expenses` tables, with constraints and indexes
- Functions for users, expenses and analysis in `database/db.py`
- Money helpers in `database/money.py`
- Setup in `app.py`: database path, connection closing, and `init-db` / `seed-db` commands
- Sample (seed) data for development
- Automated tests for every function

### Out of scope (later steps)

| Not in this step | Comes in |
|---|---|
| Register form saving a user, login checking a password | Step 2 (Auth) |
| Logout and sessions | Step 3 |
| Profile page | Step 4 |
| Dashboard and charts using the analysis functions | Steps 5–6 |
| Add / edit / delete expense pages | Steps 7–9 |
| Moving to PostgreSQL for production | Future |

The placeholder routes in `app.py` (`/logout`, `/profile`, `/expenses/...`) must **stay unchanged**, including their "coming in Step N" text.

---

## 3. Technical decisions

| Decision | Choice | Why |
|---|---|---|
| Database | **SQLite** (file `expense_tracker.db`) | Built into Python, nothing to install, one file. It's enough for learning and a small number of users. |
| Database file location | `expense-tracker/expense_tracker.db` (already in `.gitignore`) | Keeps real data out of git |
| Access style | Plain SQL through Python's `sqlite3` module, no ORM | It's easier to learn what's happening, and there are no new dependencies |
| Money | Stored as **whole paise** (`INTEGER`), e.g. ₹123.45 is stored as `12345` | Decimal numbers (floats) cause rounding errors with money. Whole numbers don't. |
| Dates | Stored as text in ISO format `YYYY-MM-DD` | SQLite has no date type, and ISO text sorts and compares correctly |
| Passwords | Hashed with `werkzeug.security` | Passwords are **never** stored as plain text |
| Categories | A fixed list in code, also enforced by the database | Simple. A categories table can come later if users need custom ones. |

### Categories (fixed list)

```
Food, Transport, Bills, Health, Entertainment, Shopping, Other
```

Defined once as `CATEGORIES` in `database/db.py`. Everything else must use that constant rather than retyping the list.

---

## 4. Dependencies

**No new packages.** Everything needed is already in `requirements.txt` or in Python itself.

| Need | Comes from | Already available? |
|---|---|---|
| Database | `sqlite3` (Python standard library) | ✅ |
| Password hashing | `werkzeug.security` (installed with Flask; `werkzeug==3.1.6` is pinned) | ✅ |
| Dates | `datetime` (standard library) | ✅ |
| Paths | `os` (standard library) | ✅ |
| Money parsing | `decimal` (standard library) | ✅ |
| Tests | `pytest==8.3.5`, `pytest-flask==1.3.0` | ✅ |

`requirements.txt` must **not** change.

---

## 5. Data model

### 5.1 `users` table

Stores each customer and their login details.

| Column | Type | Rules |
|---|---|---|
| `id` | INTEGER | Primary key, auto-increment |
| `name` | TEXT | Required, 1–100 characters after trimming spaces |
| `email` | TEXT | Required, **unique**, stored in lowercase |
| `password_hash` | TEXT | Required. The hash, never the real password. |
| `created_at` | TEXT | Set automatically to the current UTC time |

### 5.2 `expenses` table

Stores each expense, linked to the user who owns it.

| Column | Type | Rules |
|---|---|---|
| `id` | INTEGER | Primary key, auto-increment |
| `user_id` | INTEGER | Required. Links to `users.id`. If a user is deleted, their expenses are deleted too. |
| `amount_paise` | INTEGER | Required, greater than 0, at most 100,000,000 (₹10,00,000) |
| `category` | TEXT | Required, must be one of `CATEGORIES` |
| `expense_date` | TEXT | Required, `YYYY-MM-DD` |
| `description` | TEXT | Optional, at most 200 characters |
| `created_at` | TEXT | Set automatically |
| `updated_at` | TEXT | Set automatically, and updated on every edit |

### 5.3 Relationship

```
users (1) ────< (many) expenses
```

One user has many expenses. Each expense belongs to exactly one user.

### 5.4 SQL (reference)

```sql
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
    category      TEXT    NOT NULL CHECK (category IN
                    ('Food','Transport','Bills','Health','Entertainment','Shopping','Other')),
    expense_date  TEXT    NOT NULL,
    description   TEXT    CHECK (description IS NULL OR length(description) <= 200),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_date
    ON expenses (user_id, expense_date);
```

The index makes "this user's expenses between two dates" fast, and that's the most common query.

---

## 6. Files to create or change

| File | Action | What changes |
|---|---|---|
| `expense-tracker/database/db.py` | **Replace** the comment stub | All database code (section 7) |
| `expense-tracker/database/money.py` | **Create** | Rupee ↔ paise helpers (section 7.6) |
| `expense-tracker/app.py` | **Edit** | Database config, connection closing, CLI commands (section 8) |
| `expense-tracker/tests/conftest.py` | **Create** | `app` fixture using a temporary database |
| `expense-tracker/tests/test_db.py` | **Create** | Tests for the database functions |
| `expense-tracker/tests/test_money.py` | **Create** | Tests for the money helpers |
| `CLAUDE.md` | **Edit** | Update the `database/db.py` description, and add the `init-db` / `seed-db` commands |
| `requirements.txt` | No change | |
| Templates and CSS | No change | |

---

## 7. Functions in `database/db.py`

All functions that read or write data take a **`user_id`** where relevant, and only ever touch **that user's** rows. One user must never be able to read, change or delete another user's expenses.

### 7.1 Errors

```python
class ValidationError(ValueError):
    """Input is invalid. The message is safe to show to the user."""

class DuplicateEmailError(ValidationError):
    """A user with this email already exists."""
```

### 7.2 Connection and setup

| Function | Behaviour |
|---|---|
| `get_db()` | Returns the SQLite connection for the current request. Stores it on `flask.g` so it's created **once per request**. Path comes from `current_app.config["DATABASE"]`. Sets `row_factory = sqlite3.Row` (so rows act like dicts) and runs `PRAGMA foreign_keys = ON`. |
| `close_db(e=None)` | Closes the connection if one is open. Registered with `app.teardown_appcontext`. |
| `init_db()` | Creates the tables and index using `CREATE TABLE IF NOT EXISTS`. Safe to run many times, and **never deletes data**. |
| `seed_db()` | Adds sample data (section 9). If the demo user already exists, does nothing, so it's safe to run twice. |

### 7.3 Users

| Function | Returns | Behaviour |
|---|---|---|
| `create_user(name, email, password)` | new user `id` (int) | Trims `name` and `email`, lowercases `email`, checks the rules (section 10.1), hashes the password, inserts the row. Raises `DuplicateEmailError` if the email exists. |
| `get_user_by_id(user_id)` | row or `None` | |
| `get_user_by_email(email)` | row or `None` | Case-insensitive (lowercases the input) |
| `verify_user(email, password)` | user row or `None` | Returns the user only if the email exists **and** the password matches the hash. Returns `None` in every other case, without saying which part was wrong. |

### 7.4 Expenses

| Function | Returns | Behaviour |
|---|---|---|
| `add_expense(user_id, amount_paise, category, expense_date, description=None)` | new expense `id` | Validates every field (section 10.1). An empty or whitespace-only description is stored as `NULL`. |
| `get_expense(expense_id, user_id)` | row or `None` | `None` if the expense doesn't exist **or** belongs to someone else |
| `get_expenses(user_id, start_date=None, end_date=None, category=None)` | list of rows | Newest first (`expense_date` descending, then `id` descending). Date filters include both the start and end days. |
| `get_recent_expenses(user_id, limit=5)` | list of rows | The latest `limit` expenses. `limit` must be 1–50. |
| `update_expense(expense_id, user_id, amount_paise, category, expense_date, description=None)` | `True` if updated, `False` if not found or not owned | Same validation as `add_expense`. Sets `updated_at`. |
| `delete_expense(expense_id, user_id)` | `True` if deleted, `False` if not found or not owned | |

### 7.5 Analysis

These are the functions the dashboard and charts will use later.

| Function | Returns | Example |
|---|---|---|
| `get_total_spent(user_id, start_date=None, end_date=None)` | total in paise (int, `0` if none) | `1245000` |
| `get_spending_by_category(user_id, start_date=None, end_date=None)` | list of dicts sorted by total, highest first | `[{"category": "Bills", "total_paise": 450000, "count": 3}, ...]` |
| `get_monthly_totals(user_id, months=6)` | list of dicts, oldest month first, **including months with no spending** (total `0`) | `[{"month": "2026-06", "total_paise": 0}, {"month": "2026-07", "total_paise": 820000}, ...]` |
| `get_spending_summary(user_id, start_date=None, end_date=None)` | one dict | `{"total_paise": 1245000, "count": 14, "average_paise": 88928, "top_category": "Bills"}`. `average_paise` is rounded down. `top_category` is `None` if there are no expenses. |

`months` must be 1–24. Months run back from the current month, which is included.

### 7.6 Money helpers in `database/money.py`

| Function | Behaviour |
|---|---|
| `rupees_to_paise(value)` | Accepts a string or number such as `"123.45"`, `"1,250"` or `99`. Removes commas and spaces, then converts using `Decimal` (never `float`). Raises `ValidationError` if the value isn't a valid positive amount, or has more than 2 decimal places. `"123.45"` becomes `12345`. |
| `paise_to_rupees(paise)` | Returns a display string with Indian digit grouping: `12345` becomes `"₹123.45"`, `1245000` becomes `"₹12,450.00"`, `10000000` becomes `"₹1,00,000.00"`. |

---

## 8. Changes to `app.py`

1. **Database path.** Add, near the top:
   ```python
   app.config["DATABASE"] = os.path.join(app.root_path, "expense_tracker.db")
   ```
2. **Close connections.** Register `close_db`:
   ```python
   app.teardown_appcontext(close_db)
   ```
3. **CLI commands.** Add two Flask commands:
   - `flask --app app init-db` runs `init_db()` and prints `Database initialised.`
   - `flask --app app seed-db` runs `init_db()` then `seed_db()`, and prints what it did
4. **Start-up.** In the `if __name__ == "__main__":` block only, call `init_db()` inside `app.app_context()` before `app.run(...)`, so `python app.py` works on a fresh clone.
   - **Don't** create the database at import time. Tests import `app` and must use their own temporary database.
5. **Email pattern.** Import `EMAIL_PATTERN` from `database/db.py` instead of defining it here. The `/contact` page must behave exactly as before.
6. **Leave everything else unchanged**: existing routes, placeholder routes and their step numbers, port 5001.

---

## 9. Seed data (development only)

`seed_db()` creates:

- **One demo user:** name `Demo User`, email `demo@spendly.local`, password `demo1234`
- **About 20–30 expenses** for that user spread over the **last 3 months**, covering **every category**, with realistic amounts (e.g. Food ₹80–₹1,200, Bills ₹500–₹4,500) and short descriptions

Use a fixed random seed, or a fixed list, so the data is the same every time.

The demo password is for local development only and must never be used in production.

---

## 10. Implementation rules

### 10.1 Validation rules

| Field | Rule | Error message (shown to user) |
|---|---|---|
| name | 1–100 characters after trimming | "Please enter your name (up to 100 characters)." |
| email | Matches `EMAIL_PATTERN`. Move the pattern from `app.py` into `database/db.py`, and have `app.py` import it from there, so there's only one copy. | "Please enter a valid email address." |
| email | Not already registered | "An account with this email already exists." |
| password | At least 8 characters | "Password must be at least 8 characters." |
| amount_paise | An `int` (not `bool`), from 1 to 100,000,000 | "Please enter an amount between ₹0.01 and ₹10,00,000." |
| category | One of `CATEGORIES` (exact match) | "Please choose a valid category." |
| expense_date | Valid `YYYY-MM-DD` date, not more than 1 day in the future | "Please enter a valid date (not in the future)." |
| description | At most 200 characters after trimming | "Description must be 200 characters or fewer." |
| start/end date | Valid dates, and start must not be after end | "Start date must be before end date." |

### 10.2 Coding rules

1. **Always use parameterised queries** (`?` placeholders). Never build SQL with f-strings or `+`, which would allow SQL injection.
2. **Always filter by `user_id`** for expense reads, updates and deletes.
3. **Validate in Python first**, with the database `CHECK` constraints as a safety net.
4. **Commit after every successful write.** On any error during a write, roll back.
5. **Never store, log or print plain passwords.**
6. **Never return `password_hash`** from any function except the ones used internally for login (`get_user_by_email`, `verify_user`).
7. Use the `CATEGORIES` constant; never retype the list.
8. Add a short docstring to every public function, written simply, because this is a learning project.
9. Follow the existing code style: comment banners in `app.py`, and plain, readable code.
10. Don't change templates, CSS or the step numbering.

---

## 11. Error handling expectations

| Situation | Expected behaviour |
|---|---|
| Invalid input | Raise `ValidationError` with a friendly message from 10.1. Nothing is written to the database. |
| Duplicate email | Raise `DuplicateEmailError`. Catch `sqlite3.IntegrityError` and turn it into this error, so the user never sees a raw database error. |
| Expense not found, or owned by another user | `get_expense` returns `None`; `update_expense` and `delete_expense` return `False`. **Don't** reveal whether the expense exists for someone else. |
| Wrong email or password at login | `verify_user` returns `None`. Don't reveal which one was wrong. |
| No expenses yet | Analysis functions return `0`, empty lists, or (for monthly totals) months with `0`, never `None` or an error. |
| Unexpected database error (file locked, disk full) | Roll back and let the error bubble up. Later steps show a generic "Something went wrong" page. **Never show SQL or stack traces to users.** |
| Database file missing | `init_db()` creates it. `get_db()` must not crash on a fresh clone after `init_db()` has run. |

---

## 12. Tests

Create `expense-tracker/tests/`. Tests must use a **temporary database** (pytest's `tmp_path`), never `expense_tracker.db`.

**`conftest.py`**: an `app` fixture that sets `app.config["TESTING"] = True`, points `DATABASE` at a temp file, runs `init_db()`, and yields the app. Also a fixture that creates a test user.

**Tests to include, at minimum:**

| Area | Test |
|---|---|
| Setup | `init_db()` creates both tables; running it twice doesn't fail or lose data |
| Setup | Foreign keys are on (deleting a user deletes their expenses) |
| Setup | `seed_db()` creates the demo user and expenses; running it twice doesn't duplicate them |
| Users | Create a user, then read it back by id and by email (in any letter case) |
| Users | Duplicate email (in different letter case) raises `DuplicateEmailError` |
| Users | The password is stored hashed, not as plain text |
| Users | `verify_user` works with the right password and returns `None` for a wrong password or unknown email |
| Users | Invalid name, email or password raise `ValidationError` |
| Expenses | Add, get, update and delete an expense |
| Expenses | **User A can't get, update or delete user B's expense** |
| Expenses | Invalid amount (0, negative, too large, float, bool), category, date (bad format, future) and long description each raise `ValidationError` |
| Expenses | `get_expenses` sorts newest first and filters correctly by date range and category |
| Analysis | Totals, category breakdown, monthly totals (including zero months), and summary are correct for known data |
| Analysis | Every analysis function works for a user with **no** expenses |
| Money | `rupees_to_paise` handles valid input and rejects bad input; `paise_to_rupees` formats with Indian grouping |

Run all tests from `expense-tracker/`:

```powershell
pytest -v
```

---

## 13. Definition of done

The feature is complete only when **every** box is ticked:

**Functionality**
- [ ] `database/db.py` contains every function in section 7, with docstrings
- [ ] `database/money.py` contains both helpers
- [ ] `flask --app app init-db` creates `expense_tracker.db` with both tables and the index
- [ ] `flask --app app seed-db` adds the demo user and sample expenses, and running it twice causes no duplicates
- [ ] `python app.py` starts on port 5001 on a fresh clone with no database file, and all existing pages still work

**Quality**
- [ ] All tests pass (`pytest -v`) with **no** failures or errors
- [ ] Every SQL query uses `?` placeholders
- [ ] Every expense query filters by `user_id`
- [ ] No plain-text passwords anywhere
- [ ] No new packages; `requirements.txt` is unchanged
- [ ] Templates, CSS and placeholder routes are unchanged

**Housekeeping**
- [ ] `expense_tracker.db` is **not** committed (`git status` doesn't show it)
- [ ] `CLAUDE.md` is updated with the new commands and the `db.py` description
- [ ] Work is committed on the `feature/database-setup` branch with clear commit messages
- [ ] A pull request into `main` is opened, describing what was built and how to test it

**Manual check**
- [ ] Open the database and confirm the tables, for example:
  `python -c "import sqlite3; c=sqlite3.connect('expense_tracker.db'); print(c.execute('select name from sqlite_master').fetchall())"`
- [ ] Confirm the demo user's password is a long hash, not `demo1234`

---

## 14. How to build this with Claude Code

1. Create the branch:
   ```powershell
   git checkout main
   git pull origin main
   git checkout -b feature/database-setup
   ```
2. Activate the environment and start Claude:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   claude
   ```
3. Turn on **Plan mode** (Shift + Tab) and send:
   > Read .claude/specs/database-setup.md and make a plan to implement it. Follow every rule in the spec. Ask me if anything is unclear. Explain each change simply, because I'm learning.
4. Review and approve the plan. Approve each file change.
5. When Claude has finished, ask:
   > Check the work against the definition of done in section 13 and tell me which items pass and which don't.
6. Commit, push, and open a pull request.
