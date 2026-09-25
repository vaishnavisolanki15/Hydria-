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
        # --- HIGH RISK (4 reports - Dirty water bodies) ---
        {
            "user_idx": 0,
            "name": "Bellandur Lake",
            "type": "Lake",
            "lat": 12.9360,
            "lon": 77.6680,
            "colour": "Dark Green",
            "smell": "Sewage-like smell",
            "algae": "Yes",
            "waste": "High",
            "appearance": "Very Dirty",
            "dead_fish": "Yes",
            "observation": "Heavy toxic chemical froth and severe eutrophication spillage at outflow. Strong stagnant sewage odor.",
            "color_type": "dark_green",
            "status": "Submitted",
            "votes": 19
        },
        {
            "user_idx": 1,
            "name": "Mithi River (CST Road)",
            "type": "River",
            "lat": 19.0688,
            "lon": 72.8700,
            "colour": "Black",
            "smell": "Chemical smell",
            "algae": "No",
            "waste": "High",
            "appearance": "Very Dirty",
            "dead_fish": "No",
            "observation": "Heavy accumulation of floating single-use plastic waste, industrial chemical drainage, and dark anaerobic sludge.",
            "color_type": "black",
            "status": "In Process",
            "votes": 14
        },
        {
            "user_idx": 2,
            "name": "Najafgarh Industrial Drain",
            "type": "Canal",
            "lat": 28.6120,
            "lon": 77.0140,
            "colour": "Brown",
            "smell": "Chemical smell",
            "algae": "No",
            "waste": "High",
            "appearance": "Very Dirty",
            "dead_fish": "No",
            "observation": "Plastic bottles, styrofoam packaging, and industrial chemical wastewater clogging urban waterway.",
            "color_type": "brown",
            "status": "Submitted",
            "votes": 11
        },
        {
            "user_idx": 3,
            "name": "Yamuna River (Nigambodh Ghat)",
            "type": "River",
            "lat": 28.6653,
            "lon": 77.2346,
            "colour": "Brown",
            "smell": "Bad smell",
            "algae": "No",
            "waste": "High",
            "appearance": "Dirty",
            "dead_fish": "Yes",
            "observation": "High turbidity, heavy domestic organic debris, and untreated urban sewage discharge along the ghat.",
            "color_type": "brown",
            "status": "Not Watched",
            "votes": 8
        },

        # --- MEDIUM RISK (7 reports - Moderate concern) ---
        {
            "user_idx": 0,
            "name": "Yamuna River (Kalindi Kunj)",
            "type": "River",
            "lat": 28.5447,
            "lon": 77.3090,
            "colour": "Brown",
            "smell": "Bad smell",
            "algae": "No",
            "waste": "Low",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Surfactant froth clusters observed near the barrage with seasonal silt sedimentation.",
            "color_type": "brown",
            "status": "Submitted",
            "votes": 13
        },
        {
            "user_idx": 1,
            "name": "Kshipra River (Ram Ghat)",
            "type": "River",
            "lat": 23.1827,
            "lon": 75.7682,
            "colour": "Brown",
            "smell": "No unusual smell",
            "algae": "No",
            "waste": "Medium",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Turbid silt water carrying ritual organic material and temple ghat runoff.",
            "color_type": "brown",
            "status": "Submitted",
            "votes": 10
        },
        {
            "user_idx": 2,
            "name": "East Industrial River Bend",
            "type": "River",
            "lat": 19.0912,
            "lon": 72.8944,
            "colour": "Green",
            "smell": "No unusual smell",
            "algae": "Yes",
            "waste": "Low",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Greenish algae discoloration and slight odor along the inner river bend.",
            "color_type": "green",
            "status": "Not Watched",
            "votes": 4
        },
        {
            "user_idx": 3,
            "name": "Bilawali Lake Shore",
            "type": "Lake",
            "lat": 22.6841,
            "lon": 75.8752,
            "colour": "Green",
            "smell": "No unusual smell",
            "algae": "Yes",
            "waste": "Low",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Localized surface algae growth along shallow eastern lake shore with packaging debris.",
            "color_type": "green",
            "status": "Submitted",
            "votes": 7
        },
        {
            "user_idx": 4,
            "name": "Mahalakshmi Pond",
            "type": "Pond",
            "lat": 22.7548,
            "lon": 75.8950,
            "colour": "Yellowish",
            "smell": "No unusual smell",
            "algae": "Yes",
            "waste": "Low",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Stagnant pond with duckweed mats and seasonal organic discoloration.",
            "color_type": "yellowish",
            "status": "Submitted",
            "votes": 6
        },
        {
            "user_idx": 0,
            "name": "North Canal Drainage",
            "type": "Canal",
            "lat": 22.7680,
            "lon": 75.8450,
            "colour": "Brown",
            "smell": "Chemical smell",
            "algae": "No",
            "waste": "None",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Concrete drainage channel showing discoloration and slight chemical odor.",
            "color_type": "brown",
            "status": "In Process",
            "votes": 5
        },
       

        # --- LOW RISK (4 reports - Clean water bodies) ---
        {
            "user_idx": 2,
            "name": "Umngot River (Dawki)",
            "type": "River",
            "lat": 25.1950,
            "lon": 92.0194,
            "colour": "Clear",
            "smell": "No unusual smell",
            "algae": "No",
            "waste": "None",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Pristine transparent riverbed, underwater pebbles visible at 15ft depth, zero waste, perfectly clear.",
            "color_type": "clear",
            "status": "Submitted",
            "votes": 25
        },
        {
            "user_idx": 3,
            "name": "Dal Lake (Hazratbal Basin)",
            "type": "Lake",
            "lat": 34.1260,
            "lon": 74.8430,
            "colour": "Clear",
            "smell": "No unusual smell",
            "algae": "No",
            "waste": "Low",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Clean mirror-like water surface reflecting Himalayan peaks, healthy lotus beds, well preserved.",
            "color_type": "clear",
            "status": "Submitted",
            "votes": 18
        },
        {
            "user_idx": 4,
            "name": "Lake Pichola",
            "type": "Lake",
            "lat": 24.5764,
            "lon": 73.6800,
            "colour": "Clear",
            "smell": "No unusual smell",
            "algae": "No",
            "waste": "Low",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Clear historic lake water surrounding City Palace and Jagmandir, active municipal lake conservation.",
            "color_type": "clear",
            "status": "Submitted",
            "votes": 16
        },
        {
            "user_idx": 0,
            "name": "Pangong Tso",
            "type": "Lake",
            "lat": 33.7595,
            "lon": 78.6674,
            "colour": "Clear",
            "smell": "No unusual smell",
            "algae": "No",
            "waste": "None",
            "appearance": "Normal",
            "dead_fish": "No",
            "observation": "Pristine high-altitude turquoise lake with 100% water clarity, zero floating debris or contamination.",
            "color_type": "clear",
            "status": "Submitted",
            "votes": 22
        }
    ]

    photo_map = {
        "Bellandur Lake": "real_bellandur_lake.jpg",
        "Mithi River (CST Road)": "real_mithi_river.jpg",
        "Najafgarh Industrial Drain": "real_bali_polluted_river.jpg",
        "Yamuna River (Nigambodh Ghat)": "real_yamuna_delhi.jpg",
        "Yamuna River (Kalindi Kunj)": "real_yamuna_delhi.jpg",
        "Kshipra River (Ram Ghat)": "photo_river_ghat.jpg",
        "East Industrial River Bend": "real_mithi_river.jpg",
        "Bilawali Lake Shore": "real_bellandur_lake.jpg",
        "Mahalakshmi Pond": "photo_lily_pond.jpg",
        "North Canal Drainage": "real_bali_polluted_river.jpg",
        "Umngot River (Dawki)": "real_dawki_river.jpg",
        "Dal Lake (Hazratbal Basin)": "real_dal_lake.jpg",
        "Lake Pichola": "real_lake_pichola.jpg",
        "Pangong Tso": "real_pangong_tso.jpg",
    }

    for i, r in enumerate(demo_reports):
        photo_filename = photo_map.get(r["name"])
        if photo_filename and os.path.exists(os.path.join(uploads_dir, photo_filename)):
            rel_img_path = f"uploads/{photo_filename}"
            full_img_path = os.path.join(uploads_dir, photo_filename)
        else:
            filename = f"demo_report_{i+1}.jpg"
            full_img_path = os.path.join(uploads_dir, filename)
            generate_sample_water_image(full_img_path, base_color_type=r["color_type"], title=r["name"])
            rel_img_path = f"uploads/{filename}"

        # Calculate dHash
        with Image.open(full_img_path) as img:
            img_hash = compute_dhash(img) or f"demohash_{i+1:08x}"
            
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
