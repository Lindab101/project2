import os, json

from flask import Flask, session, render_template, request, flash, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from flask_login import login_required, LoginManager
from werkzeug.security import check_password_hash, generate_password_hash

import requests



app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/", methods=["POST", "GET"])
def index():
    
    session.clear()
    if request.method == "GET":
        return render_template("index.html")
    else:
        if request.method == "POST":
            if not request.form.get("regusername"):
                return render_template("error.html", text="Sorry, must provide a correct username")
            if not request.form.get("regemail"):
                return render_template("error.html", text="Sorry, must provide an email adress")
            
            check= db.execute("SELECT * FROM users WHERE username = :username",
                              {"username":request.form.get("regusername")}).fetchall()
            checkemail = db.execute ("SELECT * FROM users WHERE email = :email", {"email": request.form.get("regemail")}).fetchall()
            
            if len(check) == 1 or len(checkemail) == 1:
                return render_template("error.html", text="Sorry, must provide a unique username and emailadress")
            
            if not request.form.get("regpassword") == request.form.get("regpassword2"):
                return render_template("error.html", text="Sorry, the passwords are not the same")
            if not request.form.get("regusername"):
                return render_template("error.html", text="Sorry, must provide correct username")
            
            hash_password=generate_password_hash(request.form.get("regpassword"), "sha256")
            
            db.execute("INSERT INTO users (username, hash, email) VALUES (:username, :password, :email)",
                                  {"username":request.form.get("regusername"), "password":hash_password, "email":request.form.get("regemail")})
            
            db.commit()
    
            return redirect("/registered")

@app.route("/registered")
def registered():
    return render_template("registered.html")
    
@app.route("/signin", methods=["POST"])
def signin():
    session.clear()
    if request.method == "POST":
    #ensure username and password were submitten
        if not request.form.get("username"):
            return render_template("error.html", text="Sorry, must provide correct username")
        if not request.form.get("password"):
            return render_template("error.html", text="Sorry, must provide correct password")
        
    #query database for username
        data = db.execute("SELECT * FROM users WHERE username = :username",
                      {"username": request.form.get("username")}).fetchall()
    
    #check if username exists and if password is correct
        if len(data) != 1 or not check_password_hash(data[0]["hash"], request.form.get("password")):
            return render_template("error.html", text="password is invalid or username doesn't exist")
    
        session["user_id"]= data[0][0]
        session["username"]= data[0][1]

        return render_template("dashboard.html", username = session["username"])


@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():

    if request.method == "GET":
        return render_template("dashboard.html")
    

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

@app.route("/search", methods=["POST"])
def search():
    
    username = session["username"]
    
    #get search query from request
    query = request.form.get("query")
    q = "%" + query + "%"

    # search results like typed in request
    result = db.execute("SELECT isbn, title, author, year FROM books WHERE isbn LIKE :q OR title LIKE :q OR author LIKE :q",
                {"q": q})
    
    if result is None:
        return render_template("error.html", text="No such book can be found.")

    # make list to save data in
    list = []

    # lists created in a list
    for row in result:
        rows = []
        for i in range(4):
            rows.append(row[i])

        list.append(rows)

    # results print on found.html
    return render_template("found.html", list=list, username=username)

@app.route("/books/<isbn>", methods=["GET", "POST"])
def books(isbn):
    username = session["username"]
    
    
    if request.method == "GET":
        # Make sure book exists.
        book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        if book is None:
            return render_template("error.html", text="No such books.")
        
        reviews = db.execute("SELECT * FROM user_ratings WHERE isbn_book = :isbn", {"isbn": isbn}).fetchall()
        if len(reviews) == 0:
            render_template("books.html", book=book, username=username, reviewlist=None)
        
        # make list to save data in
        reviewlist = []

        # lists created in a list
        for row in reviews:
            rowss = []
            for i in range(4):
                rowss.append(row[i])

            reviewlist.append(rowss)
            
        # get the Goodreads ratings data through the API
        site = "https://www.goodreads.com/book/review_counts.json?isbns="
        key= "&key=3cekdMcHPx8swsrQbkrd8A"
        isbnstr = str(isbn)
        def remove(string): 
            return string.replace(" ", "") 
        strip = remove(isbnstr)
        wholesite = site+strip+key
        res = requests.get(wholesite)
    
        if res.status_code == 404 or res.status_code == 422:
            data = None
        else:
            goodreads_data = json.loads(res.text)['books'][0]
            data = {
                    'num_ratings': goodreads_data.get('work_ratings_count'),
                    'average_rating': goodreads_data.get('average_rating')
                    }
        
        return render_template("books.html", book=book, username=username, reviewlist=reviewlist, avg=data['average_rating'], nr=data['num_ratings'])


    if request.method == "POST":
        #see if user already submitted a review
        check = db.execute("SELECT * FROM user_ratings WHERE username = :username AND isbn_book= :isbn",
                           {"username": username, "isbn": isbn}).fetchall()
        if len(check) == 1:
            return render_template("error.html", text="You already submitted a review for this book!")
        
        #insert variables into database of user_ratings
        addreview = db.execute("INSERT INTO user_ratings (username, scale, isbn_book, opinion) VALUES (:u, :s, :isbn, :o)",
                               {"u": username, "s": request.form.get("rating"), "isbn": isbn, "o": request.form.get("opinion")})

        db.commit()
        
        return render_template("submit.html", isbn=isbn)
    
    
@app.route("/api/<isbn>", methods=["GET"])
def api(isbn):
    if request.method == "GET":
        
        book = db.execute("SELECT title, author, year FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    
        if book is None:
            return jsonify({"Error": "Invalid ISBN"}), 422
    
        ratings = db.execute("SELECT COUNT(scale), AVG(scale) FROM user_ratings WHERE isbn_book = :isbn", {"isbn": isbn}).fetchone()
        
        def remove(string): 
            return string.replace(" ", "") 
    
        return jsonify({
                "title": book[0].rstrip(),
                "author": book[1].rstrip(),
                "year": book[2],
                "isbn": isbn,
                "review_count": ratings[0],
                "average_score": ratings[1]
                })