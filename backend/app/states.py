"""Static lookups: institute -> state, Indian states list, and the mapping of a
student's career goal to preferred branch tags + guidance.

Keeping this data in one module makes the recommendation logic in
``recommender.py`` purely about filtering/ranking, and makes the mappings easy
to audit and extend.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Indian states / union territories (used to populate the home-state dropdown
# and to validate / normalise the home-state input).
# ---------------------------------------------------------------------------
INDIAN_STATES: List[str] = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]

# ---------------------------------------------------------------------------
# Institute -> state. Curated from the institute names in JEE_2025_Cutoffs.xlsx.
# This is what powers accurate Home-State (HS) vs Other-State (OS) filtering for
# NITs / IIITs / GFTIs.
# ---------------------------------------------------------------------------
INSTITUTE_STATE: Dict[str, str] = {
    "Assam University, Silchar": "Assam",
    "Atal Bihari Vajpayee Indian Institute of Information Technology & Management Gwalior": "Madhya Pradesh",
    "Birla Institute of Technology, Deoghar Off-Campus": "Jharkhand",
    "Birla Institute of Technology, Mesra, Ranchi": "Jharkhand",
    "Birla Institute of Technology, Patna Off-Campus": "Bihar",
    "CU Jharkhand": "Jharkhand",
    "Central University of Haryana": "Haryana",
    "Central University of Jammu": "Jammu and Kashmir",
    "Central University of Rajasthan, Rajasthan": "Rajasthan",
    "Central institute of Technology Kokrajar, Assam": "Assam",
    "Chhattisgarh Swami Vivekanada Technical University, Bhilai (CSVTU Bhilai)": "Chhattisgarh",
    "Dr. B R Ambedkar National Institute of Technology, Jalandhar": "Punjab",
    "Gati Shakti Vishwavidyalaya, Vadodara": "Gujarat",
    "Ghani Khan Choudhary Institute of Engineering and Technology, Malda, West Bengal": "West Bengal",
    "Gurukula Kangri Vishwavidyalaya, Haridwar": "Uttarakhand",
    "INDIAN INSTITUTE OF INFORMATION TECHNOLOGY SENAPATI MANIPUR": "Manipur",
    "Indian Institute of Carpet Technology, Bhadohi": "Uttar Pradesh",
    "Indian Institute of Engineering Science and Technology, Shibpur": "West Bengal",
    "Indian Institute of Handloom Technology(IIHT), Varanasi": "Uttar Pradesh",
    "Indian Institute of Handloom Technology, Salem": "Tamil Nadu",
    "Indian Institute of Information Technology (IIIT) Nagpur": "Maharashtra",
    "Indian Institute of Information Technology (IIIT) Pune": "Maharashtra",
    "Indian Institute of Information Technology (IIIT) Ranchi": "Jharkhand",
    "Indian Institute of Information Technology (IIIT), Sri City, Chittoor": "Andhra Pradesh",
    "Indian Institute of Information Technology (IIIT)Kota, Rajasthan": "Rajasthan",
    "Indian Institute of Information Technology Bhagalpur": "Bihar",
    "Indian Institute of Information Technology Bhopal": "Madhya Pradesh",
    "Indian Institute of Information Technology Design & Manufacturing Kurnool, Andhra Pradesh": "Andhra Pradesh",
    "Indian Institute of Information Technology Guwahati": "Assam",
    "Indian Institute of Information Technology Lucknow": "Uttar Pradesh",
    "Indian Institute of Information Technology Surat": "Gujarat",
    "Indian Institute of Information Technology Tiruchirappalli": "Tamil Nadu",
    "Indian Institute of Information Technology(IIIT) Dharwad": "Karnataka",
    "Indian Institute of Information Technology(IIIT) Kalyani, West Bengal": "West Bengal",
    "Indian Institute of Information Technology(IIIT) Kilohrad, Sonepat, Haryana": "Haryana",
    "Indian Institute of Information Technology(IIIT) Kottayam": "Kerala",
    "Indian Institute of Information Technology(IIIT) Una, Himachal Pradesh": "Himachal Pradesh",
    "Indian Institute of Information Technology(IIIT), Vadodara, Gujrat": "Gujarat",
    "Indian Institute of Information Technology, Agartala": "Tripura",
    "Indian Institute of Information Technology, Allahabad": "Uttar Pradesh",
    "Indian Institute of Information Technology, Design & Manufacturing, Kancheepuram": "Tamil Nadu",
    "Indian Institute of Information Technology, Vadodara International Campus Diu (IIITVICD)": "Daman and Diu",
    "Indian Institute of Technology (BHU) Varanasi": "Uttar Pradesh",
    "Indian Institute of Technology (ISM) Dhanbad": "Jharkhand",
    "Indian Institute of Technology Bhilai": "Chhattisgarh",
    "Indian Institute of Technology Bhubaneswar": "Odisha",
    "Indian Institute of Technology Bombay": "Maharashtra",
    "Indian Institute of Technology Delhi": "Delhi",
    "Indian Institute of Technology Dharwad": "Karnataka",
    "Indian Institute of Technology Gandhinagar": "Gujarat",
    "Indian Institute of Technology Goa": "Goa",
    "Indian Institute of Technology Guwahati": "Assam",
    "Indian Institute of Technology Hyderabad": "Telangana",
    "Indian Institute of Technology Indore": "Madhya Pradesh",
    "Indian Institute of Technology Jammu": "Jammu and Kashmir",
    "Indian Institute of Technology Jodhpur": "Rajasthan",
    "Indian Institute of Technology Kanpur": "Uttar Pradesh",
    "Indian Institute of Technology Kharagpur": "West Bengal",
    "Indian Institute of Technology Madras": "Tamil Nadu",
    "Indian Institute of Technology Mandi": "Himachal Pradesh",
    "Indian Institute of Technology Palakkad": "Kerala",
    "Indian Institute of Technology Patna": "Bihar",
    "Indian Institute of Technology Roorkee": "Uttarakhand",
    "Indian Institute of Technology Ropar": "Punjab",
    "Indian Institute of Technology Tirupati": "Andhra Pradesh",
    "Indian institute of information technology, Raichur, Karnataka": "Karnataka",
    "Institute of Chemical Technology, Mumbai: Indian Oil Odisha Campus, Bhubaneswar": "Odisha",
    "Institute of Engineering and Technology, Dr. H. S. Gour University. Sagar (A Central University)": "Madhya Pradesh",
    "Institute of Infrastructure, Technology, Research and Management-Ahmedabad": "Gujarat",
    "International Institute of Information Technology, Bhubaneswar": "Odisha",
    "International Institute of Information Technology, Naya Raipur": "Chhattisgarh",
    "Islamic University of Science and Technology Kashmir": "Jammu and Kashmir",
    "J.K. Institute of Applied Physics & Technology, Department of Electronics & Communication, University of Allahabad- Allahabad": "Uttar Pradesh",
    "Jawaharlal Nehru University, Delhi": "Delhi",
    "Malaviya National Institute of Technology Jaipur": "Rajasthan",
    "Maulana Azad National Institute of Technology Bhopal": "Madhya Pradesh",
    "Mizoram University, Aizawl": "Mizoram",
    "Motilal Nehru National Institute of Technology Allahabad": "Uttar Pradesh",
    "National Institute of Advanced Manufacturing Technology, Ranchi": "Jharkhand",
    "National Institute of Electronics and Information Technology, Ajmer (Rajasthan)": "Rajasthan",
    "National Institute of Electronics and Information Technology, Aurangabad (Maharashtra)": "Maharashtra",
    "National Institute of Electronics and Information Technology, Gorakhpur (UP)": "Uttar Pradesh",
    "National Institute of Electronics and Information Technology, Patna (Bihar)": "Bihar",
    "National Institute of Electronics and Information Technology, Ropar (Punjab)": "Punjab",
    "National Institute of Food Technology Entrepreneurship and Management, Kundli": "Haryana",
    "National Institute of Food Technology Entrepreneurship and Management, Thanjavur": "Tamil Nadu",
    "National Institute of Technology Agartala": "Tripura",
    "National Institute of Technology Arunachal Pradesh": "Arunachal Pradesh",
    "National Institute of Technology Calicut": "Kerala",
    "National Institute of Technology Delhi": "Delhi",
    "National Institute of Technology Durgapur": "West Bengal",
    "National Institute of Technology Goa": "Goa",
    "National Institute of Technology Hamirpur": "Himachal Pradesh",
    "National Institute of Technology Karnataka, Surathkal": "Karnataka",
    "National Institute of Technology Meghalaya": "Meghalaya",
    "National Institute of Technology Nagaland": "Nagaland",
    "National Institute of Technology Patna": "Bihar",
    "National Institute of Technology Puducherry": "Puducherry",
    "National Institute of Technology Raipur": "Chhattisgarh",
    "National Institute of Technology Sikkim": "Sikkim",
    "National Institute of Technology, Andhra Pradesh": "Andhra Pradesh",
    "National Institute of Technology, Jamshedpur": "Jharkhand",
    "National Institute of Technology, Kurukshetra": "Haryana",
    "National Institute of Technology, Manipur": "Manipur",
    "National Institute of Technology, Mizoram": "Mizoram",
    "National Institute of Technology, Rourkela": "Odisha",
    "National Institute of Technology, Silchar": "Assam",
    "National Institute of Technology, Srinagar": "Jammu and Kashmir",
    "National Institute of Technology, Tiruchirappalli": "Tamil Nadu",
    "National Institute of Technology, Uttarakhand": "Uttarakhand",
    "National Institute of Technology, Warangal": "Telangana",
    "North Eastern Regional Institute of Science and Technology, Nirjuli-791109 (Itanagar),Arunachal Pradesh": "Arunachal Pradesh",
    "North-Eastern Hill University, Shillong": "Meghalaya",
    "Pt. Dwarka Prasad Mishra Indian Institute of Information Technology, Design & Manufacture Jabalpur": "Madhya Pradesh",
    "Puducherry Technological University, Puducherry": "Puducherry",
    "Punjab Engineering College, Chandigarh": "Chandigarh",
    "Rajiv Gandhi National Aviation University, Fursatganj, Amethi (UP)": "Uttar Pradesh",
    "Sant Longowal Institute of Engineering and Technology": "Punjab",
    "Sardar Vallabhbhai National Institute of Technology, Surat": "Gujarat",
    "School of Engineering, Tezpur University, Napaam, Tezpur": "Assam",
    "School of Planning & Architecture, Bhopal": "Madhya Pradesh",
    "School of Planning & Architecture, New Delhi": "Delhi",
    "School of Planning & Architecture: Vijayawada": "Andhra Pradesh",
    "School of Studies of Engineering and Technology, Guru Ghasidas Vishwavidyalaya, Bilaspur": "Chhattisgarh",
    "Shri G. S. Institute of Technology and Science Indore": "Madhya Pradesh",
    "Shri Mata Vaishno Devi University, Katra, Jammu & Kashmir": "Jammu and Kashmir",
    "University of Hyderabad": "Telangana",
    "Visvesvaraya National Institute of Technology, Nagpur": "Maharashtra",
}

# Special state quotas that appear in the data for a handful of institutes.
# GO = Goa, JK = Jammu & Kashmir, LA = Ladakh. They behave like a Home-State
# quota that is only available to candidates from that specific state/UT.
SPECIAL_QUOTA_STATE: Dict[str, str] = {
    "GO": "Goa",
    "JK": "Jammu and Kashmir",
    "LA": "Ladakh",
}


def get_institute_state(institute: str) -> str:
    """Return the state for an institute, falling back to a best-effort guess
    from the trailing tokens of the name if it is not in the curated map."""
    if institute in INSTITUTE_STATE:
        return INSTITUTE_STATE[institute]
    # Fallback: try to match any known state name appearing in the institute name.
    lowered = institute.lower()
    for state in INDIAN_STATES:
        if state.lower() in lowered:
            return state
    return "Unknown"


# ---------------------------------------------------------------------------
# Branch classification: map a (messy) academic program name to a set of tags.
# ---------------------------------------------------------------------------
def classify_branch(program: str) -> Set[str]:
    """Return a set of semantic tags for a program name."""
    p = program.lower()
    tags: Set[str] = set()

    def has(*keys: str) -> bool:
        return any(k in p for k in keys)

    # Computing-oriented
    if has("computer science", "computer engineering", "cse", " cs "):
        tags.add("cse")
    if has("mathematics and computing", "maths and computing", "mathematics & computing"):
        tags.add("math_computing")
    if has("artificial intelligence", "data science", "machine learning", " ai "):
        tags.add("ai_ds")
    if has("information technology") and "national institute of" not in p:
        tags.add("it")

    # Electronics / electrical
    if has("electronics", "communication", "vlsi", "electronics and communication"):
        tags.add("ece")
    if has("electrical"):
        tags.add("electrical")
    if has("instrumentation"):
        tags.add("ece")

    # Core mechanical / civil / chemical / aero / materials etc.
    if has("mechanical"):
        tags.add("mechanical")
    if has("civil"):
        tags.add("civil")
    if has("chemical"):
        tags.add("chemical")
    if has("aerospace", "aeronaut", "aviation"):
        tags.add("aerospace")
    if has("metallurg", "materials"):
        tags.add("materials")
    if has("production", "industrial", "manufacturing", "mechatron"):
        tags.add("production")
    if has("energy"):
        tags.add("energy")
    if has("biotech", "bio technology", "biomedical", "biological", "bio-medical"):
        tags.add("biotech")

    # Pure / applied sciences (research-leaning)
    if has("physics", "geophysics"):
        tags.add("physics")
    if has("chemistry"):
        tags.add("chemistry")
    if has("mathematics") and "computing" not in p:
        tags.add("math_science")
    if has("economics"):
        tags.add("economics")
    # Generic "BS in"/"Bachelor of Science" research-style programs.
    if "bachelor of science" in p or p.strip().startswith("bs ") or " bs in" in p:
        tags.add("bs_science")

    # Architecture / planning / design
    if has("architecture"):
        tags.add("architecture")
    if has("planning"):
        tags.add("planning")
    if has("design") and not has("manufacturing"):
        tags.add("design")

    if not tags:
        tags.add("other")
    return tags


# ---------------------------------------------------------------------------
# Career goals -> tag weights + guidance text.
# ---------------------------------------------------------------------------
# Each goal maps to a dict of {tag: weight}. An option's interest score is the
# max weight among its tags (plus a small institute-brand bonus applied in the
# recommender). Higher = better fit for the stated goal.
GOAL_TAG_WEIGHTS: Dict[str, Dict[str, float]] = {
    "coding": {
        "cse": 10,
        "math_computing": 9,
        "ai_ds": 9,
        "it": 8,
        "ece": 6,
        "electrical": 4,
    },
    "research": {
        "physics": 10,
        "bs_science": 9,
        "math_science": 9,
        "chemistry": 8,
        "math_computing": 7,
        "economics": 6,
        "cse": 5,
        "ece": 5,
        "materials": 5,
        "mechanical": 4,
        "chemical": 4,
    },
    "mba": {
        # For management aspirants the branch matters less than the brand of
        # the institute (handled via a brand bonus in the recommender), but
        # analytical/quant branches help a little.
        "economics": 8,
        "cse": 6,
        "math_computing": 6,
        "ece": 5,
        "mechanical": 5,
        "electrical": 5,
        "civil": 4,
        "chemical": 4,
    },
    "core": {
        "mechanical": 10,
        "civil": 9,
        "electrical": 9,
        "chemical": 9,
        "aerospace": 9,
        "materials": 8,
        "energy": 8,
        "production": 8,
        "ece": 6,
        "cse": 3,
    },
    "undecided": {
        # Balanced: favour versatile, high-demand branches without going
        # all-in on any single direction.
        "cse": 7,
        "ece": 7,
        "math_computing": 7,
        "ai_ds": 7,
        "electrical": 6,
        "mechanical": 6,
        "chemical": 5,
        "civil": 5,
        "it": 6,
        "economics": 5,
    },
}

# Whether a goal cares strongly about institute brand/tier (used for the brand
# bonus and for guidance wording).
GOAL_BRAND_SENSITIVE = {"mba": 1.0, "undecided": 0.5}

GOAL_LABELS: Dict[str, str] = {
    "coding": "Software / coding career",
    "research": "Research / higher studies",
    "mba": "Management / MBA / business",
    "core": "Core engineering",
    "undecided": "Undecided / keeping options open",
}

GOAL_GUIDANCE: Dict[str, str] = {
    "coding": (
        "Since you are aiming for a software/coding career, Computer Science, "
        "Mathematics & Computing, AI/Data Science and IT branches are ranked "
        "highest for you. A strong CS-adjacent branch usually matters more for "
        "coding roles than the exact institute, but a higher-brand institute "
        "helps with internships and placements."
    ),
    "research": (
        "For a research or higher-studies path, fundamental-science and "
        "research-heavy programs (Engineering Physics, BS degrees in Maths/"
        "Physics/Chemistry/Economics) and core branches at top institutes are "
        "prioritised. Look for institutes with strong labs, faculty and PhD "
        "pipelines."
    ),
    "mba": (
        "If you are leaning towards management/MBA, the brand and peer network "
        "of the institute matter most, so higher-tier institutes are weighted "
        "up. Any branch is fine for an MBA later; quantitative branches like "
        "Economics, CS and Maths & Computing add a small edge."
    ),
    "core": (
        "For a core-engineering career, Mechanical, Civil, Electrical, "
        "Chemical, Aerospace and Materials branches are ranked highest. Core "
        "branches at reputed institutes (with good core-sector recruiters and "
        "labs) are the best fit."
    ),
    "undecided": (
        "Since you are still deciding, the list favours versatile, high-demand "
        "branches and stronger-brand institutes that keep the most doors open "
        "(coding, higher studies, core roles or management later)."
    ),
}

VALID_GOALS = list(GOAL_TAG_WEIGHTS.keys())
VALID_GENDERS = ["male", "female"]

# Reservation categories for JoSAA/CSAB seat allocation.
# The current dataset (JEE_2025_Cutoffs.xlsx) contains OPEN seats only.
# Entries marked available=False are shown in the UI with a "coming soon" note.
VALID_CATEGORIES: list = [
    {"value": "OPEN", "label": "OPEN (General / CRL)", "available": True},
    {"value": "OBC-NCL", "label": "OBC-NCL", "available": False},
    {"value": "SC", "label": "SC (Scheduled Caste)", "available": False},
    {"value": "ST", "label": "ST (Scheduled Tribe)", "available": False},
    {"value": "EWS", "label": "EWS (Economically Weaker Section)", "available": False},
    {"value": "PwD", "label": "PwD (Person with Disability)", "available": False},
]
