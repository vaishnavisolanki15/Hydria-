"""
Hydria Environmental Analysis Engine
Combines Google Gemini Generative AI report diagnostics with an offline deterministic rule-based fallback.
"""

import os
import json
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

def generate_local_rule_insight(report_data):
    """
    Deterministic rule-based baseline analysis when Gemini AI is offline or unavailable.
    """
    if not isinstance(report_data, dict):
        report_data = dict(report_data)

    water_colour = report_data.get('water_colour', '')
    smell = report_data.get('smell', '')
    algae = report_data.get('algae', '')
    visible_waste = report_data.get('visible_waste', '')
    water_appearance = report_data.get('water_appearance', '')
    dead_fish = report_data.get('dead_fish', 'No')

    concerns = []
    score = 0

    # 1. Water Colour Analysis
    if water_colour in ["Dark Green", "Black"]:
        concerns.append(f"Unusual dark water discoloration ({water_colour.lower()})")
        score += 3
    elif water_colour in ["Brown", "Green", "Yellowish"]:
        concerns.append(f"Water discoloration observed ({water_colour.lower()})")
        score += 2
    elif water_colour == "Other":
        concerns.append("Atypical water colour reported")
        score += 1

    # 2. Odor / Smell Analysis
    if smell in ["Sewage-like smell", "Chemical smell", "Rotten smell"]:
        concerns.append(f"Noticeable pungent odor ({smell.lower()})")
        score += 3
    elif smell == "Bad smell":
        concerns.append("Unpleasant odor detected")
        score += 2
    elif smell == "Other":
        concerns.append("Unusual smell noted")
        score += 1

    # 3. Algae Presence
    if algae == "Yes":
        concerns.append("Visible algal growth or bloom")
        score += 2

    # 4. Visible Waste
    if visible_waste == "High":
        concerns.append("Substantial surface waste and debris")
        score += 3
    elif visible_waste == "Medium":
        concerns.append("Noticeable floating waste and litter")
        score += 2
    elif visible_waste == "Low":
        concerns.append("Minor debris observed")
        score += 1

    # 5. Overall Appearance
    if water_appearance == "Very Dirty":
        concerns.append("Severe visual contamination reported")
        score += 3
    elif water_appearance == "Dirty":
        concerns.append("Dirty water condition observed")
        score += 2
    elif water_appearance == "Unusual":
        concerns.append("Unusual visual surface condition")
        score += 1

    # 6. Dead Fish / Animals (Critical biological indicator)
    if dead_fish == "Yes":
        concerns.append("Dead aquatic wildlife observed (critical indicator)")
        score += 4

    # Determine Concern Level and Narrative
    if score >= 6 or dead_fish == "Yes":
        concern_level = "High Concern"
        color_badge = "badge-danger"
        factors = ", ".join(concerns[:3]) if concerns else "multiple concerning indicators"
        summary = (
            f"The report indicates several visible signs of critical environmental concern, "
            f"including {factors}. Further observation and community monitoring are strongly advised."
        )
        recommendation = "Local community water monitors and authorities should verify this report, inspect inflows, and track condition trends."
        root_causes = [
            "Severe organic/sewage contamination depleting dissolved oxygen",
            "Potential municipal storm-drain overflow or untreated effluent discharge",
            "Surface algal accumulation and biological oxygen depletion"
        ]
        civic_action_steps = [
            "Report immediately to local municipal pollution control board or water authority",
            "Conduct dissolved oxygen (DO) and biochemical oxygen demand (BOD) testing",
            "Restrict public water contact and notify local community monitors"
        ]
    elif score >= 3:
        concern_level = "Moderate Concern"
        color_badge = "badge-warning"
        factors = ", ".join(concerns[:2]) if concerns else "elevated observation markers"
        summary = (
            f"Moderate environmental indicators were reported, including {factors}. "
            f"Conditions deviate noticeably from typical clean freshwater states."
        )
        recommendation = "Periodic check-ins by nearby residents can help determine if this is temporary seasonal runoff or persistent pollution."
        root_causes = [
            "Urban stormwater runoff carrying surface silt or organic debris",
            "Moderate nutrient enrichment promoting seasonal algae presence",
            "Litter accumulation from nearby residential or commercial activity"
        ]
        civic_action_steps = [
            "Organize community clean-up drive for shoreline debris",
            "Monitor water clarity after rainfall events",
            "Document seasonal changes through follow-up observations"
        ]
    else:
        concern_level = "Low / Baseline Concern"
        color_badge = "badge-success"
        summary = (
            "The submitted observations do not show major visible concerns based on the information provided. "
            "The water body appears relatively healthy and stable."
        )
        recommendation = "Continued periodic observation is recommended to help maintain a healthy baseline record."
        root_causes = [
            "Healthy aquatic equilibrium with natural seasonal variations",
            "Low anthropogenic disturbance observed at reported site"
        ]
        civic_action_steps = [
            "Log monthly baseline observations to track long-term health",
            "Protect riparian shoreline vegetation from degradation"
        ]

    return {
        'concern_level': concern_level,
        'badge_class': color_badge,
        'concern_score': score,
        'flagged_items': concerns,
        'summary': summary,
        'recommendation': recommendation,
        'root_causes': root_causes,
        'health_advisory': recommendation,
        'civic_action_steps': civic_action_steps,
        'is_ai': False,
        'ai_model': "Hydria Rule Engine (Local Baseline)",
        'disclaimer': "Observation-based insight generated by Hydria Local Rule Engine. This is not a certified laboratory water-quality test."
    }

def generate_gemini_water_insight(report_data, image_path=None):
    """
    Calls Google Gemini API (gemini-2.5-flash) to produce deep ecological report analysis.
    Optionally includes the uploaded photograph for multimodal visual inspection.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
        from PIL import Image

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an expert environmental scientist and limnologist analyzing a freshwater quality observation report for the Hydria Citizen Science platform.
Evaluate the following field report submitted by a citizen monitor:

- Water Body Name: {report_data.get('water_body_name') or 'Unnamed Water Body'}
- Water Body Type: {report_data.get('water_body_type', 'Freshwater body')}
- Location Coordinates: ({report_data.get('latitude')}, {report_data.get('longitude')})
- Water Colour: {report_data.get('water_colour', 'Unspecified')}
- Odor / Smell: {report_data.get('smell', 'Unspecified')}
- Algae Growth: {report_data.get('algae', 'Unspecified')}
- Visible Waste & Litter: {report_data.get('visible_waste', 'Unspecified')}
- Surface Appearance: {report_data.get('water_appearance', 'Unspecified')}
- Dead Wildlife / Fish: {report_data.get('dead_fish', 'No')}
- Observer Field Notes: {report_data.get('additional_observation') or 'None provided'}

Provide an environmental assessment formatted strictly as a single valid JSON object with the following exact keys:
{{
    "concern_level": "High Concern" | "Moderate Concern" | "Low / Baseline Concern",
    "concern_score": integer between 1 and 10,
    "summary": "2-3 sentences concise executive diagnosis of the water body condition and primary threat",
    "root_causes": ["ecological or anthropogenic cause 1", "cause 2", "cause 3"],
    "health_advisory": "Clear safety advice for citizens, residents, children, pets, and recreation",
    "civic_action_steps": ["Actionable step 1 for civic monitors/municipal authorities", "Actionable step 2", "Actionable step 3"],
    "flagged_items": ["notable concerning observation 1", "notable observation 2"]
}}
Return ONLY valid raw JSON without markdown formatting or code blocks.
"""

        contents = [prompt]

        # Attach image if provided and valid on disk
        if image_path:
            full_img_path = image_path
            if not os.path.isabs(full_img_path):
                full_img_path = os.path.join(BASE_DIR, image_path)
            if os.path.exists(full_img_path):
                try:
                    img = Image.open(full_img_path)
                    contents.append(img)
                except Exception:
                    pass

        response = None
        for model_cand in ["gemini-flash-latest", "gemini-2.5-flash"]:
            try:
                response = client.models.generate_content(
                    model=model_cand,
                    contents=contents
                )
                if response and response.text:
                    break
            except Exception:
                continue

        if not response or not response.text:
            return None

        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()

        data = json.loads(raw_text)

        # Standardize badge class
        level = data.get('concern_level', 'Moderate Concern')
        if 'High' in level:
            badge_class = 'badge-danger'
        elif 'Moderate' in level or 'Medium' in level:
            badge_class = 'badge-warning'
        else:
            badge_class = 'badge-success'

        return {
            'concern_level': level,
            'badge_class': badge_class,
            'concern_score': int(data.get('concern_score', 5)),
            'summary': data.get('summary', ''),
            'root_causes': data.get('root_causes', []),
            'health_advisory': data.get('health_advisory', ''),
            'recommendation': data.get('health_advisory', ''),
            'civic_action_steps': data.get('civic_action_steps', []),
            'flagged_items': data.get('flagged_items', []),
            'is_ai': True,
            'ai_model': "Google Gemini 2.5 Flash",
            'disclaimer': "AI Environmental Diagnostic generated by Google Gemini 2.5 Flash & Hydria Intelligence Platform."
        }

    except Exception as e:
        print(f"Gemini API analysis notice: {e}. Utilizing local rule engine.")
        return None

def generate_water_insight(report_data, image_path=None, force_refresh=False, allow_remote=True):
    """
    Main entry point for report analysis:
    1. Checks if report already has cached ai_analysis in database
    2. If allow_remote is True and (not cached or force_refresh is True), queries Gemini API
    3. If Gemini is unavailable or allow_remote is False, falls back to deterministic local rule engine
    """
    if not isinstance(report_data, dict):
        report_data = dict(report_data)

    # 1. Check for cached AI analysis from MySQL
    cached_ai = report_data.get('ai_analysis')
    if cached_ai and not force_refresh:
        try:
            if isinstance(cached_ai, str):
                parsed = json.loads(cached_ai)
            else:
                parsed = dict(cached_ai)

            if parsed and 'concern_level' in parsed:
                # Ensure badge class is present
                level = parsed.get('concern_level', '')
                if 'High' in level:
                    parsed['badge_class'] = 'badge-danger'
                elif 'Moderate' in level or 'Medium' in level:
                    parsed['badge_class'] = 'badge-warning'
                else:
                    parsed['badge_class'] = 'badge-success'
                return parsed
        except Exception:
            pass

    # 2. Try Gemini Generative AI if remote calls allowed
    if allow_remote:
        gemini_insight = generate_gemini_water_insight(
            report_data,
            image_path=image_path or report_data.get('image_path')
        )
        if gemini_insight:
            # Cache back to database if report ID exists
            report_id = report_data.get('id')
            if report_id:
                try:
                    import database
                    database.save_report_ai_analysis(report_id, json.dumps(gemini_insight))
                except Exception:
                    pass
            return gemini_insight

    # 3. Fallback to deterministic local rule engine
    return generate_local_rule_insight(report_data)
