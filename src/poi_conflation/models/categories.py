"""Category normalization mapping between OSM tags, Overture taxonomies, and canonical categories."""

from typing import Optional

# High-level canonical categories
CANONICAL_CATEGORIES = {
    "sustenance",
    "retail",
    "healthcare",
    "hospitality",
    "financial",
    "education",
    "commercial_services",
    "civic_religious",
    "leisure_tourism",
    "other"
}

# Mapping rules for OSM primary key=value
OSM_CATEGORY_MAP = {
    # Sustenance
    "amenity=restaurant": "sustenance",
    "amenity=cafe": "sustenance",
    "amenity=fast_food": "sustenance",
    "amenity=food_court": "sustenance",
    "amenity=bar": "sustenance",
    "amenity=pub": "sustenance",
    "amenity=ice_cream": "sustenance",
    "shop=bakery": "sustenance",
    "shop=coffee": "sustenance",
    "shop=tea": "sustenance",

    # Retail / Shopping
    "shop=supermarket": "retail",
    "shop=convenience": "retail",
    "shop=clothes": "retail",
    "shop=mall": "retail",
    "shop=department_store": "retail",
    "shop=general": "retail",
    "shop=electronics": "retail",
    "shop=mobile_phone": "retail",
    "shop=hardware": "retail",
    "shop=chemist": "retail",
    "shop=hairdresser": "retail",
    "shop=beauty": "retail",
    "shop=jewelry": "retail",
    "shop=stationery": "retail",
    "shop=shoes": "retail",

    # Healthcare
    "amenity=hospital": "healthcare",
    "amenity=clinic": "healthcare",
    "amenity=pharmacy": "healthcare",
    "amenity=doctors": "healthcare",
    "amenity=dentist": "healthcare",
    "healthcare=hospital": "healthcare",
    "healthcare=clinic": "healthcare",
    "healthcare=pharmacy": "healthcare",
    "healthcare=doctor": "healthcare",

    # Hospitality
    "tourism=hotel": "hospitality",
    "tourism=guest_house": "hospitality",
    "tourism=hostel": "hospitality",
    "tourism=motel": "hospitality",
    "tourism=lodge": "hospitality",

    # Financial
    "amenity=bank": "financial",
    "amenity=atm": "financial",
    "amenity=bureau_de_change": "financial",

    # Education
    "amenity=school": "education",
    "amenity=college": "education",
    "amenity=university": "education",
    "amenity=kindergarten": "education",
    "amenity=library": "education",
    "amenity=research_institute": "education",

    # Commercial Services & Offices
    "office=company": "commercial_services",
    "office=it": "commercial_services",
    "office=telecommunication": "commercial_services",
    "office=estate_agent": "commercial_services",
    "office=lawyer": "commercial_services",
    "office=accountant": "commercial_services",
    "office=consulting": "commercial_services",
    "craft=photographer": "commercial_services",

    # Civic & Religious
    "amenity=place_of_worship": "civic_religious",
    "amenity=police": "civic_religious",
    "amenity=post_office": "civic_religious",
    "amenity=fire_station": "civic_religious",
    "amenity=townhall": "civic_religious",
    "amenity=courthouse": "civic_religious",
    "amenity=community_centre": "civic_religious",

    # Leisure & Tourism
    "tourism=attraction": "leisure_tourism",
    "tourism=museum": "leisure_tourism",
    "tourism=theme_park": "leisure_tourism",
    "historic=monument": "leisure_tourism",
    "historic=memorial": "leisure_tourism",
    "historic=heritage": "leisure_tourism",
    "leisure=park": "leisure_tourism",
    "leisure=fitness_centre": "leisure_tourism",
    "leisure=sports_centre": "leisure_tourism",
    "amenity=cinema": "leisure_tourism",
    "amenity=theatre": "leisure_tourism",
}

# Mapping rules for Overture taxonomies / basic categories
OVERTURE_CATEGORY_MAP = {
    # Sustenance
    "restaurant": "sustenance",
    "indian_restaurant": "sustenance",
    "cafe": "sustenance",
    "coffee_shop": "sustenance",
    "fast_food_restaurant": "sustenance",
    "bakery": "sustenance",
    "bar": "sustenance",
    "pub": "sustenance",
    "dessert_shop": "sustenance",
    "caterer": "sustenance",

    # Retail
    "shopping": "retail",
    "clothing_store": "retail",
    "supermarket": "retail",
    "grocery_store": "retail",
    "convenience_store": "retail",
    "shopping_mall": "retail",
    "jewelry_store": "retail",
    "electronics_store": "retail",
    "mobile_phone_shop": "retail",
    "shoe_store": "retail",
    "department_store": "retail",
    "hardware_store": "retail",
    "beauty_salon": "retail",
    "hair_salon": "retail",

    # Healthcare
    "hospital": "healthcare",
    "medical_center": "healthcare",
    "clinic": "healthcare",
    "pharmacy": "healthcare",
    "doctor": "healthcare",
    "dentist": "healthcare",

    # Hospitality
    "hotel": "hospitality",
    "motel": "hospitality",
    "bed_and_breakfast": "hospitality",
    "resort": "hospitality",
    "lodging": "hospitality",

    # Financial
    "bank": "financial",
    "atm": "financial",
    "financial_service": "financial",
    "insurance_company": "financial",

    # Education
    "school": "education",
    "college_or_university": "education",
    "elementary_school": "education",
    "middle_school": "education",
    "high_school": "education",
    "preschool": "education",
    "educational_institution": "education",

    # Commercial Services
    "professional_service": "commercial_services",
    "real_estate_service": "commercial_services",
    "real_estate_agent": "commercial_services",
    "business_service": "commercial_services",
    "party_and_event_planning": "commercial_services",
    "legal_service": "commercial_services",
    "corporate_office": "commercial_services",
    "consulting_agency": "commercial_services",

    # Civic & Religious
    "place_of_worship": "civic_religious",
    "hindu_place_of_worship": "civic_religious",
    "mosque": "civic_religious",
    "church": "civic_religious",
    "temple": "civic_religious",
    "government_office": "civic_religious",
    "police_station": "civic_religious",
    "post_office": "civic_religious",

    # Leisure & Tourism
    "historic_site": "leisure_tourism",
    "tourist_attraction": "leisure_tourism",
    "museum": "leisure_tourism",
    "park": "leisure_tourism",
    "gym_and_fitness_center": "leisure_tourism",
    "movie_theater": "leisure_tourism",
}


def normalize_osm_category(tags: dict) -> str:
    """Determine canonical category from OSM tags."""
    for key in ("amenity", "shop", "healthcare", "tourism", "office", "leisure", "craft", "historic"):
        val = tags.get(key)
        if val:
            pair = f"{key}={val}"
            if pair in OSM_CATEGORY_MAP:
                return OSM_CATEGORY_MAP[pair]
            # Fallbacks by primary key
            if key == "shop":
                return "retail"
            if key == "healthcare":
                return "healthcare"
            if key == "office":
                return "commercial_services"
            if key == "tourism":
                return "hospitality"
    return "other"


def normalize_overture_category(primary_tax: Optional[str], basic_cat: Optional[str]) -> str:
    """Determine canonical category from Overture taxonomy / basic category."""
    if primary_tax:
        clean = primary_tax.lower().strip()
        if clean in OVERTURE_CATEGORY_MAP:
            return OVERTURE_CATEGORY_MAP[clean]
    if basic_cat:
        clean_b = basic_cat.lower().strip()
        if clean_b in OVERTURE_CATEGORY_MAP:
            return OVERTURE_CATEGORY_MAP[clean_b]
    return "other"
