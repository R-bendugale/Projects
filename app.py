import os
from datetime import datetime, date, timedelta
from functools import wraps

from bson import ObjectId
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client["campus_borrow_lend"]
users = db["users"]
items = db["items"]
borrow_requests = db["borrow_requests"]
activity_logs = db["activity_logs"]

# Useful indexes for the NoSQL demonstration.
users.create_index([("email", ASCENDING)], unique=True)
items.create_index([("category", ASCENDING), ("availability", ASCENDING)])
items.create_index([("created_at", DESCENDING)])
borrow_requests.create_index([("owner_id", ASCENDING), ("status", ASCENDING)])
borrow_requests.create_index([("borrower_id", ASCENDING), ("requested_at", DESCENDING)])

CATEGORIES = ["Books", "Electronics", "Lab Equipment", "Stationery", "Sports", "Other"]
CONDITIONS = ["New", "Like New", "Good", "Fair"]
STATUSES = ["pending", "approved", "rejected", "borrowed", "returned"]


def now():
    return datetime.now()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        return users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        session.clear()
        return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def log_action(action, item_id=None, request_id=None):
    user = current_user()
    activity_logs.insert_one({
        "actor_id": user["_id"] if user else None,
        "action": action,
        "item_id": ObjectId(item_id) if item_id else None,
        "request_id": ObjectId(request_id) if request_id else None,
        "created_at": now()
    })


def safe_object_id(value):
    try:
        return ObjectId(value)
    except Exception:
        abort(404)


@app.template_filter("dt")
def format_datetime(value, fmt="%d %b %Y, %I:%M %p"):
    if not value:
        return "—"
    if isinstance(value, str):
        return value
    return value.strftime(fmt)


@app.context_processor
def inject_globals():
    return {"logged_user": current_user(), "categories": CATEGORIES, "today": date.today().isoformat()}


@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query = {"availability": "available"}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}}
        ]
    if category in CATEGORIES:
        query["category"] = category
    listing = list(items.find(query).sort("created_at", DESCENDING).limit(100))
    owner_ids = {item.get("owner_id") for item in listing if item.get("owner_id")}
    owner_map = {u["_id"]: u.get("name", "Student") for u in users.find({"_id": {"$in": list(owner_ids)}}, {"name": 1})}
    for item in listing:
        item["owner_name"] = owner_map.get(item.get("owner_id"), "Student")
    return render_template("home.html", items=listing, q=q, selected_category=category)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "").strip()
        password = request.form.get("password", "")
        if not name or not email or not department or len(password) < 8:
            flash("Complete every field. Password must be at least 8 characters.", "danger")
            return render_template("register.html")
        try:
            result = users.insert_one({
                "name": name, "email": email, "department": department,
                "password_hash": generate_password_hash(password), "created_at": now()
            })
        except Exception:
            flash("That email is already registered, or the database rejected the account.", "danger")
            return render_template("register.html")
        session["user_id"] = str(result.inserted_id)
        log_action("USER_REGISTERED")
        flash("Welcome! Your account has been created.", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = users.find_one({"email": email})
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            flash("Incorrect email or password.", "danger")
            return render_template("login.html")
        session.clear()
        session["user_id"] = str(user["_id"])
        flash("You are now logged in.", "success")
        return redirect(request.args.get("next") or url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    my_items = list(items.find({"owner_id": user["_id"]}).sort("created_at", DESCENDING))
    owner_requests = list(borrow_requests.find({"owner_id": user["_id"]}).sort("requested_at", DESCENDING))
    my_borrowings = list(borrow_requests.find({"borrower_id": user["_id"]}).sort("requested_at", DESCENDING))
    total_items = len(my_items)
    available = sum(1 for i in my_items if i.get("availability") == "available")
    borrowed = sum(1 for i in my_items if i.get("availability") == "borrowed")
    pending = sum(1 for r in owner_requests if r.get("status") == "pending")
    category_rows = list(items.aggregate([
        {"$match": {"owner_id": user["_id"]}},
        {"$group": {"_id": "$category", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}}
    ]))
    for req in owner_requests + my_borrowings:
        req["item"] = items.find_one({"_id": req.get("item_id")}) or {"name": "Deleted item"}
        req["owner"] = users.find_one({"_id": req.get("owner_id")}, {"name": 1}) or {"name": "Student"}
        req["borrower"] = users.find_one({"_id": req.get("borrower_id")}, {"name": 1}) or {"name": "Student"}
    return render_template("dashboard.html", my_items=my_items, owner_requests=owner_requests,
        my_borrowings=my_borrowings, total_items=total_items, available=available,
        borrowed=borrowed, pending=pending, category_rows=category_rows)


@app.route("/items/add", methods=["GET", "POST"])
@login_required
def add_item():
    if request.method == "POST":
        user = current_user()
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "")
        condition = request.form.get("condition", "")
        description = request.form.get("description", "").strip()
        tags = [tag.strip().lower() for tag in request.form.get("tags", "").split(",") if tag.strip()]
        building = request.form.get("building", "").strip()
        department = request.form.get("location_department", "").strip()
        if not name or category not in CATEGORIES or condition not in CONDITIONS:
            flash("Please enter an item name and choose a valid category and condition.", "danger")
            return render_template("item_form.html", item=None, conditions=CONDITIONS)
        doc = {
            "name": name, "category": category, "owner_id": user["_id"],
            "condition": condition, "description": description,
            "availability": "available", "tags": tags,
            "location": {"building": building, "department": department},
            "created_at": now(), "updated_at": now()
        }
        result = items.insert_one(doc)
        log_action("ITEM_CREATED", str(result.inserted_id))
        flash("Your item has been listed.", "success")
        return redirect(url_for("my_items"))
    return render_template("item_form.html", item=None, conditions=CONDITIONS)


@app.route("/items/mine")
@login_required
def my_items():
    user = current_user()
    listing = list(items.find({"owner_id": user["_id"]}).sort("created_at", DESCENDING))
    return render_template("my_items.html", items=listing)


@app.route("/items/<item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    oid = safe_object_id(item_id)
    user = current_user()
    item = items.find_one({"_id": oid})
    if not item or item.get("owner_id") != user["_id"]:
        abort(403)
    if item.get("availability") == "borrowed":
        flash("A borrowed item cannot be edited until it is returned.", "warning")
        return redirect(url_for("my_items"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "")
        condition = request.form.get("condition", "")
        if not name or category not in CATEGORIES or condition not in CONDITIONS:
            flash("Please provide a name, category and condition.", "danger")
            return render_template("item_form.html", item=item, conditions=CONDITIONS)
        items.update_one({"_id": oid, "owner_id": user["_id"]}, {"$set": {
            "name": name, "category": category, "condition": condition,
            "description": request.form.get("description", "").strip(),
            "tags": [t.strip().lower() for t in request.form.get("tags", "").split(",") if t.strip()],
            "location": {"building": request.form.get("building", "").strip(),
                         "department": request.form.get("location_department", "").strip()},
            "updated_at": now()
        }})
        log_action("ITEM_UPDATED", item_id)
        flash("Item updated.", "success")
        return redirect(url_for("my_items"))
    return render_template("item_form.html", item=item, conditions=CONDITIONS)


@app.route("/items/<item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    oid = safe_object_id(item_id)
    user = current_user()
    item = items.find_one({"_id": oid, "owner_id": user["_id"]})
    if not item:
        abort(404)
    if item.get("availability") != "available":
        flash("Only available items can be deleted.", "warning")
        return redirect(url_for("my_items"))
    active = borrow_requests.find_one({"item_id": oid, "status": {"$in": ["pending", "approved", "borrowed"]}})
    if active:
        flash("This item has an active borrowing request and cannot be deleted.", "warning")
        return redirect(url_for("my_items"))
    items.delete_one({"_id": oid, "owner_id": user["_id"]})
    log_action("ITEM_DELETED", item_id)
    flash("Item deleted.", "success")
    return redirect(url_for("my_items"))


@app.route("/items/<item_id>")
def item_detail(item_id):
    oid = safe_object_id(item_id)
    item = items.find_one({"_id": oid})
    if not item:
        abort(404)
    owner = users.find_one({"_id": item.get("owner_id")}, {"name": 1, "department": 1}) or {"name": "Student", "department": ""}
    already_requested = False
    if current_user():
        already_requested = bool(borrow_requests.find_one({"item_id": oid, "borrower_id": current_user()["_id"],
            "status": {"$in": ["pending", "approved", "borrowed"]}}))
    return render_template("item_detail.html", item=item, owner=owner, already_requested=already_requested)


@app.route("/items/<item_id>/request", methods=["POST"])
@login_required
def request_item(item_id):
    oid = safe_object_id(item_id)
    user = current_user()
    item = items.find_one({"_id": oid})
    if not item:
        abort(404)
    if item.get("owner_id") == user["_id"]:
        flash("You cannot borrow your own item.", "warning")
        return redirect(url_for("item_detail", item_id=item_id))
    if item.get("availability") != "available":
        flash("This item is no longer available.", "warning")
        return redirect(url_for("item_detail", item_id=item_id))
    existing = borrow_requests.find_one({"item_id": oid, "borrower_id": user["_id"],
        "status": {"$in": ["pending", "approved", "borrowed"]}})
    if existing:
        flash("You already have an active request for this item.", "info")
        return redirect(url_for("dashboard"))
    due_str = request.form.get("due_date", "")
    try:
        due_date = datetime.strptime(due_str, "%Y-%m-%d")
        if due_date.date() < date.today() or due_date.date() > date.today() + timedelta(days=90):
            raise ValueError
    except ValueError:
        flash("Choose a due date between today and the next 90 days.", "danger")
        return redirect(url_for("item_detail", item_id=item_id))
    req_doc = {
        "item_id": oid, "owner_id": item["owner_id"], "borrower_id": user["_id"],
        "requested_at": now(), "due_date": due_date, "status": "pending",
        "status_history": [{"status": "pending", "changed_at": now()}]
    }
    result = borrow_requests.insert_one(req_doc)
    log_action("REQUEST_CREATED", item_id, str(result.inserted_id))
    flash("Borrowing request sent to the owner.", "success")
    return redirect(url_for("dashboard"))


@app.route("/requests/<request_id>/<decision>", methods=["POST"])
@login_required
def decide_request(request_id, decision):
    rid = safe_object_id(request_id)
    user = current_user()
    req = borrow_requests.find_one({"_id": rid, "owner_id": user["_id"], "status": "pending"})
    if not req:
        flash("Request not found or it has already been processed.", "warning")
        return redirect(url_for("dashboard"))
    if decision not in ("approve", "reject"):
        abort(404)
    item = items.find_one({"_id": req["item_id"]})
    if not item:
        borrow_requests.update_one({"_id": rid}, {"$set": {"status": "rejected"},
            "$push": {"status_history": {"status": "rejected", "changed_at": now()}}})
        flash("The item no longer exists, so the request was rejected.", "warning")
        return redirect(url_for("dashboard"))
    if decision == "approve":
        # Conditional update prevents approving requests for an item that is no longer available.
        updated = items.update_one({"_id": item["_id"], "availability": "available"},
                                   {"$set": {"availability": "borrowed", "updated_at": now()}})
        if updated.modified_count != 1:
            flash("This item is no longer available. The request could not be approved.", "warning")
            return redirect(url_for("dashboard"))
        new_status = "approved"
    else:
        new_status = "rejected"
    borrow_requests.update_one({"_id": rid, "status": "pending"}, {"$set": {"status": new_status},
        "$push": {"status_history": {"status": new_status, "changed_at": now()}}})
    log_action("REQUEST_" + new_status.upper(), str(req["item_id"]), request_id)
    flash("Request " + new_status + ".", "success")
    return redirect(url_for("dashboard"))


@app.route("/requests/<request_id>/return", methods=["POST"])
@login_required
def return_item(request_id):
    rid = safe_object_id(request_id)
    user = current_user()
    req = borrow_requests.find_one({"_id": rid, "owner_id": user["_id"], "status": "approved"})
    if not req:
        flash("This return cannot be processed.", "warning")
        return redirect(url_for("dashboard"))
    borrow_requests.update_one({"_id": rid, "status": "approved"}, {"$set": {"status": "returned"},
        "$push": {"status_history": {"status": "returned", "changed_at": now()}}})
    items.update_one({"_id": req["item_id"], "owner_id": user["_id"]},
                     {"$set": {"availability": "available", "updated_at": now()}})
    log_action("ITEM_RETURNED", str(req["item_id"]), request_id)
    flash("Return confirmed. The item is available again.", "success")
    return redirect(url_for("dashboard"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        if not name or not department:
            flash("Name and department are required.", "danger")
        else:
            users.update_one({"_id": user["_id"]}, {"$set": {"name": name, "department": department}})
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


@app.route("/health")
def health():
    try:
        client.admin.command("ping")
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}, 503


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="You do not have permission to do that."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="We couldn't find that page or item."), 404


if __name__ == "__main__":
    app.run(debug=True)
