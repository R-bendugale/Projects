# Campus Borrow & Lend

A student-to-student item sharing portal built with **Python, Flask, MongoDB, PyMongo, HTML and CSS**. Students can list useful items, search available listings, request to borrow items, approve/reject requests, confirm returns, and view a dashboard with MongoDB aggregation statistics.

## Features

- Student registration and login; passwords stored as secure hashes
- Profile editing
- Item CRUD: create, view, edit and delete your own listings
- Search by item name, description or tags; filter by category
- Item condition, tags and embedded location document
- Borrowing requests with due dates, owner approval/rejection and return workflow
- Ownership checks for item editing/deletion and request decisions
- Dashboard totals for listed, available, borrowed and pending items
- Category report built with a MongoDB aggregation pipeline
- Activity log collection
- MongoDB indexes for unique emails, category/availability and request lookup
- Responsive layout and helpful flash messages

## Requirements

- Python 3.10+
- MongoDB Community Server running locally, or a MongoDB connection URI
- Optional: MongoDB Compass for inspecting collections and demonstrating NoSQL concepts

## Run on Windows (PowerShell)

1. Extract this ZIP and open the `campus_borrow_lend` folder in VS Code.
2. Start MongoDB Community Server. The default connection is `mongodb://localhost:27017/`.
3. Open a terminal in this folder and create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Optional: set a secret key and MongoDB URI in PowerShell:

   ```powershell
   $env:SECRET_KEY="use-a-long-random-secret"
   $env:MONGO_URI="mongodb://localhost:27017/"
   ```

5. Start the website:

   ```powershell
   python app.py
   ```

6. Open **http://127.0.0.1:5000**.

If PowerShell blocks environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again.

## MongoDB collections

The application creates/uses database `campus_borrow_lend` and these collections:

- `users` — student profiles and password hashes
- `items` — item listings, tags array and embedded `location` document
- `borrow_requests` — item/owner/borrower references, due dates and status history array
- `activity_logs` — action history

Indexes are created automatically at application startup.

## Suggested demo flow

1. Register Student A and add a calculator or textbook.
2. Log out, register Student B, search for that item and submit a borrowing request.
3. Log in as Student A and approve or reject the request from Dashboard.
4. Confirm the return from Student A's Dashboard.
5. Open MongoDB Compass and inspect the four collections.
6. Show aggregation in `app.py` (`category_rows`) and indexes in the startup section.

## Useful `mongosh` commands for viva

```javascript
use campus_borrow_lend

db.users.find({}, {name: 1, email: 1, department: 1})
db.items.find({availability: "available"})
db.items.createIndex({category: 1, availability: 1})
db.users.getIndexes()

db.items.aggregate([
  {$group: {_id: "$category", total: {$sum: 1}}},
  {$sort: {total: -1}}
])

db.borrow_requests.aggregate([
  {$group: {_id: "$status", total: {$sum: 1}}},
  {$sort: {total: -1}}
])
```

## Notes

- This is a local educational project, not a production-hardened service. Before deployment, configure a strong `SECRET_KEY`, disable Flask debug mode, add CSRF protection and review authorization and transaction behavior.
- The app requires MongoDB to be running before opening it. Visit `/health` to check the database connection.
- The application intentionally keeps the frontend simple so the MongoDB document model, indexes, CRUD operations and aggregation are easy to demonstrate.
