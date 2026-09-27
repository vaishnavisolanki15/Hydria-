import os
from dotenv import load_dotenv
load_dotenv()

import uuid
import shutil
import threading
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

import database
from image_validator import validate_image_full, compute_dhash, check_duplicate_image, check_photo_suitability
from analysis_engine import generate_water_insight
from seed_demo import seed_database

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hydria_citizen_freshwater_secret_key_2026')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max request size

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'temp'), exist_ok=True)

# Initialize database and seed demo data on first start if needed
database.init_db()
seed_database()

# -------------------------------------------------------------
# Authentication & Access Control Decorator
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for('login', next=request.path))
        # Validate that user ID actually exists in the database
        db_user = database.get_user_by_id(session['user_id'])
        if not db_user:
            session.clear()
            flash("Your previous session is no longer active. Please log in again.", "warning")
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    """Make current user info available to all templates."""
    user = None
    if 'user_id' in session:
        db_user = database.get_user_by_id(session['user_id'])
        if db_user:
            user = {
                'id': db_user['id'],
                'name': db_user.get('name', session.get('user_name', 'Citizen Monitor')),
                'email': db_user.get('email', session.get('user_email', ''))
            }
        else:
            session.clear()
    return dict(current_user=user)

# -------------------------------------------------------------
# Uploads serving route
# -------------------------------------------------------------
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# -------------------------------------------------------------
# Page 1 & Navigation: Home, Login, Register, Logout
# -------------------------------------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email:
            flash("Please enter your email.", "error")
            return render_template('login.html', email=email)

        # Allow empty password to default to universal password 'password123'
        if not password:
            password = 'password123'

        user = database.get_user_by_email(email)
        
        # Universal password 'password123' works for all accounts
        is_authenticated = False
        if user:
            if password == 'password123' or check_password_hash(user['password_hash'], password):
                is_authenticated = True
        elif password == 'password123' or len(password) >= 6:
            # Auto-create user account so any email can log in immediately
            name_part = email.split('@')[0]
            clean_name = ''.join([c if not c.isdigit() else ' ' for c in name_part]).replace('.', ' ').replace('_', ' ').strip().title()
            if not clean_name:
                clean_name = name_part.title()
            pwd_hash = generate_password_hash(password)
            user_id = database.create_user(clean_name, email, pwd_hash)
            user = database.get_user_by_id(user_id)
            is_authenticated = True

        if user and is_authenticated:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard'))
        else:
            flash("Invalid email or password. Note: password is 'password123' for all accounts.", "error")
            return render_template('login.html', email=email)

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Password rules: min 6 chars
        if not name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template('register.html', name=name, email=email)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template('register.html', name=name, email=email)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "error")
            return render_template('register.html', name=name, email=email)

        existing_user = database.get_user_by_email(email)
        if existing_user:
            flash("An account with this email already exists. Please log in.", "error")
            return redirect(url_for('login'))

        password_hash = generate_password_hash(password)
        database.create_user(name, email, password_hash)
        flash("Account created successfully.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# -------------------------------------------------------------
# Page 2: Dashboard / Home Page
# -------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    my_reports = database.get_reports_by_user(user_id)
    return render_template('dashboard.html', reports=my_reports)

# -------------------------------------------------------------
# Page 3: Report Water Body Form (Step 1 & 2)
# -------------------------------------------------------------
@app.route('/report', methods=['GET'])
@login_required
def report_page():
    # Pass empty or retained values if returning from fix
    return render_template('report.html', form_data={}, google_maps_api_key=os.getenv('GOOGLE_MAPS_API_KEY', ''))

# -------------------------------------------------------------
# Page 4: Hydria Report Check / Validation (Step 3)
# -------------------------------------------------------------
@app.route('/validate-report', methods=['POST'])
@login_required
def validate_report():
    """
    Receives observation form data and image file.
    Runs local checks:
    1. Required fields presence
    2. File validity (size, format, integrity)
    3. Perceptual duplicate image check
    4. Photo suitability heuristics
    5. Photo EXIF GPS comparison against browser location
    6. Duplicate report check (nearby same day report)
    """
    # 1. Collect form data
    water_body_name = request.form.get('water_body_name', '').strip()
    water_body_type = request.form.get('water_body_type', '').strip()
    water_colour = request.form.get('water_colour', '').strip()
    smell = request.form.get('smell', '').strip()
    algae = request.form.get('algae', '').strip()
    visible_waste = request.form.get('visible_waste', '').strip()
    water_appearance = request.form.get('water_appearance', '').strip()
    dead_fish = request.form.get('dead_fish', 'No').strip()
    additional_observation = request.form.get('additional_observation', '').strip()

    lat_str = request.form.get('latitude', '').strip()
    lon_str = request.form.get('longitude', '').strip()

    # Re-packaged form state for template reuse
    form_data = {
        'water_body_name': water_body_name,
        'water_body_type': water_body_type,
        'water_colour': water_colour,
        'smell': smell,
        'algae': algae,
        'visible_waste': visible_waste,
        'water_appearance': water_appearance,
        'dead_fish': dead_fish,
        'additional_observation': additional_observation,
        'latitude': lat_str,
        'longitude': lon_str
    }

    # 2. Check required fields
    missing_fields = []
    if not lat_str or not lon_str:
        missing_fields.append("Location coordinates (Latitude & Longitude)")
    if not water_body_type:
        missing_fields.append("Water body type")
    if not water_colour:
        missing_fields.append("Water colour")
    if not smell:
        missing_fields.append("Smell observation")
    if not algae:
        missing_fields.append("Algae observation")
    if not visible_waste:
        missing_fields.append("Visible waste level")
    if not water_appearance:
        missing_fields.append("Water appearance")

    # Image check
    file = request.files.get('image')
    temp_filename = request.form.get('temp_image_filename', '')
    temp_file_path = None

    if file and file.filename != '':
        # Generate safe unique temporary filename
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
        temp_filename = f"temp_{uuid.uuid4().hex}.{ext}"
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, temp_filename)
        file.save(temp_file_path)
    elif temp_filename:
        # User already uploaded an image in previous step
        temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', secure_filename(temp_filename))
        if not os.path.exists(temp_file_path):
            temp_file_path = None
            temp_filename = ''

    if not temp_file_path:
        missing_fields.append("Water body photograph")

    # If any required fields are missing, display friendly Missing Information screen
    if missing_fields:
        return render_template(
            'validation.html',
            has_missing=True,
            missing_fields=missing_fields,
            form_data=form_data,
            temp_filename=temp_filename,
            ready_to_submit=False
        )

    # 3. Parse location coordinates
    try:
        browser_lat = float(lat_str)
        browser_lon = float(lon_str)
    except ValueError:
        return render_template(
            'validation.html',
            has_missing=True,
            missing_fields=["Valid numeric latitude and longitude coordinates"],
            form_data=form_data,
            temp_filename=temp_filename,
            ready_to_submit=False
        )

    # 4. Run Hydria Local Image Validation Engine
    existing_hashes = database.get_all_image_hashes()
    validation_results = validate_image_full(
        temp_file_path,
        browser_lat,
        browser_lon,
        existing_hashes
    )

    # 5. Check Duplicate Report (same user/location/water body on the same day)
    nearby_reports = database.check_duplicate_report(browser_lat, browser_lon, water_body_name)

    duplicate_photo_found = not validation_results.get('duplicate_check', True)
    duplicate_report_found = len(nearby_reports) > 0

    # Determine readiness: Duplicate photos or reports are STRICTLY NOT ALLOWED!
    ready_to_submit = (
        len(missing_fields) == 0 and
        validation_results['file_valid'] and
        not duplicate_photo_found and
        validation_results['image_suitability'] and
        not duplicate_report_found
    )

    return render_template(
        'validation.html',
        has_missing=False,
        missing_fields=[],
        validation=validation_results,
        nearby_reports=nearby_reports,
        duplicate_photo_found=duplicate_photo_found,
        duplicate_report_found=duplicate_report_found,
        form_data=form_data,
        temp_filename=temp_filename,
        ready_to_submit=ready_to_submit
    )

# -------------------------------------------------------------
# Page 5: Final Submit Route
# -------------------------------------------------------------
@app.route('/submit-report', methods=['POST'])
@login_required
def submit_report():
    user_id = session.get('user_id')
    user = database.get_user_by_id(user_id) if user_id else None
    if not user:
        session.clear()
        flash("Your user session has expired or is invalid. Please log in again.", "warning")
        return redirect(url_for('login'))
    
    water_body_name = request.form.get('water_body_name', '').strip()
    water_body_type = request.form.get('water_body_type', '').strip()
    lat_str = request.form.get('latitude', '').strip()
    lon_str = request.form.get('longitude', '').strip()
    water_colour = request.form.get('water_colour', '').strip()
    smell = request.form.get('smell', '').strip()
    algae = request.form.get('algae', '').strip()
    visible_waste = request.form.get('visible_waste', '').strip()
    water_appearance = request.form.get('water_appearance', '').strip()
    dead_fish = request.form.get('dead_fish', 'No').strip()
    additional_observation = request.form.get('additional_observation', '').strip()
    temp_filename = request.form.get('temp_filename', '').strip()

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        flash("Invalid coordinates.", "error")
        return redirect(url_for('report_page'))

    # Strict Check 1: Server-side verification for duplicate report
    dup_reports = database.check_duplicate_report(lat, lon, water_body_name)
    if dup_reports:
        if temp_filename:
            tp = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', secure_filename(temp_filename))
            if os.path.exists(tp):
                try:
                    os.remove(tp)
                except Exception:
                    pass
        dup = dup_reports[0]
        flash(f"Submission blocked: Duplicate reports are strictly not allowed! An observation for '{dup['water_body_name']}' was already submitted today (Report #{dup['id']}).", "error")
        return redirect(url_for('report_page'))

    if not temp_filename:
        flash("Image is required to submit a report.", "error")
        return redirect(url_for('report_page'))

    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', secure_filename(temp_filename))
    if not os.path.exists(temp_path):
        flash("Uploaded image session expired. Please upload your photo again.", "error")
        return redirect(url_for('report_page'))

    # Strict Check 2: Server-side verification for photo suitability (blocking screenshots & non-water pictures)
    with Image.open(temp_path) as img:
        img_suitable, is_suit_warn, suit_msg = check_photo_suitability(img, file_path=temp_path)
    if not img_suitable:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        flash(f"Submission blocked: {suit_msg}", "error")
        return redirect(url_for('report_page'))

    # Strict Check 3: Server-side verification for duplicate photo
    with Image.open(temp_path) as img:
        img_hash = compute_dhash(img) or "hash_unavailable"
    existing_hashes = database.get_all_image_hashes()
    is_dup_img, dup_rep_id = check_duplicate_image(img_hash, existing_hashes)
    if is_dup_img:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        flash(f"Submission blocked: Duplicate photos are strictly not allowed! This photo was already submitted in Report #{dup_rep_id}.", "error")
        return redirect(url_for('report_page'))

    # Move from temp to permanent uploads
    ext = temp_filename.rsplit('.', 1)[-1].lower() if '.' in temp_filename else 'jpg'
    perm_filename = f"report_{uuid.uuid4().hex}.{ext}"
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    perm_path = os.path.join(app.config['UPLOAD_FOLDER'], perm_filename)
    shutil.move(temp_path, perm_path)
    rel_image_path = f"uploads/{perm_filename}"

    # Save to MySQL reports table with robust foreign-key exception handling
    try:
        report_id = database.create_report(
            user_id=user_id,
            water_body_name=water_body_name if water_body_name else None,
            water_body_type=water_body_type,
            latitude=lat,
            longitude=lon,
            water_colour=water_colour,
            smell=smell,
            algae=algae,
            visible_waste=visible_waste,
            water_appearance=water_appearance,
            dead_fish=dead_fish,
            additional_observation=additional_observation,
            image_path=rel_image_path,
            image_hash=img_hash,
            status="Submitted",
            is_demo=0
        )
    except Exception as e:
        app.logger.error(f"Error creating report in MySQL: {e}")
        if "foreign key" in str(e).lower() or "fk_reports_user" in str(e).lower():
            session.clear()
            flash("Your user session was invalid or the account was removed. Please log in again.", "error")
            return redirect(url_for('login'))
        flash("An error occurred while saving your report. Please try again.", "error")
        return redirect(url_for('report_page'))

    # Save validation log entry
    database.save_validation(
        report_id=report_id,
        file_valid=1,
        duplicate_check=1,
        image_suitability=1,
        location_check=1,
        missing_fields="",
        validation_message="Report successfully verified and saved to MySQL database."
    )

    # Run Gemini AI analysis asynchronously in background so submit returns immediately without blocking
    def run_async_ai_task(rep_id, img_rel):
        try:
            r_data = database.get_report_by_id(rep_id)
            if r_data:
                generate_water_insight(r_data, image_path=img_rel, allow_remote=True)
        except Exception as e:
            print(f"Async Gemini analysis error: {e}")

    threading.Thread(target=run_async_ai_task, args=(report_id, rel_image_path), daemon=True).start()

    # Render confirmation screen (Section 19)
    return render_template('submit_success.html', report_id=report_id, water_body_name=water_body_name or "Water Body")

# -------------------------------------------------------------
# Page 6: Community Reports
# -------------------------------------------------------------
@app.route('/community')
def community():
    reports = database.get_community_reports()
    return render_template('community.html', reports=reports)

# -------------------------------------------------------------
# Page 7: Analysis Board
# -------------------------------------------------------------
@app.route('/analysis-board')
def analysis_board():
    conn = database.get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT r.*, u.name AS submitter_name,
                       (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
                FROM reports r
                JOIN users u ON r.user_id = u.id
                ORDER BY r.created_at DESC
            """
            cursor.execute(query)
            all_reports = cursor.fetchall()
    finally:
        conn.close()

    risk_categories = {
        'High Risk': {
            'key': 'high-risk',
            'title': 'High Risk',
            'badge_text': 'High Concern',
            'badge_class': 'badge-high-concern',
            'card_border_class': 'card-border-high',
            'header_class': 'risk-header-high',
            'reports': []
        },
        'Medium Risk': {
            'key': 'medium-risk',
            'title': 'Medium Risk',
            'badge_text': 'Medium Risk',
            'badge_class': 'badge-medium-risk',
            'card_border_class': 'card-border-med',
            'header_class': 'risk-header-med',
            'reports': []
        },
        'Low Risk': {
            'key': 'low-risk',
            'title': 'Low Risk',
            'badge_text': 'Low Risk',
            'badge_class': 'badge-low-risk',
            'card_border_class': 'card-border-low',
            'header_class': 'risk-header-low',
            'reports': []
        }
    }

    status_counts = {'Not Watched': 0, 'In Process': 0, 'Submitted': 0}
    total_count = 0

    for r in all_reports:
        r_dict = database._format_row(r)
        # Use cached Gemini AI insight if available; for uncached, use fast local baseline on board
        insight = generate_water_insight(r_dict, allow_remote=False if not r_dict.get('ai_analysis') else True)
        r_dict['insight'] = insight
        total_count += 1

        st = r_dict.get('status', 'Not Watched')
        if st in status_counts:
            status_counts[st] += 1

        # Classify into High Risk, Medium Risk, Low Risk
        concern = insight.get('concern_level', '')
        if 'High' in concern:
            risk_key = 'High Risk'
        elif 'Moderate' in concern or 'Medium' in concern:
            risk_key = 'Medium Risk'
        else:
            risk_key = 'Low Risk'

        r_dict['risk_category'] = risk_key
        risk_categories[risk_key]['reports'].append(r_dict)

    return render_template(
        'analysis_board.html',
        risk_categories=risk_categories,
        total_count=total_count,
        status_counts=status_counts
    )


@app.route('/analysis-board/status/<int:report_id>', methods=['POST'])
def update_report_status_route(report_id):
    new_status = request.form.get('status') or (request.get_json(silent=True) or {}).get('status')
    if new_status in ['Not Watched', 'In Process', 'Submitted']:
        database.update_report_status(report_id, new_status)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'report_id': report_id, 'new_status': new_status})
        flash(f"Report status moved to '{new_status}'.", "success")
    return redirect(url_for('analysis_board'))


# -------------------------------------------------------------
# Page 8: Report Details Page
# -------------------------------------------------------------
@app.route('/report/<int:report_id>')
def report_detail(report_id):
    report = database.get_report_by_id(report_id)
    if not report:
        flash("Report not found.", "error")
        return redirect(url_for('community'))

    # Generate or load Gemini AI Water Insight
    insight = generate_water_insight(report, image_path=report.get('image_path'))

    # Check if logged in user has voted
    user_id = session.get('user_id')
    user_voted = database.has_user_voted(user_id, report_id) if user_id else False

    return render_template(
        'report_detail.html',
        report=report,
        insight=insight,
        user_voted=user_voted
    )

@app.route('/report/<int:report_id>/reanalyze', methods=['POST'])
@login_required
def reanalyze_report(report_id):
    report = database.get_report_by_id(report_id)
    if not report:
        flash("Report not found.", "error")
        return redirect(url_for('community'))

    generate_water_insight(report, image_path=report.get('image_path'), force_refresh=True)
    flash("✨ Report successfully re-analyzed with Google Gemini AI.", "success")
    return redirect(url_for('report_detail', report_id=report_id))

# -------------------------------------------------------------
# Page 9: Community Voting ("I observed this too")
# -------------------------------------------------------------
@app.route('/vote/<int:report_id>', methods=['POST'])
@login_required
def vote(report_id):
    user_id = session['user_id']
    report = database.get_report_by_id(report_id)
    if not report:
        return jsonify({'error': 'Report not found'}), 404

    voted_now, total_votes = database.toggle_vote(user_id, report_id)

    # If AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'voted': voted_now,
            'total_votes': total_votes,
            'label': 'Confirmed by You' if voted_now else 'I Observed This Too'
        })

    # Standard POST fallback: redirect back to report details
    return redirect(url_for('report_detail', report_id=report_id))

# -------------------------------------------------------------
# Delete Report Route (Authorized Submitter Only)
# -------------------------------------------------------------
@app.route('/report/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_report_route(report_id):
    user_id = session['user_id']
    user = database.get_user_by_id(user_id)
    report = database.get_report_by_id(report_id)
    if not report:
        flash("Report not found.", "error")
        return redirect(url_for('community'))

    # Authorization check:
    # 1. The original submitter can delete their report
    # 2. Platform administrators (Vaishnavi, user ID 1 or 21) can delete any report
    # 3. Any logged-in member can delete sample/demo reports
    is_owner = (report['user_id'] == user_id)
    is_admin = (user_id in [1, 21]) or (user and 'vaishnavi' in user['email'].lower())
    is_demo = bool(report['is_demo']) if 'is_demo' in report.keys() else False

    if not (is_owner or is_admin or is_demo):
        flash("You are not authorized to delete this report.", "error")
        return redirect(url_for('report_detail', report_id=report_id))

    success = database.delete_report(report_id, user_id=None if (is_admin or is_demo) else user_id)
    if success:
        flash(f"Report has been deleted successfully.", "success")
        referer = request.referrer
        if referer and ('/community' in referer or '/analysis-board' in referer):
            return redirect(referer)
        return redirect(url_for('community'))
    else:
        flash("Could not delete report. Please try again.", "error")
        return redirect(url_for('report_detail', report_id=report_id))


# -------------------------------------------------------------
# Geocoding Endpoints (Manual Address, Autocomplete & Map Trace)
# -------------------------------------------------------------
OFFLINE_PLACES = {
    'indore': (22.7196, 75.8577, 'Indore, Madhya Pradesh'),
    'palasia': (22.7247, 75.8872, 'Palasia, Indore, Madhya Pradesh'),
    'vijay nagar': (22.7533, 75.8937, 'Vijay Nagar, Indore, Madhya Pradesh'),
    'bilawali': (22.6841, 75.8752, 'Bilawali Lake, Indore'),
    'sirpur': (22.6950, 75.8180, 'Sirpur Lake, Indore'),
    'bhopal': (23.2599, 77.4126, 'Bhopal, Madhya Pradesh'),
    'upper lake': (23.2500, 77.3500, 'Upper Lake (Bhojtal), Bhopal'),
    'bengaluru': (12.9716, 77.5946, 'Bengaluru, Karnataka'),
    'bangalore': (12.9716, 77.5946, 'Bengaluru, Karnataka'),
    'bellandur': (12.9360, 77.6680, 'Bellandur Lake, Bengaluru'),
    'bellandur lake': (12.9360, 77.6680, 'Bellandur Lake, Bengaluru'),
    'ulsoor': (12.9822, 77.6200, 'Ulsoor Lake, Bengaluru'),
    'ulsoor lake': (12.9822, 77.6200, 'Ulsoor Lake, Bengaluru'),
    'hebbal': (13.0425, 77.5925, 'Hebbal Lake, Bengaluru'),
    'delhi': (28.6139, 77.2090, 'New Delhi, Delhi'),
    'new delhi': (28.6139, 77.2090, 'New Delhi, Delhi'),
    'yamuna': (28.6653, 77.2346, 'Yamuna River, Delhi'),
    'hauz khas': (28.5535, 77.1944, 'Hauz Khas Lake, New Delhi'),
    'mumbai': (19.0760, 72.8777, 'Mumbai, Maharashtra'),
    'marine drive': (18.9438, 72.8234, 'Marine Drive, Mumbai'),
    'powai': (19.1264, 72.9050, 'Powai Lake, Mumbai'),
    'mithi river': (19.0688, 72.8700, 'Mithi River, Mumbai'),
    'pune': (18.5204, 73.8567, 'Pune, Maharashtra'),
    'khadakwasla': (18.4419, 73.7663, 'Khadakwasla Dam, Pune'),
    'hyderabad': (17.3850, 78.4867, 'Hyderabad, Telangana'),
    'hussain sagar': (17.4239, 78.4738, 'Hussain Sagar Lake, Hyderabad'),
    'chennai': (13.0827, 80.2707, 'Chennai, Tamil Nadu'),
    'kolkata': (22.5726, 88.3639, 'Kolkata, West Bengal'),
    'ahmedabad': (23.0225, 72.5714, 'Ahmedabad, Gujarat'),
    'jaipur': (26.9124, 75.7873, 'Jaipur, Rajasthan'),
    'udaipur': (24.5854, 73.7125, 'Udaipur, Rajasthan'),
    'lake pichola': (24.5760, 73.6800, 'Lake Pichola, Udaipur'),
    'dal lake': (34.1167, 74.8667, 'Dal Lake, Srinagar, Kashmir'),
    'srinagar': (34.0837, 74.7973, 'Srinagar, Jammu & Kashmir'),
    'varanasi': (25.3176, 82.9739, 'Varanasi, Uttar Pradesh'),
    'ganga': (25.3050, 83.0100, 'Ganga River, Varanasi'),
    'lucknow': (26.8467, 80.9462, 'Lucknow, Uttar Pradesh'),
    'gomti': (26.8500, 80.9500, 'Gomti River, Lucknow'),
    'chandigarh': (30.7333, 76.7794, 'Chandigarh'),
    'sukhna': (30.7420, 76.8180, 'Sukhna Lake, Chandigarh'),
    'pangong': (33.7595, 78.6674, 'Pangong Tso, Ladakh'),
    'dawki': (25.1850, 92.0150, 'Umngot River, Dawki, Meghalaya')
}

@app.route('/api/geocode', methods=['GET'])
def geocode_address():
    """Geocode a manually typed address or place name to latitude/longitude coordinates."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'message': 'Please provide an address or place name.'}), 400

    q_lower = query.lower().strip()
    # 1. Check offline dictionary first
    for k, v in OFFLINE_PLACES.items():
        if k == q_lower or (len(k) >= 4 and k in q_lower) or (len(q_lower) >= 4 and q_lower in k):
            return jsonify({
                'success': True,
                'source': 'offline',
                'lat': v[0],
                'lon': v[1],
                'display_name': v[2]
            })

    # 2. Try OpenStreetMap Nominatim for exact address/street/city Worldwide
    try:
        import urllib.request, urllib.parse, json
        params = urllib.parse.urlencode({
            'q': query,
            'format': 'json',
            'limit': 3,
            'addressdetails': 1
        })
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Hydria-Citizen-Water/1.0 (contact@hydria.local)'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                first = data[0]
                return jsonify({
                    'success': True,
                    'source': 'nominatim',
                    'lat': float(first['lat']),
                    'lon': float(first['lon']),
                    'display_name': first['display_name']
                })
    except Exception:
        pass

    # If lookup was unsuccessful, return error
    return jsonify({
        'success': False,
        'message': f"Could not find coordinates for '{query}'. Please try typing a city, area, or nearby landmark name."
    }), 404

@app.route('/api/geocode/suggest', methods=['GET'])
def geocode_suggest():
    """Live search suggestions / autocomplete for location search as the user types."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'success': True, 'results': []})

    results = []
    seen = set()
    q_lower = query.lower()

    # 1. Check offline curated water bodies & cities first (instant response)
    for k, v in OFFLINE_PLACES.items():
        if q_lower in k or k in q_lower:
            key = f"{round(v[0], 3)}_{round(v[1], 3)}"
            if key not in seen:
                seen.add(key)
                is_water = any(w in v[2].lower() for w in ['lake', 'river', 'tal', 'sagar', 'dam', 'pond', 'canal', 'ghat'])
                results.append({
                    'name': v[2].split(',')[0],
                    'display_name': v[2],
                    'lat': v[0],
                    'lon': v[1],
                    'is_water': is_water,
                    'source': 'curated'
                })

    # 2. Query Photon API (fast OpenStreetMap autocomplete)
    try:
        import urllib.request, urllib.parse, json
        params = urllib.parse.urlencode({'q': query, 'limit': 6})
        url = f"https://photon.komoot.io/api/?{params}"
        req = urllib.request.Request(url, headers={'User-Agent': 'HydriaWater/1.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            for feat in data.get('features', []):
                p = feat.get('properties', {})
                coords = feat.get('geometry', {}).get('coordinates', [])
                if len(coords) >= 2:
                    name = p.get('name') or p.get('street') or query
                    parts = [name]
                    for loc_key in ['district', 'city', 'state', 'country']:
                        loc_val = p.get(loc_key)
                        if loc_val and loc_val not in parts:
                            parts.append(loc_val)
                    full_name = ", ".join(parts)
                    lon = float(coords[0])
                    lat = float(coords[1])
                    key = f"{round(lat, 3)}_{round(lon, 3)}"
                    if key not in seen:
                        seen.add(key)
                        osm_val = (p.get('osm_value') or '').lower()
                        osm_k = (p.get('osm_key') or '').lower()
                        is_water = (osm_k in ['water', 'natural', 'waterway'] or
                                    osm_val in ['water', 'lake', 'river', 'reservoir', 'pond', 'wetland'] or
                                    any(w in name.lower() for w in ['lake', 'river', 'tal', 'sagar', 'dam', 'pond', 'canal', 'ghat']))
                        results.append({
                            'name': name,
                            'display_name': full_name,
                            'lat': lat,
                            'lon': lon,
                            'is_water': is_water,
                            'source': 'photon'
                        })
    except Exception:
        pass

    # 3. Fallback to OpenStreetMap Nominatim search if no results found
    if len(results) == 0:
        try:
            import urllib.request, urllib.parse, json
            params = urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 4, 'addressdetails': 1})
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Hydria-Citizen-Water/1.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                for item in data:
                    lat = float(item['lat'])
                    lon = float(item['lon'])
                    key = f"{round(lat, 3)}_{round(lon, 3)}"
                    if key not in seen:
                        seen.add(key)
                        name = item.get('display_name', '').split(',')[0]
                        disp = item.get('display_name', '')
                        is_water = any(w in disp.lower() for w in ['lake', 'river', 'tal', 'sagar', 'dam', 'pond', 'canal', 'ghat'])
                        results.append({
                            'name': name,
                            'display_name': disp,
                            'lat': lat,
                            'lon': lon,
                            'is_water': is_water,
                            'source': 'nominatim'
                        })
        except Exception:
            pass

    return jsonify({'success': True, 'results': results[:7]})

@app.route('/api/geocode/reverse', methods=['GET'])
def reverse_geocode():
    """Reverse geocode latitude and longitude to human-readable address on map pin drag/click."""
    lat_str = request.args.get('lat', '').strip()
    lon_str = request.args.get('lon', '').strip()
    if not lat_str or not lon_str:
        return jsonify({'success': False, 'message': 'Missing latitude and longitude.'}), 400

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid numeric coordinates.'}), 400

    try:
        import urllib.request, urllib.parse, json
        params = urllib.parse.urlencode({
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'addressdetails': 1
        })
        url = f"https://nominatim.openstreetmap.org/reverse?{params}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Hydria-Citizen-Water/1.0 (contact@hydria.local)'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            display_name = data.get('display_name', f"Location ({lat:.4f}, {lon:.4f})")
            return jsonify({
                'success': True,
                'display_name': display_name,
                'lat': lat,
                'lon': lon,
                'address': data.get('address', {})
            })
    except Exception:
        return jsonify({
            'success': True,
            'display_name': f"Pinned Location ({lat:.4f}°, {lon:.4f}°)",
            'lat': lat,
            'lon': lon
        })

# -------------------------------------------------------------
# Friendly Error Handling (Section 31)
# -------------------------------------------------------------
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', title="Page Not Found",
                           message="The page you were looking for doesn't exist."), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', title="Something went wrong",
                           message="Something went wrong on our end. Please try again in a moment."), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("The uploaded file exceeds the 5 MB limit. Please select a smaller photo.", "error")
    return redirect(url_for('report_page'))

if __name__ == '__main__':
    # Run locally on 127.0.0.1:5000 with use_reloader=False to prevent
    # Werkzeug from restarting mid-request when files are written to uploads/
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
