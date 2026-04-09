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
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
users_db = {
    "user1@email.com": "password123",
    "user2@email.com": "password456"
}

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
# In-memory data store
# ------------------------
items = []

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
    Rule("/report-found", endpoint="report_found", methods=["GET", "POST"]),
    Rule("/item/<item_id>", endpoint="item_detail"),
    Rule("/search", endpoint="search"),
    Rule("/login", endpoint="login", methods=["GET", "POST"]),
    Rule("/logout", endpoint="logout"),
    Rule("/admin", endpoint="admin_dashboard"),
    Rule("/admin/accept/<item_id>", endpoint="accept_item", methods=["POST"]),
])

# ------------------------
# View functions
# ------------------------
def home(request):
    total_lost = sum(1 for i in items if i["type"] == "lost" and i["publish_status"] == "published")
    total_found = sum(1 for i in items if i["type"] == "found" and i["publish_status"] == "published")
    total_claimed = sum(1 for i in items if i["publish_status"] == "claimed")
    recent = sorted([i for i in items if i["publish_status"] == "published"], key=lambda x: x["reported_at"], reverse=True)[:6]
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
    filtered = [i for i in items if i["type"] == "lost" and i["publish_status"] == "published"]
    if category:
        filtered = [i for i in filtered if i["category"].lower() == category.lower()]
    if location:
        filtered = [i for i in filtered if location.lower() in i["location"].lower()]
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
    filtered = [i for i in items if i["type"] == "found" and i["publish_status"] == "published"]
    if category:
        filtered = [i for i in filtered if i["category"].lower() == category.lower()]
    if location:
        filtered = [i for i in filtered if location.lower() in i["location"].lower()]
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
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "type": "lost",
                "publish_status": "pending",
                "reported_at": datetime.now().strftime("%Y-%m-%d"),
                "image": image_path,
                **form_data,
            }
            items.append(new_item)
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
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "type": "found",
                "publish_status": "pending",
                "reported_at": datetime.now().strftime("%Y-%m-%d"),
                "image": image_path,
                **form_data,
            }
            items.append(new_item)
            success = f'Thank you! Your found item report for "{form_data["title"]}" has been submitted.'
            form_data = {}
    return render(
        "report_form.html",
        request=request,
        title="Report Found Item",
        form_type="found",
        categories=CATEGORIES,
        error=error,
        success=success,
        form_data=form_data,
    )


def item_detail(request, item_id):
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return Response("Item not found", status=404)
    return render("item_detail.html", request=request, title=item["title"], item=item)


def search(request):
    query = request.args.get("q", "").strip()
    results = []
    if query:
        q = query.lower()
        results = [
            i for i in items
            if i["publish_status"] == "published" and (
                q in i["title"].lower()
                or q in i["description"].lower()
                or q in i["location"].lower()
                or q in i["category"].lower()
            )
        ]
    return render("search_results.html", request=request, title="Search Results", query=query, results=results)


def login(request):
    error = None
    if request.method == "POST":
        login_type = request.form.get("login_type", "user")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        if login_type == "admin":
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                response = Response()
                response = set_session(response, "admin", "admin")
                response.status_code = 302
                response.headers["Location"] = "/admin"
                return response
            else:
                error = "Invalid admin credentials."
        else:  # user login
            if username in users_db and users_db[username] == password:
                response = Response()
                response = set_session(response, "user", username)
                response.status_code = 302
                response.headers["Location"] = "/"
                return response
            else:
                # Allow any email/password combination for new users
                response = Response()
                response = set_session(response, "user", username)
                response.status_code = 302
                response.headers["Location"] = "/"
                return response
    
    return render("login.html", request=request, title="Login", error=error)


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
    
    pending_items = [i for i in items if i["publish_status"] == "pending"]
    published_items = [i for i in items if i["publish_status"] == "published"]
    claimed_items = [i for i in items if i["publish_status"] == "claimed"]
    all_items = sorted(items, key=lambda x: x["reported_at"], reverse=True)
    
    return render(
        "admin_dashboard.html",
        request=request,
        title="Admin Dashboard",
        pending_items=pending_items,
        published_items=published_items,
        claimed_items=claimed_items,
        all_items=all_items,
        pending_count=len(pending_items),
        published_count=len(published_items),
        claimed_count=len(claimed_items),
    )


def accept_item(request, item_id):
    session = get_session(request)
    if not session or session["type"] != "admin":
        return Response("Unauthorized", status=401)
    
    if request.method == "POST":
        item = next((i for i in items if i["id"] == item_id), None)
        if item:
            item["publish_status"] = "published"
    
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
