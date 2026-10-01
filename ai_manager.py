import os
from google import genai
from PIL import Image

FAULT_CATEGORIES = ["plumbing", "lift", "electrical", "general maintenance"]
RISK_INDICATORS = [
    "fire", "smoke", "trapped_person", "exposed_wiring", "electric_sparks",
    "flooding", "active_leak", "trip_hazard", "service_outage",
]
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "fault_category": {"type": "string", "enum": FAULT_CATEGORIES},
        "summary": {"type": "string"},
        "risk_indicators": {
            "type": "array",
            "items": {"type": "string", "enum": RISK_INDICATORS},
        },
        "common_area_hazard": {"type": "boolean"},
        "is_unclear": {"type": "boolean"},
    },
    "required": [
        "fault_category", "summary", "risk_indicators",
        "common_area_hazard", "is_unclear",
    ],
    "additionalProperties": False,
}

client = genai.Client()

image_path = "cow.jpg"
image = Image.open(image_path)

response = client.models.generate_content(
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    contents=[image, "What is this image?"],
)

print(response.text)