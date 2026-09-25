import os
import uuid
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
from image_validator import validate_image_full, compute_dhash
from analysis_engine import generate_water_insight
from seed_demo import seed_database

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hydria_citizen_freshwater_secret_key_2026'
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
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    """Make current user info available to all templates."""
    user = None
    if 'user_id' in session:
        user = {
            'id': session['user_id'],
            'name': session.get('user_name', 'Citizen Monitor'),
            'email': session.get('user_email', '')
        }
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
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template('login.html', email=email)

        user = database.get_user_by_email(email)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard'))
        else:
            flash("Invalid email or password. Please try again.", "error")
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
    return render_template('report.html', form_data={})

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
        temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', temp_filename)
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

    # Determine readiness
    ready_to_submit = (
        len(missing_fields) == 0 and
        validation_results['file_valid'] and
        validation_results['duplicate_check'] and
        validation_results['image_suitability']
    )

    return render_template(
        'validation.html',
        has_missing=False,
        missing_fields=[],
        validation=validation_results,
        nearby_reports=nearby_reports,
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
    user_id = session['user_id']
    
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

    if not temp_filename:
        flash("Image is required to submit a report.", "error")
        return redirect(url_for('report_page'))

    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', secure_filename(temp_filename))
    if not os.path.exists(temp_path):
        flash("Uploaded image session expired. Please upload your photo again.", "error")
        return redirect(url_for('report_page'))

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        flash("Invalid coordinates.", "error")
        return redirect(url_for('report_page'))

    # Move from temp to permanent uploads
    ext = temp_filename.rsplit('.', 1)[-1].lower() if '.' in temp_filename else 'jpg'
    perm_filename = f"report_{uuid.uuid4().hex}.{ext}"
    perm_path = os.path.join(app.config['UPLOAD_FOLDER'], perm_filename)
    os.rename(temp_path, perm_path)
    rel_image_path = f"uploads/{perm_filename}"

    # Calculate image hash for permanent storage
    with Image.open(perm_path) as img:
        img_hash = compute_dhash(img) or "hash_unavailable"

    # Save to SQLite reports table
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

    # Save validation log entry
    database.save_validation(
        report_id=report_id,
        file_valid=1,
        duplicate_check=1,
        image_suitability=1,
        location_check=1,
        missing_fields="",
        validation_message="Report successfully verified and submitted."
    )

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
    query = """
        SELECT r.*, u.name AS submitter_name,
               (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
        FROM reports r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    """
    all_reports = conn.execute(query).fetchall()
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
        r_dict = dict(r)
        insight = generate_water_insight(r_dict)
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

    # Generate rule-based Hydria Water Insight
    insight = generate_water_insight(report)

    # Check if logged in user has voted
    user_id = session.get('user_id')
    user_voted = database.has_user_voted(user_id, report_id) if user_id else False

    return render_template(
        'report_detail.html',
        report=report,
        insight=insight,
        user_voted=user_voted
    )

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
    report = database.get_report_by_id(report_id)
    if not report:
        flash("Report not found.", "error")
        return redirect(url_for('dashboard'))

    # Authorization check: only the submitter can delete their report
    if report['user_id'] != user_id:
        flash("You are not authorized to delete this report.", "error")
        return redirect(url_for('report_detail', report_id=report_id))

    success = database.delete_report(report_id, user_id=user_id)
    if success:
        flash("Report has been deleted successfully.", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Could not delete report. Please try again.", "error")
        return redirect(url_for('report_detail', report_id=report_id))


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
    # Run locally on 127.0.0.1:5000 as specified
    app.run(host='127.0.0.1', port=5000, debug=True)
