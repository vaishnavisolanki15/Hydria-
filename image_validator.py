import os
import math
import json
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))
from PIL import Image, ImageStat
from PIL.ExifTags import TAGS, GPSTAGS

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

def compute_dhash(image, hash_size=8):
    """
    Compute a 64-bit difference hash (dHash) using Pillow.
    dHash is an efficient perceptual hash resilient to minor scaling, compression, and brightness changes.
    """
    try:
        # Resize to (hash_size + 1, hash_size) and convert to grayscale
        resized = image.convert('L').resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        if hasattr(resized, 'get_flattened_data'):
            pixels = list(resized.get_flattened_data())
        else:
            pixels = list(resized.getdata())
        
        # Compare adjacent pixels in each row
        difference = []
        for row in range(hash_size):
            for col in range(hash_size):
                pixel_left = pixels[row * (hash_size + 1) + col]
                pixel_right = pixels[row * (hash_size + 1) + col + 1]
                difference.append(pixel_left > pixel_right)
                
        # Convert boolean list to hexadecimal string
        decimal_val = 0
        hex_string = []
        for index, value in enumerate(difference):
            if value:
                decimal_val += 2 ** (index % 4)
            if index % 4 == 3:
                hex_string.append(hex(decimal_val)[2:])
                decimal_val = 0
        return ''.join(hex_string)
    except Exception:
        return None

def hamming_distance(hash1, hash2):
    """Calculate the Hamming distance between two hex hashes."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count('1')
    except Exception:
        return 999

def check_file_validity(file_path):
    """
    Check 1: Verify file exists, format is supported, image is not corrupted,
    and size is within 5MB limit.
    """
    if not os.path.exists(file_path):
        return False, "File does not exist on disk."
    
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False, "Uploaded file is empty (0 bytes)."
    if file_size > MAX_FILE_SIZE_BYTES:
        return False, f"File size ({file_size / (1024*1024):.2f} MB) exceeds the 5 MB limit."
    
    # Check extension
    ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported format (.{ext}). Allowed formats are JPG, JPEG, PNG, WEBP."
    
    # Verify image integrity with Pillow
    try:
        with Image.open(file_path) as img:
            img.verify()
        # Re-open to confirm full loading capability
        with Image.open(file_path) as img:
            img.load()
            w, h = img.size
            if w < 50 or h < 50:
                return False, f"Image dimensions ({w}x{h}) are too small for water observation."
        return True, "Image file is valid and readable."
    except Exception as e:
        return False, f"Image file is corrupted or cannot be processed: {str(e)}"

def check_duplicate_image(image_hash, existing_hashes, threshold=6):
    """
    Check 2: Compare perceptual hash with existing reports.
    If hamming distance is <= threshold (or exact match), it's strictly considered a duplicate.
    Duplicates are NOT allowed.
    """
    if not image_hash:
        return False, None
    for rep_id, ex_hash in existing_hashes:
        if not ex_hash:
            continue
        # Exact match
        if image_hash.strip().lower() == ex_hash.strip().lower():
            return True, rep_id
        # Perceptual hash match
        dist = hamming_distance(image_hash, ex_hash)
        if dist <= threshold:
            return True, rep_id
    return False, None

def validate_with_gemini_vision(image_input, water_body_name=None, water_body_type=None, latitude=None, longitude=None):
    """
    Classify uploaded image using Google Gemini Vision (gemini-flash-latest).
    Determines whether the photograph plausibly depicts the reported freshwater body/location
    or is an unrelated/unwanted image (selfies, portraits, indoor rooms, unrelated buildings,
    cars, computer screenshots, text documents, or non-water subjects).
    
    Returns structured dict:
    {'passed': bool, 'confidence': float, 'detected_subject': str, 'reason': str}
    or None on failure/offline.
    """
    # Skip remote API calls during automated unit test runs
    try:
        from flask import has_app_context, current_app
        if has_app_context() and current_app and current_app.config.get('TESTING'):
            return None
    except Exception:
        pass
    if os.getenv('TESTING') == 'True':
        return None

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        pil_img = None
        if isinstance(image_input, str):
            pil_img = Image.open(image_input)
        elif hasattr(image_input, 'convert'):
            pil_img = image_input
        else:
            return None

        loc_ctx = f"Coordinates: {latitude}, {longitude}" if (latitude and longitude) else "Coordinates: Not specified"
        name_ctx = f"Reported water body: {water_body_name}" if water_body_name else "Reported water body: Unnamed"
        type_ctx = f"Reported water body type: {water_body_type}" if water_body_type else "Reported type: Freshwater body"

        prompt = f"""You are the environmental photo validator for Hydria, a citizen science freshwater monitoring platform.
The user has submitted an environmental observation report:
- {name_ctx}
- {type_ctx}
- {loc_ctx}

Analyze the uploaded photograph to determine if it is relevant to this water body observation:

1. Does the image plausibly depict an outdoor freshwater body or its immediate shoreline/riparian/wetland environment (such as a lake, river, pond, stream, reservoir, canal, wetland, or storm runoff channel)?
2. Or is it an UNRELATED, UNWANTED, or INAPPROPRIATE image that clearly does NOT show the reported water observation, such as:
   - A selfie or people-focused portrait
   - An indoor room or indoor photograph
   - Unrelated buildings, architecture, or interior spaces
   - Cars, vehicles, traffic, or roads without a water body
   - A computer screen screenshot, application window, terminal, or phone screen
   - A document, receipt, diagram, chart, infographic, illustration, or meme
   - Random household objects or personal items
   - Dry, unrelated landscapes with no water body or wetland
   - Any photograph that clearly does not show an outdoor water/environmental observation.

Guidelines:
- Do NOT reject legitimate water-body photos simply because you cannot identify the specific named lake or river from visual appearance alone. If the photo plausibly shows a real outdoor water body or shoreline consistent with the report, it should PASS.
- If EXIF GPS is absent, evaluate visual environmental plausibility. Avoid false rejections of genuine water bodies.
- Reject photos that clearly depict non-water subjects, indoor scenes, selfies, cars, screenshots, or unrelated landscapes.

Return ONLY a valid JSON object in this format:
{{
    "passed": true or false,
    "confidence": float between 0.0 and 1.0,
    "detected_subject": "short description of what is depicted",
    "reason": "Clear explanation. If passed: 'Photo appears relevant to the reported water observation.' If rejected: 'This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.'"
}}
"""
        resp = None
        for model_name in ['gemini-flash-latest', 'gemini-2.5-flash']:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, pil_img]
                )
                if resp and resp.text:
                    break
            except Exception:
                continue
                
        if not resp or not resp.text:
            return None
            
        raw_text = resp.text.strip()
        if raw_text.startswith("```"):
            parts = raw_text.split("```")
            if len(parts) >= 2:
                raw_text = parts[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
        raw_text = raw_text.strip()
        
        data = json.loads(raw_text)
        passed = bool(data.get('passed', data.get('is_water_body', False)))
        confidence = float(data.get('confidence', 0.9)) if data.get('confidence') is not None else 0.9
        subject = str(data.get('detected_subject', '')).strip()
        reason = str(data.get('reason', data.get('rejection_reason', ''))).strip()

        if passed and not reason:
            reason = "Photo appears relevant to the reported water observation."
        elif not passed and not reason:
            reason = "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph."

        return {
            'passed': passed,
            'confidence': confidence,
            'detected_subject': subject,
            'reason': reason
        }
    except Exception as e:
        print(f"[ImageValidator] Gemini Vision check fallback: {e}")
        return None

def check_photo_suitability_and_relevance(image, file_path=None, water_body_name=None, water_body_type=None, browser_lat=None, browser_lon=None):
    """
    Validate photo suitability and visual water-body relevance.
    Evaluates:
    1. Gemini Vision analysis (when available) against reported water body context.
    2. Local computer vision heuristics for corrupt/blank/dark images, selfies/portraits,
       screenshots, documents, and natural water/environmental tone distribution.
    
    Returns structured dict:
    {
        'passed': bool,
        'status': 'pass' or 'fail',
        'title': 'Photo verification',
        'message': str,
        'reason': str,
        'confidence': float,
        'detected_subject': str,
        'is_warning': bool
    }
    """
    # 1. AI Vision Check via Gemini with observation context
    vision_input = file_path if file_path else image
    vision_result = validate_with_gemini_vision(
        vision_input,
        water_body_name=water_body_name,
        water_body_type=water_body_type,
        latitude=browser_lat,
        longitude=browser_lon
    )
    if vision_result is not None:
        passed = vision_result['passed']
        confidence = vision_result.get('confidence', 0.9)
        subject = vision_result.get('detected_subject', '')
        reason = vision_result.get('reason', '')
        
        if passed:
            user_msg = "Photo appears relevant to the reported water observation."
            return {
                'passed': True,
                'status': 'pass',
                'title': 'Photo verification',
                'message': user_msg,
                'reason': reason or user_msg,
                'confidence': confidence,
                'detected_subject': subject,
                'is_warning': False
            }
        else:
            user_msg = "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph."
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': user_msg,
                'reason': reason or user_msg,
                'confidence': confidence,
                'detected_subject': subject,
                'is_warning': False
            }

    # 2. Local Fallback Computer Vision Heuristics
    try:
        rgb_img = image.convert('RGB')
        w, h = rgb_img.size
        
        # Blank / uniform color detection using standard deviation
        stat = ImageStat.Stat(rgb_img)
        avg_stddev = sum(stat.stddev) / len(stat.stddev)
        if avg_stddev < 8.0:
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': "Image appears blank or has virtually no visual details.",
                'confidence': 0.95,
                'detected_subject': "Blank image",
                'is_warning': False
            }
        
        # Extreme brightness (completely pitch black or blown-out white)
        avg_mean = sum(stat.mean) / len(stat.mean)
        if avg_mean < 10.0:
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': "Image is completely dark/black. Please upload a visible photo taken with adequate lighting.",
                'confidence': 0.95,
                'detected_subject': "Dark image",
                'is_warning': False
            }
        if avg_mean > 250.0:
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': "Image is overexposed or solid white.",
                'confidence': 0.95,
                'detected_subject': "Overexposed image",
                'is_warning': False
            }
            
        # Analyze thumbnail for color distribution and screenshot detection
        thumb = rgb_img.resize((100, 100), Image.Resampling.BILINEAR)
        if hasattr(thumb, 'get_flattened_data'):
            pixels = list(thumb.get_flattened_data())
        else:
            pixels = list(thumb.getdata())
        total_pixels = len(pixels)
        
        # Center region portrait / selfie heuristic (middle 50% box)
        center_pixels = []
        for y in range(25, 75):
            for x in range(25, 75):
                center_pixels.append(thumb.getpixel((x, y)))
        
        skin_count = 0
        for r, g, b in center_pixels:
            if (r > 95 and g > 40 and b > 20 and 
                (max(r, g, b) - min(r, g, b)) > 15 and 
                abs(r - g) > 15 and r > g and r > b):
                skin_count += 1
                
        skin_ratio_center = skin_count / len(center_pixels)
        if skin_ratio_center > 0.50:
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': "The uploaded image appears to be a portrait or selfie rather than a water body.",
                'confidence': 0.90,
                'detected_subject': "Portrait / selfie",
                'is_warning': False
            }
            
        # Screenshot / UI / Document Detection:
        unique_colors = len(set(pixels))
        mono_pixels = 0
        natural_tones = 0
        for r, g, b in pixels:
            saturation = max(r, g, b) - min(r, g, b)
            # Monochromatic / grayscale / flat UI pixel
            if saturation < 15:
                mono_pixels += 1
            else:
                # Saturated natural tones (blues, greens, earth tones, dark water)
                is_blue = (b > r and (b > g or abs(b - g) < 30)) and b > 40
                is_green = (g > r and g > b) and g > 40
                is_earth = (r > g >= b) and (r - b < 90) and (r - b >= 15) and r > 40
                is_dark_water = (max(r, g, b) < 80 and min(r, g, b) > 15 and saturation >= 10)
                
                if is_blue or is_green or is_earth or is_dark_water:
                    natural_tones += 1

        mono_ratio = mono_pixels / total_pixels
        natural_ratio = natural_tones / total_pixels
        
        if unique_colors < 650 and mono_ratio > 0.65:
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': "Image appears to be a computer screenshot, text document, or UI capture.",
                'confidence': 0.92,
                'detected_subject': "Screenshot / digital document",
                'is_warning': False
            }
            
        if mono_ratio > 0.85:
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': "Image appears to be a document or screen capture (excessive monochrome content).",
                'confidence': 0.90,
                'detected_subject': "Document capture",
                'is_warning': False
            }
            
        if natural_ratio < 0.20:
            return {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': f"Image lacks natural outdoor water or environmental tones ({int(natural_ratio*100)}% detected).",
                'confidence': 0.85,
                'detected_subject': "Non-environmental image",
                'is_warning': False
            }
            
        return {
            'passed': True,
            'status': 'pass',
            'title': 'Photo verification',
            'message': "Photo appears relevant to the reported water observation.",
            'reason': "Photo appears relevant to the reported water observation.",
            'confidence': 0.85,
            'detected_subject': "Outdoor water environment",
            'is_warning': False
        }
            
    except Exception as e:
        return {
            'passed': True,
            'status': 'pass',
            'title': 'Photo verification',
            'message': "Photo appears relevant to the reported water observation.",
            'reason': f"Photo processed with basic verification: {str(e)}",
            'confidence': 0.70,
            'detected_subject': "Water observation",
            'is_warning': True
        }

def check_photo_suitability(image, file_path=None, water_body_name=None, water_body_type=None, browser_lat=None, browser_lon=None):
    """
    Check 3: AI Vision + local heuristic check for photo suitability.
    Returns: (is_suitable: bool, is_warning: bool, message: str)
    Maintained for backward compatibility.
    """
    res = check_photo_suitability_and_relevance(
        image,
        file_path=file_path,
        water_body_name=water_body_name,
        water_body_type=water_body_type,
        browser_lat=browser_lat,
        browser_lon=browser_lon
    )
    return res['passed'], res.get('is_warning', False), res['message']

def extract_exif_gps(image):
    """
    Check 4: Extract GPS coordinates from image EXIF metadata if present.
    Returns: (lat, lon) as floats or (None, None).
    """
    try:
        exif = image._getexif()
        if not exif:
            return None, None
            
        gps_info = {}
        for key, value in exif.items():
            decoded = TAGS.get(key, key)
            if decoded == "GPSInfo":
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = value[t]
                    
        if not gps_info:
            return None, None
            
        def _convert_to_degrees(value):
            """Helper to convert GPS degree/minute/second tuple to decimal degrees."""
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)

        gps_lat = gps_info.get('GPSLatitude')
        gps_lat_ref = gps_info.get('GPSLatitudeRef')
        gps_lon = gps_info.get('GPSLongitude')
        gps_lon_ref = gps_info.get('GPSLongitudeRef')
        
        if gps_lat and gps_lat_ref and gps_lon and gps_lon_ref:
            lat = _convert_to_degrees(gps_lat)
            if gps_lat_ref != 'N':
                lat = -lat
            lon = _convert_to_degrees(gps_lon)
            if gps_lon_ref != 'E':
                lon = -lon
            return lat, lon
            
    except Exception:
        pass
    return None, None

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lon coordinates."""
    r = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c

def validate_image_full(file_path, browser_lat, browser_lon, existing_hashes, water_body_name=None, water_body_type=None):
    """
    Run full Hydria Validation Engine pipeline:
    1. File validity
    2. Duplicate check (perceptual hash)
    3. Photo suitability & water body relevance (Gemini Vision + local heuristics)
    4. Location verification (EXIF coordinates compared against reported location when available)
    
    Returns a structured dictionary with pass/fail states and user-friendly messages.
    """
    # 1. File Validity
    valid, file_msg = check_file_validity(file_path)
    if not valid:
        return {
            'file_valid': False,
            'file_msg': file_msg,
            'duplicate_check': False,
            'duplicate_msg': "Skipped due to file error.",
            'image_suitability': False,
            'suitability_msg': "Skipped due to file error.",
            'photo_relevance': {
                'passed': False,
                'status': 'fail',
                'title': 'Photo verification',
                'message': "This photo does not appear to match the reported water observation. Please upload a relevant water-body photograph.",
                'reason': file_msg,
                'confidence': None,
                'detected_subject': None
            },
            'location_check': 'unavailable',
            'location_msg': "Skipped due to file error.",
            'image_hash': None,
            'ready_to_submit': False
        }
        
    # Open image for further checks
    with Image.open(file_path) as img:
        # 2. Duplicate Check
        img_hash = compute_dhash(img)
        is_dup, dup_rep_id = check_duplicate_image(img_hash, existing_hashes)
        if is_dup:
            dup_msg = f"Duplicate photo detected! This photo matches an existing submission (Report #{dup_rep_id}). Duplicate photos are strictly not allowed."
            duplicate_passed = False
        else:
            dup_msg = "Passed: Unique photo confirmed (no duplicates found)."
            duplicate_passed = True
            
        # 3. Photo Suitability & Water Body Relevance (AI Vision + Local CV)
        suit_res = check_photo_suitability_and_relevance(
            img,
            file_path=file_path,
            water_body_name=water_body_name,
            water_body_type=water_body_type,
            browser_lat=browser_lat,
            browser_lon=browser_lon
        )
        
        # 4. EXIF Location Verification
        exif_lat, exif_lon = extract_exif_gps(img)
        if exif_lat is not None and exif_lon is not None and browser_lat is not None and browser_lon is not None:
            dist = haversine_distance(browser_lat, browser_lon, exif_lat, exif_lon)
            if dist <= 300:
                loc_status = 'pass'
                loc_msg = f"Photo location verified near reported observation (within ~{int(dist)}m)."
            elif dist <= 5000:
                loc_status = 'warning'
                loc_msg = f"Photo location is approximately {int(dist)}m from the reported location."
            else:
                loc_status = 'warning'
                loc_msg = f"Photo location is approximately {int(dist / 1000)}km from the reported coordinates. Please verify your observation location."
        else:
            loc_status = 'unavailable'
            loc_msg = "Location metadata is not embedded in this photo. Visual environmental verification used."
            
    # Determine overall readiness
    # Required to pass: file_valid must be True, duplicate_passed must be True, and photo relevance must pass.
    ready = valid and duplicate_passed and suit_res['passed']
    
    return {
        'file_valid': valid,
        'file_msg': file_msg,
        'duplicate_check': duplicate_passed,
        'duplicate_msg': dup_msg,
        'image_suitability': suit_res['passed'],
        'suitability_warning': suit_res.get('is_warning', False),
        'suitability_msg': suit_res['message'],
        'photo_relevance': {
            'passed': suit_res['passed'],
            'status': suit_res['status'],
            'title': 'Photo verification',
            'message': suit_res['message'],
            'reason': suit_res['reason'],
            'confidence': suit_res.get('confidence'),
            'detected_subject': suit_res.get('detected_subject')
        },
        'location_check': loc_status,
        'location_msg': loc_msg,
        'image_hash': img_hash,
        'ready_to_submit': ready
    }
