import os
import math
from datetime import datetime
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

# Load environment variables from .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'kuki')
MYSQL_DB = os.getenv('MYSQL_DB', 'hydria_db')

def get_db_connection(use_database=True):
    """
    Create and return a MySQL connection with dictionary cursor and UTF-8 charset.
    """
    connect_kwargs = {
        'host': MYSQL_HOST,
        'port': MYSQL_PORT,
        'user': MYSQL_USER,
        'password': MYSQL_PASSWORD,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'autocommit': True
    }
    if use_database:
        connect_kwargs['database'] = MYSQL_DB

    return pymysql.connect(**connect_kwargs)

def init_db():
    """
    Initialize MySQL database and required tables for Hydria platform.
    """
    # 1. Connect without DB to ensure database exists
    conn = get_db_connection(use_database=False)
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    finally:
        conn.close()

    # 2. Connect to Hydria database and create tables
    conn = get_db_connection(use_database=True)
    try:
        with conn.cursor() as cursor:
            # 1. users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_users_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 2. reports table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                water_body_name VARCHAR(255) NULL,
                water_body_type VARCHAR(100) NOT NULL,
                latitude DECIMAL(10, 7) NOT NULL,
                longitude DECIMAL(10, 7) NOT NULL,
                water_colour VARCHAR(100) NOT NULL,
                smell VARCHAR(100) NOT NULL,
                algae VARCHAR(100) NOT NULL,
                visible_waste VARCHAR(100) NOT NULL,
                water_appearance VARCHAR(100) NOT NULL,
                dead_fish VARCHAR(20) DEFAULT 'No',
                additional_observation TEXT NULL,
                image_path VARCHAR(500) NOT NULL,
                image_hash VARCHAR(64) NOT NULL,
                status ENUM('Not Watched', 'In Process', 'Submitted') NOT NULL DEFAULT 'Submitted',
                is_demo TINYINT(1) DEFAULT 0,
                ai_analysis LONGTEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_reports_user_id (user_id),
                INDEX idx_reports_status (status),
                INDEX idx_reports_created_at (created_at),
                INDEX idx_reports_coords (latitude, longitude),
                INDEX idx_reports_image_hash (image_hash),
                CONSTRAINT fk_reports_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Ensure ai_analysis column exists in case reports table was created previously without it
            cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'reports' AND COLUMN_NAME = 'ai_analysis';
            """, (MYSQL_DB,))
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE reports ADD COLUMN ai_analysis LONGTEXT NULL AFTER is_demo;")

            # 3. votes table (Community corroboration)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                report_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_user_report (user_id, report_id),
                INDEX idx_votes_report_id (report_id),
                CONSTRAINT fk_votes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_votes_report FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 4. validations table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS validations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                report_id INT NULL,
                file_valid TINYINT(1) DEFAULT 1,
                duplicate_check TINYINT(1) DEFAULT 1,
                image_suitability TINYINT(1) DEFAULT 1,
                location_check TINYINT(1) DEFAULT 1,
                missing_fields TEXT NULL,
                validation_message TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_validations_report_id (report_id),
                CONSTRAINT fk_validations_report FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

    finally:
        conn.close()

def get_user_by_email(email):
    """Retrieve user record by email address."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
            return cursor.fetchone()
    finally:
        conn.close()

def get_user_by_id(user_id):
    """Retrieve user record by user ID."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cursor.fetchone()
    finally:
        conn.close()

def create_user(name, email, password_hash):
    """Register a new user in MySQL database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name.strip(), email.strip().lower(), password_hash)
            )
            return cursor.lastrowid
    finally:
        conn.close()

def create_report(user_id, water_body_name, water_body_type, latitude, longitude,
                  water_colour, smell, algae, visible_waste, water_appearance,
                  dead_fish, additional_observation, image_path, image_hash,
                  status="Submitted", is_demo=0, ai_analysis=None):
    """Insert a new water body report into MySQL."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                INSERT INTO reports (
                    user_id, water_body_name, water_body_type, latitude, longitude,
                    water_colour, smell, algae, visible_waste, water_appearance,
                    dead_fish, additional_observation, image_path, image_hash, status, is_demo, ai_analysis
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
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
                is_demo,
                ai_analysis
            ))
            return cursor.lastrowid
    finally:
        conn.close()

def save_report_ai_analysis(report_id, ai_analysis_json):
    """Save or update cached Gemini AI analysis for a report."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE reports SET ai_analysis = %s WHERE id = %s",
                (ai_analysis_json, report_id)
            )
            return cursor.rowcount > 0
    finally:
        conn.close()

def save_validation(report_id, file_valid, duplicate_check, image_suitability, location_check, missing_fields, validation_message):
    """Log validation record in MySQL database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO validations (
                    report_id, file_valid, duplicate_check, image_suitability, location_check, missing_fields, validation_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                report_id,
                1 if file_valid else 0,
                1 if duplicate_check else 0,
                1 if image_suitability else 0,
                1 if location_check else 0,
                missing_fields,
                validation_message
            ))
            return cursor.lastrowid
    finally:
        conn.close()

def _format_row(row):
    """Format row dictionary for template consumption (float coordinates, string dates)."""
    if not row:
        return row
    d = dict(row)
    if 'latitude' in d and d['latitude'] is not None:
        d['latitude'] = float(d['latitude'])
    if 'longitude' in d and d['longitude'] is not None:
        d['longitude'] = float(d['longitude'])
    if isinstance(d.get('created_at'), datetime):
        d['created_at'] = d['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    elif d.get('created_at') is not None:
        d['created_at'] = str(d['created_at'])
    if isinstance(d.get('updated_at'), datetime):
        d['updated_at'] = d['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
    elif d.get('updated_at') is not None:
        d['updated_at'] = str(d['updated_at'])
    return d

def get_report_by_id(report_id):
    """Get single report along with vote count and submitter name from MySQL."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT r.*, u.name AS submitter_name,
                       (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
                FROM reports r
                JOIN users u ON r.user_id = u.id
                WHERE r.id = %s
            """
            cursor.execute(query, (report_id,))
            report = cursor.fetchone()
            return _format_row(report)
    finally:
        conn.close()

def delete_report(report_id, user_id=None):
    """
    Delete a report if the requesting user is the owner (or user_id is None for admin).
    Removes uploaded photo file and related rows.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if user_id:
                cursor.execute(
                    "SELECT id, image_path, user_id FROM reports WHERE id = %s AND user_id = %s",
                    (report_id, user_id)
                )
            else:
                cursor.execute(
                    "SELECT id, image_path, user_id FROM reports WHERE id = %s",
                    (report_id,)
                )
            report = cursor.fetchone()

            if not report:
                return False

            cursor.execute("DELETE FROM votes WHERE report_id = %s", (report_id,))
            cursor.execute("DELETE FROM validations WHERE report_id = %s", (report_id,))
            cursor.execute("DELETE FROM reports WHERE id = %s", (report_id,))

        # Clean up image file on disk if not a demo image
        try:
            img_path = report.get('image_path')
            if img_path and not img_path.startswith('uploads/demo_'):
                full_path = os.path.join(BASE_DIR, img_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
        except Exception:
            pass

        return True
    finally:
        conn.close()

def get_reports_by_user(user_id):
    """Retrieve all reports submitted by a specific user from MySQL."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT r.*,
                       (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
                FROM reports r
                WHERE r.user_id = %s
                ORDER BY r.created_at DESC
            """
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
            return [_format_row(r) for r in rows]
    finally:
        conn.close()

def get_community_reports():
    """Retrieve all submitted reports for community viewing."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT r.*, u.name AS submitter_name,
                       (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
                FROM reports r
                JOIN users u ON r.user_id = u.id
                WHERE r.status = 'Submitted'
                ORDER BY r.created_at DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            return [_format_row(r) for r in rows]
    finally:
        conn.close()

def get_analysis_board_reports():
    """Retrieve reports grouped by workflow statuses: Not Watched, In Process, Submitted."""
    conn = get_db_connection()
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

            grouped = {
                'Not Watched': [],
                'In Process': [],
                'Submitted': []
            }
            for r in all_reports:
                formatted = _format_row(r)
                status = formatted['status']
                if status in grouped:
                    grouped[status].append(formatted)
                else:
                    grouped['Not Watched'].append(formatted)
            return grouped
    finally:
        conn.close()

def update_report_status(report_id, new_status):
    """Update report workflow review status ('Not Watched', 'In Process', 'Submitted')."""
    valid_statuses = ('Not Watched', 'In Process', 'Submitted')
    if new_status not in valid_statuses:
        return False
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE reports SET status = %s WHERE id = %s",
                (new_status, report_id)
            )
            return cursor.rowcount > 0
    finally:
        conn.close()

def get_all_image_hashes():
    """Return list of (id, image_hash) to check for duplicate photos."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, image_hash FROM reports WHERE image_hash IS NOT NULL AND image_hash != ''")
            rows = cursor.fetchall()
            return [(row['id'], row['image_hash']) for row in rows]
    finally:
        conn.close()

def check_duplicate_report(lat, lon, water_body_name=None, max_distance_meters=300):
    """
    Check if a report already exists near the same coordinates (within ~300m)
    OR with the same water body name on the current date.
    Strictly used to prevent duplicate report submissions.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Query reports created today in MySQL
            today_str = datetime.now().strftime('%Y-%m-%d')
            query = """
                SELECT id, water_body_name, latitude, longitude, created_at, status
                FROM reports
                WHERE DATE(created_at) = DATE(%s)
            """
            cursor.execute(query, (today_str,))
            rows = cursor.fetchall()

        duplicates = []
        lat = float(lat)
        lon = float(lon)

        for row in rows:
            r_lat = float(row['latitude'])
            r_lon = float(row['longitude'])

            # Haversine distance
            dlat = math.radians(r_lat - lat)
            dlon = math.radians(r_lon - lon)
            a = (math.sin(dlat / 2.0) ** 2 +
                 math.cos(math.radians(lat)) * math.cos(math.radians(r_lat)) *
                 math.sin(dlon / 2.0) ** 2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            dist_m = 6371000 * c

            name_match = False
            if water_body_name and row.get('water_body_name'):
                wb_clean = water_body_name.strip().lower()
                row_wb_clean = row['water_body_name'].strip().lower()
                if wb_clean and row_wb_clean and (wb_clean == row_wb_clean or (len(wb_clean) >= 4 and wb_clean in row_wb_clean)):
                    name_match = True

            if dist_m <= max_distance_meters or name_match:
                duplicates.append({
                    'id': row['id'],
                    'water_body_name': row['water_body_name'] or "Unnamed Water Body",
                    'distance_meters': round(dist_m),
                    'created_at': str(row['created_at']),
                    'status': row['status'],
                    'reason': "Same water body name reported today" if name_match else f"Located within {round(dist_m)}m of existing report"
                })
        return duplicates
    finally:
        conn.close()

def has_user_voted(user_id, report_id):
    """Check if the user has already voted on this report."""
    if not user_id:
        return False
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM votes WHERE user_id = %s AND report_id = %s",
                (user_id, report_id)
            )
            return cursor.fetchone() is not None
    finally:
        conn.close()

def toggle_vote(user_id, report_id):
    """
    Add or remove a community confirmation vote in MySQL.
    Returns: (voted_now: bool, total_votes: int)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM votes WHERE user_id = %s AND report_id = %s",
                (user_id, report_id)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("DELETE FROM votes WHERE id = %s", (existing['id'],))
                voted_now = False
            else:
                cursor.execute("INSERT INTO votes (user_id, report_id) VALUES (%s, %s)", (user_id, report_id))
                voted_now = True

            cursor.execute("SELECT COUNT(*) AS cnt FROM votes WHERE report_id = %s", (report_id,))
            total_votes = cursor.fetchone()['cnt']
            return voted_now, total_votes
    finally:
        conn.close()
