"""
Hydria Local Rule-Based Analysis Engine
Transforms citizen observation data into understandable water insights without external AI APIs.
"""

def generate_water_insight(report_data):
    """
    Analyzes citizen observations and produces an observation-based insight.
    
    Expected keys in report_data:
        - water_colour: str
        - smell: str
        - algae: str
        - visible_waste: str
        - water_appearance: str
        - dead_fish: str (optional)
        - water_body_type: str (optional)
        
    Returns:
        dict: {
            'concern_level': 'High Concern' | 'Moderate Concern' | 'Low / Baseline Concern',
            'concern_score': int,
            'flagged_items': list of str,
            'summary': str,
            'recommendation': str,
            'disclaimer': str
        }
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
    elif algae == "Not sure":
        # slight ambiguity
        pass

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
            f"The report indicates several visible signs of environmental concern, "
            f"including {factors}. Further observation and community monitoring are strongly advised."
        )
        recommendation = "Local community water monitors should verify this report and track whether conditions worsen."
    elif score >= 3:
        concern_level = "Moderate Concern"
        color_badge = "badge-warning"
        factors = ", ".join(concerns[:2]) if concerns else "elevated observation markers"
        summary = (
            f"Moderate environmental indicators were reported, including {factors}. "
            f"Conditions deviate from typical clean freshwater states."
        )
        recommendation = "Periodic check-ins by nearby residents can help determine if this is temporary runoff or persistent pollution."
    else:
        concern_level = "Low / Baseline Concern"
        color_badge = "badge-success"
        summary = (
            "The submitted observations do not show major visible concerns based on the information provided. "
            "The water body appears relatively stable."
        )
        recommendation = "Continued periodic observation is recommended to help maintain a healthy baseline record."

    return {
        'concern_level': concern_level,
        'badge_class': color_badge,
        'concern_score': score,
        'flagged_items': concerns,
        'summary': summary,
        'recommendation': recommendation,
        'disclaimer': "Observation-based insight generated by Hydria Local Rule Engine. This is not a certified laboratory water-quality test."
    }
