import re

from flask import Flask, render_template, request

app = Flask(__name__)

# A simple pattern for "something@something.something" with no spaces.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


if __name__ == "__main__":
    app.run(debug=True, port=5001)
