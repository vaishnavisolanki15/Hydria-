# Hydria

**From Citizen Observations to Water Insights.**

---

### Problem

Citizens frequently notice pollution, algal blooms, or severe degradation in urban freshwater bodies (lakes, ponds, streams, canals), but collecting, verifying, and interpreting these observations can be challenging and inaccessible. Most official reporting channels require complex forms or return no immediate feedback to the citizen.

### Solution

**Hydria** provides a streamlined, beginner-friendly citizen reporting workflow and converts raw sensory observations into clear, understandable environmental insights. By integrating automated browser geolocation, local image verification, duplicate detection, and a community confirmation system, Hydria turns citizen observations into actionable community data.

---

### Tracks

* **Primary:** Track 1 — Citizen Science UX
* **Secondary:** Track 2 — Data-to-Insight

---

### Technology Stack

* **Backend:** Python & Flask
* **Frontend:** Clean HTML5, Vanilla CSS, Vanilla JavaScript
* **Database:** SQLite (`hydria.db`)
* **Image Processing & Perceptual Hashing:** Pillow (PIL)
* **Security:** Werkzeug password hashing (`generate_password_hash`, `check_password_hash`)
* **Zero External AI / Cloud API Dependencies:** Runs completely offline and locally without API keys.

---

### Key Features

1. **User Authentication & Session Management:** Simple, secure registration and login using industry-standard password hashing.
2. **Automatic Browser Geolocation:** Detects GPS coordinates (`navigator.geolocation`) without requiring complicated manual address typing.
3. **Step-by-Step Reporting Journey:**
   - Step 1: Location & Water Observations (colour, odor, algae, waste, appearance, dead wildlife).
   - Step 2: Photo Evidence Upload with immediate client-side preview.
   - Step 3: Automated local Hydria Report Check & verification.
4. **Hydria Local Validation Engine (`image_validator.py`):**
   - **Check 1 — File Validity:** Format verification (JPG, PNG, WEBP), file integrity, and 5MB size limit.
   - **Check 2 — Perceptual Duplicate Image Detection:** Calculates a 64-bit difference hash (dHash) with Hamming distance comparison to prevent identical or re-uploaded photos.
   - **Check 3 — Local Photo Suitability Heuristic:** Analyzes dominant natural palettes, luminance, and checks for obvious blank/overexposed images or portrait/selfie patterns.
   - **Check 4 — Photo EXIF GPS Comparison:** Compares photo EXIF metadata against reported coordinates (within ~200m).
5. **Duplicate Report Advisory:** Alerts user if a similar report already exists nearby on the same day.
6. **Observation-Based Insight Engine (`analysis_engine.py`):** Translates visual and olfactory observations into rule-based, community-friendly water insights with concern levels and recommendations.
7. **Community Reports & Confirmation Voting:** View submitted reports and confirm observations using `"👍 I observed this too"`, with duplicate-vote prevention.
8. **Analysis Board:** 3-column workflow status tracker (`Not Watched`, `In Process`, `Submitted`) with responsive mobile stacking.
9. **Pre-Seeded Demo Dataset:** 8 realistic urban water reports with generated sample imagery for hackathon and presentation demonstrations.

---

### Quick Start Guide

#### 1. Install Dependencies

Ensure Python 3.10+ is installed:

```bash
pip install -r requirements.txt
```

#### 2. Run the Application

```bash
python app.py
```

The database and demo dataset will automatically initialize if not already present.

#### 3. Open in Browser

Navigate to:

```text
http://127.0.0.1:5000
```

---

### Demo Accounts

You can log in immediately with one of the pre-seeded accounts:

* **Email:** `vaishnavi@example.com`
* **Password:** `password123`

Or create a new account via the `/register` page.

---

### MVP Architecture

```text
Hydria Project/
├── app.py                 # Core Flask application and route handlers
├── database.py            # SQLite schema, queries, and vote transactions
├── analysis_engine.py     # Local rule-based observation insight engine
├── image_validator.py     # Local image validation, dHash, and EXIF extraction
├── seed_demo.py           # Demo dataset & realistic water sample generator
├── requirements.txt       # Minimal Python package requirements
├── hydria.db              # SQLite database (auto-generated)
├── templates/
│   ├── base.html          # Responsive base layout & navigation
│   ├── login.html         # Login interface
│   ├── register.html      # User registration
│   ├── dashboard.html     # User dashboard & "My Reports"
│   ├── report.html        # Step-by-step reporting form
│   ├── validation.html    # Hydria automated report check
│   ├── submit_success.html# Final submission confirmation
│   ├── community.html     # Community reports view
│   ├── analysis_board.html# 3-column review status board
│   ├── report_detail.html # Detailed report & Hydria Insights
│   └── error.html         # Friendly error handling
├── static/
│   ├── css/style.css      # Aquatic design system & responsiveness
│   ├── js/location.js     # Geolocation, preview, & AJAX voting
│   └── images/            # Static assets & placeholder fallback
└── uploads/               # Stored water observation images
```

---

### Testing the Complete MVP Flow

To verify all requirements from the specification:

1. **Register:** Go to `/register`, create an account with a 6+ character password.
2. **Login:** Log in with your new credentials.
3. **Report:** Click `+ Report Water Body`.
4. **Location:** Browser detects latitude/longitude automatically.
5. **Fill Observations:** Select water colour, smell, algae, waste level, and water appearance.
6. **Upload Photo:** Attach an image and view the instant preview.
7. **Verify:** Click `Check & Verify Report` to view the Hydria verification checklist.
8. **Submit:** Click `Submit Report` to confirm submission.
9. **View in Community & Board:** Verify the report appears in `/community` and on the `/analysis-board`.
10. **Vote:** Test the `👍 I observed this too` community confirmation button. Duplicate votes are prevented.
11. **Duplicate Photo Detection:** Try uploading the same photo again in a new report to trigger the duplicate image warning.
