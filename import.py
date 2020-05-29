# -*- coding: utf-8 -*-
"""
Created on Wed May 20 12:56:35 2020

@author: linda
"""
import os, csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
    
# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

with open("books.csv", "r") as bookfile:
    reader = csv.reader(bookfile)
    
    next(reader)

    for row in reader:
        db.execute("INSERT INTO books(isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                             {"isbn": row[0], "title": row[1], "author": row[2], "year": row[3]})
        
        print(f"Added book {row[1]} with ISBN = {row[0]}, written by {row[2]} in {row[3]} to database")
        
        db.commit ()