import os

import click
from flask import Flask, render_template, request

# Only import what app.py needs. db.py also has add_expense/delete_expense,
# which would clash with the placeholder route functions below.
from database.db import EMAIL_PATTERN, close_db, init_db, seed_db

app = Flask(__name__)

# Where the SQLite database file lives (gitignored).
app.config["DATABASE"] = os.path.join(app.root_path, "expense_tracker.db")

# Close the database connection at the end of every request.
app.teardown_appcontext(close_db)


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register")
def register():
    return render_template("register.html")


@app.route("/login")
def login():
    return render_template("login.html")


# ------------------------------------------------------------------ #
# Info pages                                                          #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    # GET: someone just opened the page, so show an empty form.
    if request.method == "GET":
        return render_template("contact.html", form={}, errors={}, sent=False)

    # POST: the form was submitted. Read and tidy up each field.
    form = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "subject": request.form.get("subject", "").strip(),
        "message": request.form.get("message", "").strip(),
    }

    # Collect one error message per problem field.
    errors = {}
    if not form["name"]:
        errors["name"] = "Please enter your name."
    if not form["email"]:
        errors["email"] = "Please enter your email address."
    elif not EMAIL_PATTERN.match(form["email"]):
        errors["email"] = "Please enter a valid email address."
    if not form["subject"]:
        errors["subject"] = "Please enter a subject."
    if not form["message"]:
        errors["message"] = "Please enter a message."

    if errors:
        # Show the form again, keeping what the user typed.
        return render_template("contact.html", form=form, errors=errors, sent=False), 400

    # Everything is valid. Nothing is emailed or saved yet — just say thanks.
    return render_template("contact.html", form={}, errors={}, sent=True)


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


# ------------------------------------------------------------------ #
# CLI commands                                                        #
# ------------------------------------------------------------------ #

@app.cli.command("init-db")
def init_db_command():
    """Create the database tables (safe to run again)."""
    init_db()
    click.echo("Database initialised.")


@app.cli.command("seed-db")
def seed_db_command():
    """Create the tables, then add the demo user and sample expenses."""
    init_db()
    added = seed_db()
    if added:
        click.echo(f"Seeded demo user demo@spendly.local with {added} expenses.")
    else:
        click.echo("Demo data already present, nothing added.")


if __name__ == "__main__":
    # Make sure the tables exist so `python app.py` works on a fresh clone.
    with app.app_context():
        init_db()
    app.run(debug=True, port=5001)
