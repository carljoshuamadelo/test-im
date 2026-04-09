from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import NotFound
from jinja2 import Environment, FileSystemLoader
import os
import uuid
from datetime import datetime
from werkzeug.middleware.shared_data import SharedDataMiddleware
import json
from http.cookies import SimpleCookie
import mysql.connector

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file_storage):
    """Save an uploaded FileStorage object; return the web path or None."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_FOLDER, filename))
    return f"/static/uploads/{filename}"

# ------------------------
# Basic setup
# ------------------------
BASE_URL = ""

env = Environment(loader=FileSystemLoader("templates"))

# Session and authentication storage (in-memory for demo)
sessions = {}

# ------------------------
# Database connection
# ------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "lost_and_found_dbms",
}

def get_db():
    """Get a MySQL database connection."""
    return mysql.connector.connect(**DB_CONFIG)

def db_fetch_all(query, params=None):
    """Execute a SELECT query and return all rows as list of dicts."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def db_fetch_one(query, params=None):
    """Execute a SELECT query and return one row as dict."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def db_execute(query, params=None):
    """Execute an INSERT/UPDATE/DELETE query."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    conn.commit()
    cursor.close()
    conn.close()

def get_session(request):
    """Get current user session from cookies"""
    cookie = request.cookies.get("session_id")
    if cookie and cookie in sessions:
        return sessions[cookie]
    return None

def set_session(response, user_type, user_id):
    """Set session cookie and store session data"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"type": user_type, "user_id": user_id}
    cookie = SimpleCookie()
    cookie["session_id"] = session_id
    cookie["session_id"]["path"] = "/"
    response.headers.add("Set-Cookie", cookie.output(header="").strip())
    return response

def clear_session(response):
    """Clear session cookie"""
    cookie = SimpleCookie()
    cookie["session_id"] = ""
    cookie["session_id"]["path"] = "/"
    cookie["session_id"]["max-age"] = 0
    response.headers.add("Set-Cookie", cookie.output(header="").strip())
    return response

def render(template, request=None, **context):
    context.update({"base_url": BASE_URL})
    if request:
        session = get_session(request)
        context.update({"session": session})
    return Response(
        env.get_template(template).render(**context),
        content_type="text/html"
    )

# ------------------------
# Categories
# ------------------------

CATEGORIES = [
    "Electronics", "Bags", "Keys", "Clothing", "Jewelry",
    "Accessories", "Documents", "Pets", "Sports", "Toys", "Other"
]

# ------------------------
# Routes
# ------------------------
url_map = Map([
    Rule("/", endpoint="home"),
    Rule("/lost", endpoint="lost_items"),
    Rule("/found", endpoint="found_items"),
    Rule("/report-lost", endpoint="report_lost", methods=["GET", "POST"]),
    Rule("/report-found", endpoint="report_found"),
    Rule("/claim/<item_id>", endpoint="claim_item", methods=["GET", "POST"]),
    Rule("/item/<item_id>", endpoint="item_detail"),
    Rule("/search", endpoint="search"),
    Rule("/login", endpoint="login", methods=["GET", "POST"]),
    Rule("/logout", endpoint="logout"),
    Rule("/admin", endpoint="admin_dashboard"),
    Rule("/admin/accept/<item_id>", endpoint="accept_item", methods=["POST"]),
    Rule("/admin/delete/<item_id>", endpoint="delete_item", methods=["POST"]),
    Rule("/admin/archive/<item_id>", endpoint="archive_item", methods=["POST"]),
    Rule("/admin/edit/<item_id>", endpoint="edit_item", methods=["GET", "POST"]),
    Rule("/admin/confirm-claim/<int:claim_id>", endpoint="confirm_claim", methods=["POST"]),
    Rule("/admin/reject-claim/<int:claim_id>", endpoint="reject_claim", methods=["POST"]),
])

# ------------------------
# View functions
# ------------------------
def home(request):
    total_lost = db_fetch_one("SELECT COUNT(*) AS c FROM items WHERE type='lost' AND publish_status='published'")["c"]
    total_found = db_fetch_one("SELECT COUNT(*) AS c FROM items WHERE type='found' AND publish_status='published'")["c"]
    total_claimed = db_fetch_one("SELECT COUNT(*) AS c FROM items WHERE publish_status='claimed'")["c"]
    recent = db_fetch_all("SELECT * FROM items WHERE publish_status='published' ORDER BY reported_at DESC LIMIT 6")
    return render(
        "home.html",
        request=request,
        title="Home",
        recent_items=recent,
        total_lost=total_lost,
        total_found=total_found,
        total_claimed=total_claimed,
    )


def lost_items(request):
    category = request.args.get("category", "")
    location = request.args.get("location", "")
    query = "SELECT * FROM items WHERE type='lost' AND publish_status='published'"
    params = []
    if category:
        query += " AND LOWER(category) = LOWER(%s)"
        params.append(category)
    if location:
        query += " AND LOWER(location) LIKE LOWER(%s)"
        params.append(f"%{location}%")
    filtered = db_fetch_all(query, params)
    return render(
        "lost_items.html",
        request=request,
        title="Lost Items",
        items=filtered,
        categories=CATEGORIES,
        selected_category=category,
        location_filter=location,
    )


def found_items(request):
    category = request.args.get("category", "")
    location = request.args.get("location", "")
    query = "SELECT * FROM items WHERE publish_status='claimed'"
    params = []
    if category:
        query += " AND LOWER(category) = LOWER(%s)"
        params.append(category)
    if location:
        query += " AND LOWER(location) LIKE LOWER(%s)"
        params.append(f"%{location}%")
    query += " ORDER BY reported_at DESC"
    filtered = db_fetch_all(query, params)
    return render(
        "found_items.html",
        request=request,
        title="Found Items",
        items=filtered,
        categories=CATEGORIES,
        selected_category=category,
        location_filter=location,
    )


def report_lost(request):
    error = None
    success = None
    form_data = {}
    if request.method == "POST":
        form_data = {
            "title": request.form.get("title", "").strip(),
            "category": request.form.get("category", "").strip(),
            "date": request.form.get("date", "").strip(),
            "location": request.form.get("location", "").strip(),
            "description": request.form.get("description", "").strip(),
            "contact": request.form.get("contact", "").strip(),
        }
        if not all(form_data.values()):
            error = "Please fill in all required fields."
        else:
            image_path = save_upload(request.files.get("image"))
            item_id = str(uuid.uuid4())[:8]
            db_execute(
                "INSERT INTO items (id, type, publish_status, title, category, date, location, description, contact, image, reported_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (item_id, "lost", "pending", form_data["title"], form_data["category"], form_data["date"], form_data["location"], form_data["description"], form_data["contact"], image_path, datetime.now().strftime("%Y-%m-%d"))
            )
            success = f'Your lost item report for "{form_data["title"]}" has been submitted successfully!'
            form_data = {}
    return render(
        "report_form.html",
        request=request,
        title="Report Lost Item",
        form_type="lost",
        categories=CATEGORIES,
        error=error,
        success=success,
        form_data=form_data,
    )


def report_found(request):
    category = request.args.get("category", "")
    location = request.args.get("location", "")
    query = "SELECT * FROM items WHERE type='lost' AND publish_status='published'"
    params = []
    if category:
        query += " AND LOWER(category) = LOWER(%s)"
        params.append(category)
    if location:
        query += " AND LOWER(location) LIKE LOWER(%s)"
        params.append(f"%{location}%")
    query += " ORDER BY reported_at DESC"
    lost_items_list = db_fetch_all(query, params)
    return render(
        "report_found.html",
        request=request,
        title="Found an Item?",
        items=lost_items_list,
        categories=CATEGORIES,
        selected_category=category,
        location_filter=location,
    )


def claim_item(request, item_id):
    item = db_fetch_one("SELECT * FROM items WHERE id = %s", (item_id,))
    if not item:
        return Response("Item not found", status=404)
    
    error = None
    success = None
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        contact = request.form.get("contact", "").strip()
        proof = request.form.get("proof", "").strip()
        
        if not all([full_name, contact, proof]):
            error = "Please fill in all required fields."
        else:
            db_execute(
                "INSERT INTO claims (item_id, full_name, contact, proof) VALUES (%s, %s, %s, %s)",
                (item_id, full_name, contact, proof)
            )
            success = f'Your claim for "{item["title"]}" has been submitted! The admin will review it.'
    
    return render(
        "claim_form.html",
        request=request,
        title=f"Claim: {item['title']}",
        item=item,
        error=error,
        success=success,
    )


def item_detail(request, item_id):
    item = db_fetch_one("SELECT * FROM items WHERE id = %s", (item_id,))
    if not item:
        return Response("Item not found", status=404)
    return render("item_detail.html", request=request, title=item["title"], item=item)


def search(request):
    query = request.args.get("q", "").strip()
    results = []
    if query:
        like = f"%{query}%"
        results = db_fetch_all(
            "SELECT * FROM items WHERE publish_status='published' AND (LOWER(title) LIKE LOWER(%s) OR LOWER(description) LIKE LOWER(%s) OR LOWER(location) LIKE LOWER(%s) OR LOWER(category) LIKE LOWER(%s))",
            (like, like, like, like)
        )
    return render("search_results.html", request=request, title="Search Results", query=query, results=results)


def login(request):
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        admin = db_fetch_one("SELECT * FROM admins WHERE username = %s AND password = %s", (username, password))
        if admin:
            response = Response()
            response = set_session(response, "admin", admin["username"])
            response.status_code = 302
            response.headers["Location"] = "/admin"
            return response
        else:
            error = "Invalid admin credentials."
    
    return render("login.html", request=request, title="Admin Login", error=error)


def logout(request):
    response = Response()
    response = clear_session(response)
    response.status_code = 302
    response.headers["Location"] = "/"
    return response


def admin_dashboard(request):
    session = get_session(request)
    if not session or session["type"] != "admin":
        response = Response("Unauthorized", status=401)
        return response
    
    pending_items = db_fetch_all("SELECT * FROM items WHERE publish_status='pending'")
    published_items = db_fetch_all("SELECT * FROM items WHERE publish_status='published'")
    claimed_items = db_fetch_all("SELECT * FROM items WHERE publish_status='claimed'")
    archived_items = db_fetch_all("SELECT * FROM items WHERE publish_status='archived'")
    all_items = db_fetch_all("SELECT * FROM items ORDER BY reported_at DESC")
    pending_claims = db_fetch_all(
        "SELECT c.*, i.title AS item_title, i.type AS item_type, i.category AS item_category, "
        "i.location AS item_location, i.description AS item_description, i.image AS item_image "
        "FROM claims c JOIN items i ON c.item_id = i.id ORDER BY c.created_at DESC"
    )
    
    return render(
        "admin_dashboard.html",
        request=request,
        title="Admin Dashboard",
        pending_items=pending_items,
        published_items=published_items,
        claimed_items=claimed_items,
        archived_items=archived_items,
        all_items=all_items,
        pending_claims=pending_claims,
        pending_count=len(pending_items),
        published_count=len(published_items),
        claimed_count=len(claimed_items),
        archived_count=len(archived_items),
        claims_count=len(pending_claims),
    )


def accept_item(request, item_id):
    session = get_session(request)
    if not session or session["type"] != "admin":
        return Response("Unauthorized", status=401)
    
    if request.method == "POST":
        db_execute("UPDATE items SET publish_status='published' WHERE id = %s", (item_id,))
    
    response = Response()
    response.status_code = 302
    response.headers["Location"] = "/admin"
    return response


def delete_item(request, item_id):
    session = get_session(request)
    if not session or session["type"] != "admin":
        return Response("Unauthorized", status=401)
    
    if request.method == "POST":
        db_execute("DELETE FROM claims WHERE item_id = %s", (item_id,))
        db_execute("DELETE FROM items WHERE id = %s", (item_id,))
    
    response = Response()
    response.status_code = 302
    response.headers["Location"] = "/admin"
    return response


def archive_item(request, item_id):
    session = get_session(request)
    if not session or session["type"] != "admin":
        return Response("Unauthorized", status=401)
    
    if request.method == "POST":
        db_execute("UPDATE items SET publish_status='archived' WHERE id = %s", (item_id,))
    
    response = Response()
    response.status_code = 302
    response.headers["Location"] = "/admin"
    return response


def edit_item(request, item_id):
    session = get_session(request)
    if not session or session["type"] != "admin":
        return Response("Unauthorized", status=401)
    
    item = db_fetch_one("SELECT * FROM items WHERE id = %s", (item_id,))
    if not item:
        return Response("Item not found", status=404)
    
    error = None
    success = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        contact = request.form.get("contact", "").strip()
        item_type = request.form.get("type", "").strip()
        publish_status = request.form.get("publish_status", "").strip()
        
        if not all([title, category, date, location, description, contact]):
            error = "Please fill in all required fields."
        else:
            image_path = save_upload(request.files.get("image"))
            if image_path:
                db_execute(
                    "UPDATE items SET title=%s, category=%s, date=%s, location=%s, description=%s, contact=%s, type=%s, publish_status=%s, image=%s WHERE id=%s",
                    (title, category, date, location, description, contact, item_type, publish_status, image_path, item_id)
                )
            else:
                db_execute(
                    "UPDATE items SET title=%s, category=%s, date=%s, location=%s, description=%s, contact=%s, type=%s, publish_status=%s WHERE id=%s",
                    (title, category, date, location, description, contact, item_type, publish_status, item_id)
                )
            success = f'Item "{title}" has been updated successfully!'
            item = db_fetch_one("SELECT * FROM items WHERE id = %s", (item_id,))
    
    return render(
        "edit_item.html",
        request=request,
        title=f"Edit: {item['title']}",
        item=item,
        categories=CATEGORIES,
        error=error,
        success=success,
    )


def confirm_claim(request, claim_id):
    session = get_session(request)
    if not session or session["type"] != "admin":
        return Response("Unauthorized", status=401)
    
    if request.method == "POST":
        claim = db_fetch_one("SELECT * FROM claims WHERE id = %s", (claim_id,))
        if claim:
            db_execute("UPDATE items SET publish_status='claimed' WHERE id = %s", (claim["item_id"],))
            db_execute("DELETE FROM claims WHERE item_id = %s", (claim["item_id"],))
    
    response = Response()
    response.status_code = 302
    response.headers["Location"] = "/admin"
    return response


def reject_claim(request, claim_id):
    session = get_session(request)
    if not session or session["type"] != "admin":
        return Response("Unauthorized", status=401)
    
    if request.method == "POST":
        db_execute("DELETE FROM claims WHERE id = %s", (claim_id,))
    
    response = Response()
    response.status_code = 302
    response.headers["Location"] = "/admin"
    return response


# ------------------------
# WSGI app
# ------------------------
@Request.application
def app(request):
    adapter = url_map.bind_to_environ(request.environ)
    try:
        endpoint, values = adapter.match()
        return globals()[endpoint](request, **values)
    except NotFound:
        return Response("404 Not Found", status=404)


app = SharedDataMiddleware(app, {
    "/static": os.path.join(os.path.dirname(__file__), "static"),
    "/img": os.path.join(os.path.dirname(__file__), "img"),
})

# ------------------------
# Run standalone server
# ------------------------
if __name__ == "__main__":
    from werkzeug.serving import run_simple
    print("Starting FindIt Lost & Found server on http://localhost:5000")
    run_simple("localhost", 5000, app, use_debugger=True, use_reloader=True)
