"""
Report Merger — Merges inspection and thermal data into a unified DDR using Gemini.
"""
import json
import logging
import time
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from typing import List, Optional
from ai_engine.prompts import DDR_GENERATION_PROMPT
from parsers.pdf_parser import ExtractedImage
import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 30


def _configure_gemini():
    """Configure the Gemini API client."""
    if not config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set.")
    genai.configure(api_key=config.GEMINI_API_KEY)


def _parse_json_response(response_text: str) -> dict:
    """Parse JSON from Gemini response."""
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse DDR JSON: {e}")
        return {"error": str(e), "raw_text": text[:2000]}


def merge_and_generate_ddr(
    inspection_data: dict,
    thermal_data: dict,
    inspection_images: Optional[List[ExtractedImage]] = None,
    thermal_images: Optional[List[ExtractedImage]] = None
) -> dict:
    """
    Merge inspection and thermal data into a unified DDR structure using Gemini.
    """
    logger.info("Merging inspection + thermal data into DDR using Gemini AI...")
    
    _configure_gemini()
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    
    prompt = DDR_GENERATION_PROMPT.format(
        inspection_data=json.dumps(inspection_data, indent=2),
        thermal_data=json.dumps(thermal_data, indent=2)
    )
    
    # Retry loop for rate limits
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                )
            )
            break
        except google_exceptions.ResourceExhausted as e:
            wait = INITIAL_BACKOFF_SECONDS * attempt
            logger.warning(
                f"Rate limit hit (attempt {attempt}/{MAX_RETRIES}). "
                f"Waiting {wait}s before retry..."
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(wait)
    
    ddr_data = _parse_json_response(response.text)
    
    # Attach image metadata to the DDR
    ddr_data["_images"] = {
        "inspection": _serialize_images(inspection_images or []),
        "thermal": _serialize_images(thermal_images or [])
    }
    
    # Map images to area observations
    ddr_data = _map_images_to_areas(ddr_data, inspection_images or [], thermal_images or [])
    
    # Ensure required sections exist
    ddr_data = _ensure_required_sections(ddr_data)
    
    logger.info("DDR generation complete")
    return ddr_data


def _serialize_images(images: List[ExtractedImage]) -> list:
    """Convert ExtractedImage objects to serializable dicts (without base64 data for logging)."""
    return [
        {
            "image_path": img.image_path,
            "page_number": img.page_number,
            "image_index": img.image_index,
            "width": img.width,
            "height": img.height,
            "caption": img.caption,
            "context_text": img.context_text[:200] if img.context_text else ""
        }
        for img in images
    ]


def _map_images_to_areas(
    ddr_data: dict,
    inspection_images: List[ExtractedImage],
    thermal_images: List[ExtractedImage]
) -> dict:
    """Map extracted images to their corresponding area observations."""
    all_images = []
    
    for img in inspection_images:
        all_images.append({
            "source": "inspection",
            "base64_data": img.base64_data,
            "page_number": img.page_number,
            "caption": img.caption,
            "context_text": img.context_text,
            "width": img.width,
            "height": img.height
        })
    
    for img in thermal_images:
        all_images.append({
            "source": "thermal",
            "base64_data": img.base64_data,
            "page_number": img.page_number,
            "caption": img.caption,
            "context_text": img.context_text,
            "width": img.width,
            "height": img.height
        })
    
    # Attach all images to area observations based on context matching
    area_observations = ddr_data.get("area_observations", [])
    
    for area in area_observations:
        area_name = area.get("area_name", "").lower()
        area_images = []
        
        # Get image page references from the AI's analysis
        image_pages = area.get("image_pages", [])
        
        for img in all_images:
            context = (img.get("context_text", "") or "").lower()
            
            # Match by page reference from AI or by context text containing area name
            if img["page_number"] in image_pages:
                area_images.append(img)
            elif area_name and len(area_name) > 3 and area_name in context:
                area_images.append(img)
        
        area["matched_images"] = area_images
    
    # Any unmatched images go to a general pool
    matched_pages = set()
    for area in area_observations:
        for img in area.get("matched_images", []):
            matched_pages.add((img["source"], img["page_number"]))
    
    unmatched = [
        img for img in all_images
        if (img["source"], img["page_number"]) not in matched_pages
    ]
    ddr_data["_unmatched_images"] = unmatched
    
    return ddr_data


def _ensure_required_sections(ddr_data: dict) -> dict:
    """Ensure all 7 required DDR sections exist, even if empty."""
    defaults = {
        "property_summary": {"overall_condition": "Not Available"},
        "area_observations": [],
        "root_causes": [],
        "severity_assessment": [],
        "recommended_actions": [],
        "additional_notes": ["No additional notes."],
        "missing_information": [],
        "data_conflicts": []
    }
    
    for key, default_value in defaults.items():
        if key not in ddr_data or ddr_data[key] is None:
            ddr_data[key] = default_value
    
    return ddr_data
