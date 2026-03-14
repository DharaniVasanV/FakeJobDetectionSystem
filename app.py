import os
import re
import joblib
from datetime import datetime

# Allow OAuth over HTTP (development only)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" 

from flask import (
    Flask, render_template, request,
    redirect, url_for, jsonify, flash, send_from_directory
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, UserMixin, current_user
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from authlib.integrations.flask_client import OAuth

from utils.company_lookup import search_company_links
from utils.ocr_utils import extract_text_from_image
from utils.web_risk import calculate_web_risk
from utils.entity_extraction import extract_entities

# ---------------- APP CONFIG ----------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///fallback.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp"}

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------------- LOAD ML ----------------
model = joblib.load("models/fake_job_model.pkl")
tfidf = joblib.load("models/tfidf_vectorizer.pkl")

# ---------------- OAUTH ----------------
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

# ---------------- DATABASE MODELS ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200))
    google_id = db.Column(db.String(200), unique=True)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    job_text = db.Column(db.Text, nullable=False)
    score = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    source_type = db.Column(db.String(20))     
    image_filename = db.Column(db.String(255))

    company_name = db.Column(db.String(255))
    website_url = db.Column(db.String(500))
    linkedin_url = db.Column(db.String(500))

# ---------------- HELPERS ----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return redirect(url_for("login"))

# ---------- AUTH ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        if User.query.filter_by(email=email).first():
            flash("User already exists", "danger")
            return redirect(url_for("signup"))

        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and user.password and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid credentials", "danger")

    return render_template("login.html")

@app.route("/google-login")
def google_login():
    return google.authorize_redirect(url_for("google_callback", _external=True))

@app.route("/google-callback")
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = token.get("userinfo")

        if not user_info:
            resp = google.get("https://www.googleapis.com/oauth2/v2/userinfo")
            user_info = resp.json()

        user = User.query.filter_by(email=user_info["email"]).first()
        if not user:
            user = User(
                email=user_info["email"],
                google_id=user_info.get("id", user_info.get("sub"))
            )
            db.session.add(user)
            db.session.commit()

        login_user(user)
        return redirect(url_for("dashboard"))

    except Exception as e:
        flash("Google login failed", "danger")
        return redirect(url_for("login"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    predictions = (
        Prediction.query
        .filter_by(user_id=current_user.id)
        .order_by(Prediction.timestamp.desc())
        .limit(10)
        .all()
    )
    return render_template("dashboard.html", predictions=predictions)

# ---------- DETECT ----------
@app.route("/detect", methods=["POST"])
@login_required
def detect():
    text = ""
    source_type = "text"
    image_filename = None

    # IMAGE INPUT
    if "job_image" in request.files and request.files["job_image"].filename:
        file = request.files["job_image"]
        if not allowed_file(file.filename):
            flash("Invalid image type", "danger")
            return redirect(url_for("dashboard"))

        filename = secure_filename(file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(path)

        text = extract_text_from_image(path)
        source_type = "image"
        image_filename = filename

    # TEXT INPUT
    else:
        text = request.form.get("job_text", "")

    if not text.strip():
        flash("No job description found", "danger")
        return redirect(url_for("dashboard"))

    # ML Prediction
    vector = tfidf.transform([text])
    ml_score = float(model.predict_proba(vector)[0][1])
    
    # Web Risk Analysis
    web_risk_score, risk_flags = calculate_web_risk(text)
    
    # Combined Score (70% ML + 30% Rule-based)
    score = float((ml_score * 0.7) + (web_risk_score * 0.3))

    # -------- ENTITY EXTRACTION --------
    entities = extract_entities(text[:1000])  # Analyze first 1000 chars for performance
    
    # Extract company name from organizations
    company_name = None
    if entities['organizations']:
        company_name = entities['organizations'][0]  # Use first detected organization

    company_info = {}
    if company_name:
        company_info = search_company_links(company_name, text)

    prediction = Prediction(
        user_id=current_user.id,
        job_text=text[:500],
        score=score,
        source_type=source_type,
        image_filename=image_filename,
        company_name=company_name,
        website_url=company_info.get("website"),
        linkedin_url=company_info.get("linkedin")
    )

    db.session.add(prediction)
    db.session.commit()

    return render_template(
        "result.html",
        score=round(score, 3),
        ml_score=round(ml_score, 3),
        web_risk_score=round(web_risk_score, 3),
        risk_flags=risk_flags,
        entities=entities,
        job_text=text[:200],
        source_type=source_type,
        company_info=company_info,
        company_name=company_name,
        website_url=company_info.get("website"),
        linkedin_url=company_info.get("linkedin")
    )

# ---------- API ----------
@app.route("/api/predictions")
@login_required
def get_predictions():
    predictions = (
        Prediction.query
        .filter_by(user_id=current_user.id)
        .order_by(Prediction.timestamp.desc())
        .all()
    )

    data = [{
        "timestamp": p.timestamp.strftime("%Y-%m-%d %H:%M"),
        "score": p.score,
        "job_text": p.job_text[:50] + "..." if len(p.job_text) > 50 else p.job_text
    } for p in predictions]

    return jsonify(data)

@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/view-prediction/<int:prediction_id>")
@login_required
def view_prediction(prediction_id):
    prediction = Prediction.query.filter_by(id=prediction_id, user_id=current_user.id).first_or_404()
    
    company_info = {
        "company": prediction.company_name,
        "website": prediction.website_url,
        "linkedin": prediction.linkedin_url
    }
    
    return render_template(
        "result.html",
        score=prediction.score,
        job_text=prediction.job_text[:200],
        source_type=prediction.source_type or "text",
        company_info=company_info
    )

@app.route("/delete-prediction/<int:prediction_id>", methods=["POST"])
@login_required
def delete_prediction(prediction_id):
    prediction = Prediction.query.filter_by(id=prediction_id, user_id=current_user.id).first_or_404()
    db.session.delete(prediction)
    db.session.commit()
    flash("Prediction deleted successfully", "success")
    return redirect(url_for("dashboard"))

# ---------------- INIT DB ----------------
with app.app_context():
    db.create_all()

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
