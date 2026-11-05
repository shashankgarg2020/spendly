"""Shared test fixtures.

Every test gets its own brand-new database in a temporary folder, so
tests never touch the real expense_tracker.db or affect each other.
"""

import pytest

from app import app as flask_app
from database.db import create_user, init_db


@pytest.fixture
def app(tmp_path):
    """The Flask app, pointed at a fresh temporary database.

    pytest-flask uses this fixture and automatically gives each test an
    active request context, so get_db() works inside tests.
    """
    original_config = dict(flask_app.config)
    flask_app.config.update(TESTING=True, DATABASE=str(tmp_path / "test.db"))
    with flask_app.app_context():
        init_db()

    yield flask_app

    flask_app.config.clear()
    flask_app.config.update(original_config)


@pytest.fixture
def user(app):
    """Create a test user and return their id."""
    return create_user("Test User", "test@example.com", "password123")


@pytest.fixture
def other_user(app):
    """Create a second user (for checking users can't see each other's data)."""
    return create_user("Other User", "other@example.com", "password456")
