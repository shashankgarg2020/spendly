# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

The git root is a wrapper. The Flask app lives in the nested `expense-tracker/` directory, so run all commands from there. A `.venv/` is at the git root. `__MACOSX/` is junk from unzipping and is gitignored.

## Commands

Run from `expense-tracker/`:

- Install: `pip install -r requirements.txt` (Flask 3.1, pytest, pytest-flask)
- Run dev server: `python app.py` (debug mode, **port 5001**, not Flask's default 5000). It runs `init_db()` first, so a fresh clone works.
- Database: `flask --app app init-db` creates the tables; `flask --app app seed-db` also adds a demo user (`demo@spendly.local` / `demo1234`, dev only) with 24 sample expenses. Both are safe to re-run.
- Tests: `pytest`, or a single test with `pytest tests/test_db.py::test_name`. `pytest.ini` sets `pythonpath = .`. The `app` fixture in `tests/conftest.py` points `DATABASE` at a temp file, so tests never touch `expense_tracker.db`; `user` / `other_user` fixtures create test users.
- Specs and plans for each tutorial step live in `.claude/specs/` and `.claude/plans/` at the git root (e.g. `01-database-setup.md`).

## Architecture

This is "Spendly", a personal expense tracker (amounts in rupees) written as a step-by-step tutorial project.

- `app.py`: one module holding every route; there are no blueprints. The routes fall into three groups, each marked with a comment banner:
  - Pages: `/`, `/register`, `/login`. The auth pages are GET-only templates with no form handling yet.
  - Info pages: `/terms`, `/privacy`, `/contact`. `/contact` uses the server-side form pattern to follow: it validates into an `errors` dict, re-renders with `form`, `errors` and `sent`, and returns 400 on invalid input. It does not send email or store anything.
  - Placeholder routes (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) that return "coming in Step N" strings. Each later tutorial step replaces one of these. Keep the step numbering intact.
- `app.py` also sets `app.config["DATABASE"]`, registers `close_db` on teardown, and has a `CLI commands` banner section. It imports only `EMAIL_PATTERN`, `close_db`, `init_db` and `seed_db` from `db.py`, because the placeholder route functions `add_expense` / `delete_expense` share names with db functions.
- `database/db.py`: the whole data layer, using plain `sqlite3` and no ORM. Tables are `users` and `expenses` (with `ON DELETE CASCADE` and an index on `(user_id, expense_date)`).
  - Storage rules: money is stored as integer **paise**, dates as `YYYY-MM-DD` text, and categories come from the fixed `CATEGORIES` tuple.
  - `get_db()` keeps one connection per request on `flask.g`, with `sqlite3.Row` rows and foreign keys on.
  - Function groups: setup (`init_db`, `seed_db`), users (`create_user`, `get_user_by_id/email`, `verify_user`), expenses (CRUD, always scoped by `user_id`) and analysis (`get_total_spent`, `get_spending_by_category`, `get_monthly_totals`, `get_spending_summary`).
  - Bad input raises `ValidationError` (or `DuplicateEmailError`) with a message that is safe to show users.
  - `EMAIL_PATTERN` lives here. Always use `?` placeholders. The DB file `expense_tracker.db` is gitignored.
- `database/money.py`: `rupees_to_paise()` parses user input with `Decimal`, and `paise_to_rupees()` formats with Indian grouping (`₹1,00,000.00`).
- `templates/`: Jinja templates extend `base.html` and override `title` and `content`; there is also an optional `head` block. The navbar and footer links in `base.html` use `url_for(...)`, so renaming a route function breaks them.
- `static/css/style.css`: a single stylesheet. Use the design tokens in `:root` (`--ink*`, `--paper*`, `--accent`, `--danger`, `--radius-*`, plus the DM Serif Display and DM Sans font variables) rather than hard-coded values. Sections are separated by `/* --- Section --- */` banner comments. `static/js/main.js` is empty for now.
