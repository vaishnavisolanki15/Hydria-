import os
import math
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

def check_duplicate_image(image_hash, existing_hashes, threshold=4):
    """
    Check 2: Compare perceptual hash with existing reports.
    If hamming distance is <= threshold, it's considered duplicate/near-identical.
    """
    if not image_hash:
        return False, None
    for rep_id, ex_hash in existing_hashes:
        if not ex_hash:
            continue
        dist = hamming_distance(image_hash, ex_hash)
        if dist <= threshold:
            return True, rep_id
    return False, None

def check_photo_suitability(image):
    """
    Check 3: Local heuristic check for obvious non-water / blank / portrait images.
    Returns: (is_suitable: bool, is_warning: bool, message: str)
    """
    try:
        rgb_img = image.convert('RGB')
        w, h = rgb_img.size
        
        # 1. Blank / uniform color detection using standard deviation
        stat = ImageStat.Stat(rgb_img)
        # Average stddev across R, G, B channels
        avg_stddev = sum(stat.stddev) / len(stat.stddev)
        if avg_stddev < 8.0:
            return False, True, "Image appears blank or has virtually no visual details. Please upload a clear photo of the water body."
        
        # Check extreme brightness (completely pitch black or blown-out white)
        avg_mean = sum(stat.mean) / len(stat.mean)
        if avg_mean < 10.0:
            return False, True, "Image is completely dark/black. Please upload a visible photo taken with adequate lighting."
        if avg_mean > 250.0:
            return False, True, "Image is overexposed or solid white. Please upload a clear photo of the water body."
            
        # 2. Thumbnail analysis for dominant color heuristics
        thumb = rgb_img.resize((64, 64), Image.Resampling.BILINEAR)
        if hasattr(thumb, 'get_flattened_data'):
            pixels = list(thumb.get_flattened_data())
        else:
            pixels = list(thumb.getdata())
        total_pixels = len(pixels)
        
        # 3. Check for obvious portrait / selfie heuristic:
        # Inspect center region (middle 50% box) for high concentration of human skin tones
        center_pixels = []
        for y in range(16, 48):
            for x in range(16, 48):
                center_pixels.append(thumb.getpixel((x, y)))
        
        skin_count = 0
        for r, g, b in center_pixels:
            # Common YCbCr / RGB skin tone bounding heuristic
            # In RGB: R > 95, G > 40, B > 20, max(R,G,B) - min(R,G,B) > 15, |R - G| > 15, R > G, R > B
            if (r > 95 and g > 40 and b > 20 and 
                (max(r, g, b) - min(r, g, b)) > 15 and 
                abs(r - g) > 15 and r > g and r > b):
                skin_count += 1
                
        skin_ratio_center = skin_count / len(center_pixels)
        if skin_ratio_center > 0.65:
            return False, True, (
                "The uploaded image may not show the reported water body (portrait/selfie characteristics detected). "
                "Please upload a clear photo of the water body."
            )
            
        # 4. Check for natural environment / water / bank tones
        # Count pixels that have blue, green, cyan, muddy brown, or dark river tones
        natural_tones = 0
        for r, g, b in pixels:
            # Blues/Cyans: B > R and B > 50
            is_blue = (b > r and (b > g or abs(b - g) < 30)) and b > 40
            # Greens/Algae: G > R and G > B
            is_green = (g > r and g > b) and g > 40
            # Browns/Mud/Silt: R > G and G > B with low saturation or earthy darks
            is_earth = (r >= g >= b) and (r - b < 90) and r > 30
            # Murky/Dark water tones
            is_dark_water = (max(r, g, b) < 90 and min(r, g, b) > 10)
            
            if is_blue or is_green or is_earth or is_dark_water:
                natural_tones += 1
                
        natural_ratio = natural_tones / total_pixels
        
        if natural_ratio >= 0.25:
            return True, False, "Hydria validation suggests this image is suitable for a water-body report."
        else:
            return True, True, "We could not confidently validate this image. Please ensure this photo clearly shows the reported water body."
            
    except Exception as e:
        return True, True, f"Image could not be fully analyzed: {str(e)}"

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

def validate_image_full(file_path, browser_lat, browser_lon, existing_hashes):
    """
    Run full Hydria Local Validation Engine pipeline:
    1. File validity
    2. Perceptual duplicate check
    3. Suitability heuristic
    4. EXIF location verification
    
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
            'location_check': 'unavailable',
            'location_msg': "Skipped due to file error.",
            'image_hash': None,
            'ready_to_submit': False
        }
        
    # Open image for further checks
    with Image.open(file_path) as img:
        # 2. Hash & Duplicate Check
        img_hash = compute_dhash(img)
        is_dup, dup_rep_id = check_duplicate_image(img_hash, existing_hashes)
        if is_dup:
            dup_msg = f"Possible duplicate image detected. This image appears to have already been submitted (Report #{dup_rep_id}). Please upload a new photo."
            duplicate_passed = False
        else:
            dup_msg = "No duplicate image found."
            duplicate_passed = True
            
        # 3. Photo Suitability
        suitable, is_suit_warn, suit_msg = check_photo_suitability(img)
        
        # 4. EXIF Location Verification
        exif_lat, exif_lon = extract_exif_gps(img)
        if exif_lat is not None and exif_lon is not None and browser_lat is not None and browser_lon is not None:
            dist = haversine_distance(browser_lat, browser_lon, exif_lat, exif_lon)
            if dist <= 200:
                loc_status = 'pass'
                loc_msg = f"Photo GPS coordinates match reported location (within ~{int(dist)}m)."
            else:
                loc_status = 'warning'
                loc_msg = f"Photo EXIF location is approximately {int(dist)}m away from browser location."
        else:
            loc_status = 'unavailable'
            loc_msg = "Photo location information is unavailable. Please make sure this is a photo of the water body you are reporting."
            
    # Determine overall readiness
    # Required to pass: file_valid must be True, duplicate_passed must be True, and suitable must not be hard fail.
    # Note: loc_status 'warning' or 'unavailable' allows submission with a notice as per spec Section 16.
    ready = valid and duplicate_passed and suitable
    
    return {
        'file_valid': valid,
        'file_msg': file_msg,
        'duplicate_check': duplicate_passed,
        'duplicate_msg': dup_msg,
        'image_suitability': suitable,
        'suitability_warning': is_suit_warn,
        'suitability_msg': suit_msg,
        'location_check': loc_status,
        'location_msg': loc_msg,
        'image_hash': img_hash,
        'ready_to_submit': ready
    }
