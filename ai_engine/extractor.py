"""
AI Extraction Engine — Uses Google Gemini to extract structured data from documents.
"""
import json
import logging
import time
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from typing import Optional
from ai_engine.prompts import (
    INSPECTION_EXTRACTION_PROMPT,
    THERMAL_EXTRACTION_PROMPT,
)
import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 30


def _configure_gemini():
    """Configure the Gemini API client."""
    if not config.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. Please set it in your .env file.\n"
            "Get your key at: https://aistudio.google.com/app/apikey"
        )
    genai.configure(api_key=config.GEMINI_API_KEY)


def _call_gemini(prompt: str, model_name: Optional[str] = None) -> str:
    """Call Gemini API with automatic retry on rate-limit (429) errors."""
    _configure_gemini()
    model = genai.GenerativeModel(model_name or config.GEMINI_MODEL)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                )
            )
            return response.text
        except google_exceptions.ResourceExhausted as e:
            wait = INITIAL_BACKOFF_SECONDS * attempt
            logger.warning(
                f"Rate limit hit (attempt {attempt}/{MAX_RETRIES}). "
                f"Waiting {wait}s before retry... Error: {e}"
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(wait)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise


def _parse_json_response(response_text: str) -> dict:
    """Parse JSON from Gemini response, handling markdown code blocks."""
    text = response_text.strip()
    
    # Remove markdown code block wrapping if present
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
        logger.error(f"Failed to parse JSON response: {e}")
        logger.debug(f"Raw response: {text[:500]}")
        # Return a minimal structure rather than crashing
        return {"error": f"JSON parse error: {str(e)}", "raw_text": text[:2000]}


def extract_inspection_data(text: str) -> dict:
    """
    Extract structured data from inspection report text using Gemini.
    
    Args:
        text: Full text content of the inspection report
        
    Returns:
        Structured dict with observations, recommendations, etc.
    """
    logger.info("Extracting inspection data using Gemini AI...")
    prompt = INSPECTION_EXTRACTION_PROMPT.format(text=text)
    response = _call_gemini(prompt)
    data = _parse_json_response(response)
    
    obs_count = len(data.get("observations", []))
    rec_count = len(data.get("recommendations", []))
    logger.info(f"Extracted {obs_count} observations, {rec_count} recommendations from inspection report")
    return data


def extract_thermal_data(text: str) -> dict:
    """
    Extract structured data from thermal report text using Gemini.
    
    Args:
        text: Full text content of the thermal report
        
    Returns:
        Structured dict with thermal findings, recommendations, etc.
    """
    logger.info("Extracting thermal data using Gemini AI...")
    prompt = THERMAL_EXTRACTION_PROMPT.format(text=text)
    response = _call_gemini(prompt)
    data = _parse_json_response(response)
    
    findings_count = len(data.get("thermal_findings", []))
    logger.info(f"Extracted {findings_count} thermal findings from thermal report")
    return data
