import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    CURRENT = {}  # use this dict for current price
    try:
        STOCKS = db.execute("SELECT name, symbol, shares, price FROM stocks WHERE id = ?", session["user_id"])
    except:
        return render_template("portfolio.html")

    CASH = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    SUM = 0

    CURRENT.clear  # clear the dict before each use
    for stock in STOCKS:
        s = lookup(stock["symbol"])  # cache the stock with lookup method and also gives us access to the latestPrice
        CURRENT[stock["symbol"]] = s["price"]  # for each stock we add to the current dict symbol:latestPrice
        SUM += stock["shares"] * s["price"]  # add current ammount of shares * current price

    TOTAL = CASH[0]["cash"] + SUM
    return render_template("portfolio.html", stocks=STOCKS, current=CURRENT, sum=SUM, cash=usd(CASH[0]["cash"]), total=usd(TOTAL))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    success = 0
    if request.method == "POST":

        # if symbol is good
        if lookup(request.form.get("symbol")):

            if request.form.get("shares").isnumeric() and int(request.form.get("shares")) >= 1:
                success += 1
            else:
                return apology("must be a numeric value")

            stock = lookup(request.form.get("symbol"))
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            shares = db.execute("SELECT shares FROM stocks WHERE id = ? AND symbol = ?", session["user_id"], stock["symbol"])

            if cash[0]["cash"] >= stock["price"] * int(request.form.get("shares")):
                # user has enough cash for stock, lets buy it now
                try:
                    # stock exists so update share count
                    now = datetime.now()
                    time = now.strftime("%d/%m/%Y %H:%M:%S")
                    db.execute("INSERT INTO history (id, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?)",
                               session["user_id"], stock["symbol"], int(request.form.get("shares")), usd(stock["price"]), time)
                    db.execute("UPDATE stocks SET shares = ? WHERE id = ? AND symbol = ?",
                               shares[0]["shares"] + int(request.form.get("shares")), session["user_id"], stock["symbol"])
                except:
                    # stock doesnt exist so add it into table
                    now = datetime.now()
                    time = now.strftime("%d/%m/%Y %H:%M:%S")
                    db.execute("INSERT INTO history (id, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?)",
                               session["user_id"], stock["symbol"], int(request.form.get("shares")), usd(stock["price"]), time)
                    db.execute(s INTO stocks (id, name, symbol, shares, price, total) VALUES (?, ?, ?, ?, ?, ?)",
                               session["user_id"], stock["name"], stock["symbol"], int(request.form.get("shares")), stock["price"], stock["price"] * int(request.form.get("shares")))

                # update user's cash since they just bought some stocks
                new_cash = cash[0]["cash"] - (stock["price"] * float(request.form.get("shares")))
                db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

                return redirect("/")

            else:
                return apology("not enough cash to buy stock")
        else:
            return apology("invalid symbol")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    try:
        HISTORY = db.execute("SELECT symbol, shares, price, time FROM history WHERE id = ?", session["user_id"])
        return render_template("history.html", history=HISTORY)
    except:
        return render_template("history.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # if symbol exists we cache it to a dict then use the dict to access its values
        if lookup(request.form.get("symbol")):
            stock = lookup(request.form.get("symbol"))
            return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=stock["price"])
        else:
            # invalid symbol
            return apology("invalid symbol")

    # request method is GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # if method is POST
    if request.method == "POST":

        # cache all values
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if username == "":
            return apology("please enter a username")

        if password == "":
            return apology("please enter a username")

        if confirmation == "":
            return apology("please enter a confirmation")

        # if request.form.get("password") check password for numbers or special chars

        # check if passwords match
        if password != confirmation:
            return apology("passwords do not match, retry")

        # insert user into db
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))
        except:
            return apology("username already exists")

        # log user in
        session["user_id"] = db.execute("SELECT id FROM users WHERE username = ?", username)

        # return to home page
        return redirect("/")

    # method is GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    STOCKS = db.execute("SELECT name, symbol, shares, price FROM stocks WHERE id = ?", session["user_id"])

    if request.method == "POST":
        sale = db.execute("SELECT shares FROM stocks WHERE id = ? and symbol = ?", session["user_id"], request.form.get("symbol"))
        stock = lookup(request.form.get("symbol"))
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        if sale[0]["shares"] > int(request.form.get("shares")):
            # user has enough shares to sell, so we sell them here
            now = datetime.now()
            time = now.strftime("%d/%m/%Y %H:%M:%S")  # the time at which the transaction was made in string format
            db.execute("UPDATE stocks SET shares = ? WHERE id = ? AND symbol = ?",
                       sale[0]["shares"] - int(request.form.get("shares")), session["user_id"], request.form.get("symbol"))
            db.execute("INSERT INTO history (id, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?)",
                       session["user_id"], request.form.get("symbol"), int(request.form.get("shares")) * -1, stock["price"], time)
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
                       cash[0]["cash"] + (int(request.form.get("shares")) * stock["price"]), session["user_id"])
            return redirect("/")
        elif sale[0]["shares"] == int(request.form.get("shares")):
            # user is trying to sell all their shares so we must update tables accordingly
            now = datetime.now()
            time = now.strftime("%d/%m/%Y %H:%M:%S")
            db.execute("DELETE FROM stocks WHERE id = ? and symbol = ?", session["user_id"], request.form.get("symbol"))
            db.execute("INSERT INTO history (id, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?)",
                       session["user_id"], request.form.get("symbol"), int(request.form.get("shares")) * -1, stock["price"], time)
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
                       cash[0]["cash"] + (int(request.form.get("shares")) * stock["price"]), session["user_id"])
            return redirect("/")
        else:
            # user does not have enough shares to sell
            return apology("you dont have that many shares")

    else:
        return render_template("sell.html", stocks=STOCKS)
