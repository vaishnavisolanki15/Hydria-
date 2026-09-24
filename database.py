import sqlite3
import os
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hydria.db')

def get_db_connection():
    """Create and return a database connection with row access by column name."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initialize database tables according to Hydria specifications."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. reports table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        water_body_name TEXT,
        water_body_type TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        water_colour TEXT NOT NULL,
        smell TEXT NOT NULL,
        algae TEXT NOT NULL,
        visible_waste TEXT NOT NULL,
        water_appearance TEXT NOT NULL,
        dead_fish TEXT DEFAULT 'No',
        additional_observation TEXT,
        image_path TEXT NOT NULL,
        image_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Not Watched', 'In Process', 'Submitted')),
        is_demo INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 3. votes table (Community confirmation: 'I observed this too')
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        report_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, report_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
    );
    """)

    # 4. validations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS validations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER,
        file_valid INTEGER DEFAULT 1,
        duplicate_check INTEGER DEFAULT 1,
        image_suitability INTEGER DEFAULT 1,
        location_check INTEGER DEFAULT 1,
        missing_fields TEXT,
        validation_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE SET NULL
    );
    """)

    conn.commit()
    conn.close()

def get_user_by_email(email):
    """Retrieve user record by email address."""
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    """Retrieve user record by user ID."""
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def create_user(name, email, password_hash):
    """Register a new user in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name.strip(), email.strip().lower(), password_hash)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

def create_report(user_id, water_body_name, water_body_type, latitude, longitude,
                  water_colour, smell, algae, visible_waste, water_appearance,
                  dead_fish, additional_observation, image_path, image_hash, status="Submitted", is_demo=0):
    """Insert a new water body report into SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reports (
            user_id, water_body_name, water_body_type, latitude, longitude,
            water_colour, smell, algae, visible_waste, water_appearance,
            dead_fish, additional_observation, image_path, image_hash, status, is_demo
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        water_body_name.strip() if water_body_name else None,
        water_body_type,
        latitude,
        longitude,
        water_colour,
        smell,
        algae,
        visible_waste,
        water_appearance,
        dead_fish,
        additional_observation.strip() if additional_observation else None,
        image_path,
        image_hash,
        status,
        is_demo
    ))
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id

def save_validation(report_id, file_valid, duplicate_check, image_suitability, location_check, missing_fields, validation_message):
    """Log validation record in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO validations (
            report_id, file_valid, duplicate_check, image_suitability, location_check, missing_fields, validation_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        report_id,
        1 if file_valid else 0,
        1 if duplicate_check else 0,
        1 if image_suitability else 0,
        1 if location_check else 0,
        missing_fields,
        validation_message
    ))
    val_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return val_id

def get_report_by_id(report_id):
    """Get single report along with vote count and submitter name."""
    conn = get_db_connection()
    query = """
        SELECT r.*, u.name AS submitter_name,
               (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
        FROM reports r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    """
    report = conn.execute(query, (report_id,)).fetchone()
    conn.close()
    return report

def delete_report(report_id, user_id=None):
    """
    Delete a report if the requesting user is the owner (or user_id is None).
    Also removes the uploaded image file if present and cleans up relations.
    Returns True if successfully deleted, False otherwise.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        report = cursor.execute(
            "SELECT id, image_path, user_id FROM reports WHERE id = ? AND user_id = ?",
            (report_id, user_id)
        ).fetchone()
    else:
        report = cursor.execute(
            "SELECT id, image_path, user_id FROM reports WHERE id = ?",
            (report_id,)
        ).fetchone()

    if not report:
        conn.close()
        return False

    cursor.execute("DELETE FROM votes WHERE report_id = ?", (report_id,))
    cursor.execute("DELETE FROM validations WHERE report_id = ?", (report_id,))
    cursor.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()

    # Clean up image file on disk if not a demo image
    try:
        img_path = report['image_path']
        if img_path and not img_path.startswith('uploads/demo_'):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.join(base_dir, img_path)
            if os.path.exists(full_path):
                os.remove(full_path)
    except Exception:
        pass

    return True

def get_reports_by_user(user_id):
    """Retrieve all reports submitted by a specific user."""
    conn = get_db_connection()
    query = """
        SELECT r.*,
               (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
        FROM reports r
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    """
    reports = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return reports

def get_community_reports():
    """Retrieve all submitted reports for community viewing."""
    conn = get_db_connection()
    query = """
        SELECT r.*, u.name AS submitter_name,
               (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
        FROM reports r
        JOIN users u ON r.user_id = u.id
        WHERE r.status = 'Submitted'
        ORDER BY r.created_at DESC
    """
    reports = conn.execute(query).fetchall()
    conn.close()
    return reports

def get_analysis_board_reports():
    """Retrieve reports grouped by the 3 MVP statuses: Not Watched, In Process, Submitted."""
    conn = get_db_connection()
    query = """
        SELECT r.*, u.name AS submitter_name,
               (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
        FROM reports r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    """
    all_reports = conn.execute(query).fetchall()
    conn.close()

    grouped = {
        'Not Watched': [],
        'In Process': [],
        'Submitted': []
    }
    for r in all_reports:
        status = r['status']
        if status in grouped:
            grouped[status].append(r)
        else:
            grouped['Not Watched'].append(r)
    return grouped

def get_all_image_hashes():
    """Return list of all existing image hashes to check duplicates."""
    conn = get_db_connection()
    rows = conn.execute("SELECT id, image_hash FROM reports").fetchall()
    conn.close()
    return [(row['id'], row['image_hash']) for row in rows]

def check_duplicate_report(lat, lon, water_body_name=None, max_distance_meters=300):
    """
    Check if a report exists near the same coordinates (within ~300m)
    on the current day.
    """
    import math
    conn = get_db_connection()
    today_str = datetime.now().strftime('%Y-%m-%d')
    query = """
        SELECT id, water_body_name, latitude, longitude, created_at, status
        FROM reports
        WHERE DATE(created_at) = DATE(?)
    """
    rows = conn.execute(query, (today_str,)).fetchall()
    conn.close()

    duplicates = []
    for row in rows:
        r_lat, r_lon = row['latitude'], row['longitude']
        # Haversine distance
        dlat = math.radians(r_lat - lat)
        dlon = math.radians(r_lon - lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat)) * math.cos(math.radians(r_lat)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist_m = 6371000 * c

        name_match = False
        if water_body_name and row['water_body_name']:
            if water_body_name.strip().lower() == row['water_body_name'].strip().lower():
                name_match = True

        if dist_m <= max_distance_meters or name_match:
            duplicates.append({
                'id': row['id'],
                'water_body_name': row['water_body_name'] or "Unnamed Water Body",
                'distance_meters': round(dist_m),
                'created_at': row['created_at'],
                'status': row['status']
            })
    return duplicates

def has_user_voted(user_id, report_id):
    """Check if the user has already voted on this report."""
    if not user_id:
        return False
    conn = get_db_connection()
    vote = conn.execute(
        "SELECT id FROM votes WHERE user_id = ? AND report_id = ?",
        (user_id, report_id)
    ).fetchone()
    conn.close()
    return vote is not None

def toggle_vote(user_id, report_id):
    """
    Add or remove a community confirmation vote.
    Returns: (voted_now: bool, total_votes: int)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    existing = cursor.execute(
        "SELECT id FROM votes WHERE user_id = ? AND report_id = ?",
        (user_id, report_id)
    ).fetchone()

    if existing:
        cursor.execute("DELETE FROM votes WHERE id = ?", (existing['id'],))
        voted_now = False
    else:
        cursor.execute("INSERT INTO votes (user_id, report_id) VALUES (?, ?)", (user_id, report_id))
        voted_now = True

    conn.commit()
    total_votes = cursor.execute(
        "SELECT COUNT(*) as cnt FROM votes WHERE report_id = ?",
        (report_id,)
    ).fetchone()['cnt']
    conn.close()
    return voted_now, total_votes
