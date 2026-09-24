import os
import math
from PIL import Image, ImageDraw, ImageFilter
from werkzeug.security import generate_password_hash
from database import get_db_connection, init_db
from image_validator import compute_dhash

def generate_sample_water_image(file_path, base_color_type="green", title="Water Body", wave_seed=0):
    """
    Generate realistic, stylized water observation photo sample using Pillow.
    Creates layered ripples, natural gradients, reflections, and subtle textures.
    """
    dirname = os.path.dirname(file_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    width, height = 640, 480
    img = Image.new('RGB', (width, height), (30, 45, 60))
    draw = ImageDraw.Draw(img)

    # Color palette configurations based on water condition
    palettes = {
        "green": {
            "top": (40, 90, 70),
            "mid": (35, 120, 80),
            "deep": (20, 75, 50),
            "ripple": (60, 160, 100),
            "bank": (70, 60, 45)
        },
        "dark_green": {
            "top": (25, 60, 45),
            "mid": (15, 75, 45),
            "deep": (10, 45, 30),
            "ripple": (35, 110, 65),
            "bank": (50, 45, 35)
        },
        "brown": {
            "top": (100, 75, 50),
            "mid": (120, 85, 55),
            "deep": (75, 50, 30),
            "ripple": (145, 105, 70),
            "bank": (60, 45, 30)
        },
        "black": {
            "top": (35, 35, 40),
            "mid": (25, 25, 30),
            "deep": (15, 15, 20),
            "ripple": (55, 55, 60),
            "bank": (40, 40, 40)
        },
        "clear": {
            "top": (70, 130, 180),
            "mid": (40, 150, 200),
            "deep": (20, 90, 140),
            "ripple": (120, 200, 240),
            "bank": (90, 80, 65)
        },
        "yellowish": {
            "top": (120, 120, 60),
            "mid": (140, 130, 65),
            "deep": (80, 80, 40),
            "ripple": (160, 150, 85),
            "bank": (75, 65, 50)
        }
    }
    
    p = palettes.get(base_color_type, palettes["green"])
    
    # 1. Background gradient (water surface perspective)
    for y in range(height):
        ratio = y / height
        r = int(p["top"][0] * (1 - ratio) + p["deep"][0] * ratio)
        g = int(p["top"][1] * (1 - ratio) + p["deep"][1] * ratio)
        b = int(p["top"][2] * (1 - ratio) + p["deep"][2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. Draw water ripples and waves
    for wave_y in range(120, height, 24):
        amplitude = 4 + (wave_y / height) * 6
        points = []
        for x in range(0, width + 10, 20):
            y_offset = math.sin((x + wave_y * 3 + wave_seed) * 0.04) * amplitude
            points.append((x, wave_y + y_offset))
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=p["ripple"], width=2)

    # 3. Draw shoreline / bank edge at the top
    bank_points = [(0, 0), (width, 0), (width, 80)]
    for x in range(width, -10, -30):
        bank_y = 65 + math.sin(x * 0.03) * 15
        bank_points.append((x, bank_y))
    bank_points.append((0, 80))
    draw.polygon(bank_points, fill=p["bank"])

    # 4. Blur slightly for photographic feel
    blurred = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    blurred.save(file_path, "JPEG", quality=85)
    return file_path

def seed_database():
    """Populate initial demo users, reports, and votes."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if demo data already seeded
    existing = cursor.execute("SELECT COUNT(*) as cnt FROM reports WHERE is_demo = 1").fetchone()
    if existing['cnt'] > 0:
        print(f"Database already contains {existing['cnt']} demo reports. Skipping re-seed.")
        conn.close()
        return

    print("Seeding demo users and reports...")
    
    # 1. Create demo users
    hashed_pwd = generate_password_hash("password123")
    demo_users = [
        ("Vaishnavi Sharma", "vaishnavi@example.com"),
        ("Arjun Patel", "arjun@example.com"),
        ("Priya Nair", "priya@example.com"),
        ("Rohan Verma", "rohan@example.com"),
        ("Ananya Rao", "ananya@example.com")
    ]

    user_ids = []
    for name, email in demo_users:
        user = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            user_ids.append(user['id'])
        else:
            cursor.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                           (name, email, hashed_pwd))
            user_ids.append(cursor.lastrowid)

    conn.commit()

    # 2. Demo reports specification
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    demo_reports = [
        {
            "user_idx": 0,
            "name": "City Lake",
            "type": "Lake",
            "lat": 22.7196,
            "lon": 75.8577,
            "colour": "Green",
            "smell": "Bad smell",
            "algae": "Yes",
            "waste": "High",
            "appearance": "Dirty",
            "dead_fish": "No",
            "observation": "Heavy green surface layer near the eastern inlet with discarded plastic packaging.",
            "color_type": "green",
            "status": "Submitted",
            "votes": 14
        },
        {
            "user_idx": 1,
            "name": "Green Lake",
            "type": "Lake",
            "lat": 22.7250,
            "lon": 75.8650,
            "colour": "Dark Green",
            "smell": "Sewage-like smell",
            "algae": "Yes",
            "waste": "Medium",
            "appearance": "Very Dirty",
            "dead_fish": "No",
            "observation": "Dense algal bloom covering nearly half the lake bay; strong stagnant sewage odor.",
            "color_type": "dark_green",
            "status": "Submitted",
            "votes": 8
        },
        {
            "user_idx": 2,
            "name": "City Pond",
            "type": "Pond",
            "lat": 22.7150,
            "lon": 75.8500,
            "colour": "Brown",
            "smell": "Bad smell",
            "algae": "No",
            "waste": "Medium",
            "appearance": "Dirty",
            "dead_fish": "No",
            "observation": "Silt and stormwater runoff discoloration after recent municipal pipeline digging nearby.",
            "color_type": "brown",
            "status": "In Process",
            "votes": 5
        },
        {
            "user_idx": 3,
            "name": "North Canal Drainage",
            "type": "Canal",
            "lat": 22.7310,
            "lon": 75.8420,
            "colour": "Black",
            "smell": "Chemical smell",
            "algae": "Yes",
            "waste": "High",
            "appearance": "Very Dirty",
            "dead_fish": "Yes",
            "observation": "Extremely dark discharge with noticeable chemical fumes. Two dead small fish spotted floating near culvert.",
            "color_type": "black",
            "status": "In Process",
            "votes": 19
        },
        {
            "user_idx": 0,
            "name": "Willow Stream",
            "type": "Stream",
            "lat": 22.7400,
            "lon": 75.8700,
            "colour": "Clear",
            "smell": "No unusual smell",
            "algae": "No",
            "waste": "None",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Water looks naturally clear with pebbles visible on stream bed. Upstream flow seems healthy.",
            "color_type": "clear",
            "status": "Submitted",
            "votes": 12
        },
        {
            "user_idx": 4,
            "name": "Sunset Wetland Pond",
            "type": "Pond",
            "lat": 22.7050,
            "lon": 75.8300,
            "colour": "Yellowish",
            "smell": "Rotten smell",
            "algae": "Yes",
            "waste": "Low",
            "appearance": "Unusual",
            "dead_fish": "No",
            "observation": "Yellowish sediment foam along reed banks. Smells like rotting marsh vegetation.",
            "color_type": "yellowish",
            "status": "Not Watched",
            "votes": 2
        },
        {
            "user_idx": 1,
            "name": "East Industrial River Bend",
            "type": "River",
            "lat": 22.7520,
            "lon": 75.8910,
            "colour": "Brown",
            "smell": "Chemical smell",
            "algae": "Not sure",
            "waste": "High",
            "appearance": "Very Dirty",
            "dead_fish": "Yes",
            "observation": "Foamy brown runoff trailing down from northern storm drain. Several dead minnows observed.",
            "color_type": "brown",
            "status": "Not Watched",
            "votes": 4
        },
        {
            "user_idx": 2,
            "name": "Botanical Garden Lily Pond",
            "type": "Pond",
            "lat": 22.7210,
            "lon": 75.8750,
            "colour": "Green",
            "smell": "No unusual smell",
            "algae": "Yes",
            "waste": "Low",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Natural pond weed and duckweed surface coverage, typical seasonal lily growth.",
            "color_type": "green",
            "status": "Submitted",
            "votes": 7
        }
    ]

    for i, r in enumerate(demo_reports):
        # Generate demo image
        filename = f"demo_report_{i+1}.jpg"
        full_img_path = os.path.join(uploads_dir, filename)
        generate_sample_water_image(full_img_path, base_color_type=r["color_type"], title=r["name"])
        
        # Calculate dHash
        with Image.open(full_img_path) as img:
            img_hash = compute_dhash(img) or f"demohash_{i+1:08x}"
            
        rel_img_path = f"uploads/{filename}"
        u_id = user_ids[r["user_idx"]]

        cursor.execute("""
            INSERT INTO reports (
                user_id, water_body_name, water_body_type, latitude, longitude,
                water_colour, smell, algae, visible_waste, water_appearance,
                dead_fish, additional_observation, image_path, image_hash, status, is_demo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            u_id, r["name"], r["type"], r["lat"], r["lon"],
            r["colour"], r["smell"], r["algae"], r["waste"], r["appearance"],
            r["dead_fish"], r["observation"], rel_img_path, img_hash, r["status"]
        ))
        report_id = cursor.lastrowid

        # Seed votes
        vote_count = r["votes"]
        # Seed up to vote_count votes from random or available users
        voter_user_ids = list(user_ids)
        # If vote_count > available users, make extra mock user IDs if needed or cycle
        for v_idx in range(min(vote_count, len(voter_user_ids))):
            try:
                cursor.execute("INSERT OR IGNORE INTO votes (user_id, report_id) VALUES (?, ?)",
                               (voter_user_ids[v_idx], report_id))
            except Exception:
                pass

        # Log validation entry
        cursor.execute("""
            INSERT INTO validations (
                report_id, file_valid, duplicate_check, image_suitability, location_check, missing_fields, validation_message
            ) VALUES (?, 1, 1, 1, 1, '', 'Validated during report intake')
        """, (report_id,))

    conn.commit()
    conn.close()
    print("Demo dataset seeded successfully!")

if __name__ == '__main__':
    seed_database()
