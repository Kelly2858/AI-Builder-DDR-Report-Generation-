"""
DDR Report Builder — Generates the final HTML DDR report using Jinja2 templates.
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import config

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


def build_html_report(ddr_data: dict, output_path: str = None) -> str:
    """
    Build the final HTML DDR report from structured DDR data.
    
    Args:
        ddr_data: Complete DDR data structure from merger
        output_path: Path to save HTML file (optional)
    
    Returns:
        HTML string of the report
    """
    logger.info("Building HTML DDR report...")
    
    # Setup Jinja2
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False  # We handle escaping in the template
    )
    template = env.get_template("ddr_report.html")
    
    # Prepare template context
    summary = ddr_data.get("property_summary", {})
    
    # Add report date if not present
    if not summary.get("report_date"):
        summary["report_date"] = datetime.now().strftime("%B %d, %Y")
    
    context = {
        "title": config.REPORT_TITLE,
        "company_name": config.COMPANY_NAME,
        "summary": summary,
        "areas": ddr_data.get("area_observations", []),
        "root_causes": ddr_data.get("root_causes", []),
        "severity_assessment": ddr_data.get("severity_assessment", []),
        "recommended_actions": ddr_data.get("recommended_actions", []),
        "additional_notes": ddr_data.get("additional_notes", []),
        "missing_information": ddr_data.get("missing_information", []),
        "data_conflicts": ddr_data.get("data_conflicts", []),
        "unmatched_images": ddr_data.get("_unmatched_images", []),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    # Render HTML
    html = template.render(**context)
    
    # Save to file
    if output_path is None:
        output_path = str(config.OUTPUT_DIR / "ddr_report.html")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"DDR report saved to: {output_path}")
    
    # Also save the raw DDR data as JSON for reference
    json_path = output_path.replace(".html", "_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        # Remove base64 image data from JSON (too large)
        clean_data = _strip_base64(ddr_data)
        json.dump(clean_data, f, indent=2, default=str)
    logger.info(f"DDR data saved to: {json_path}")
    
    return html


def _strip_base64(data):
    """Recursively remove base64 image data from nested dict/list for JSON export."""
    if isinstance(data, dict):
        return {
            k: ("[BASE64_IMAGE_DATA]" if k == "base64_data" else _strip_base64(v))
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_strip_base64(item) for item in data]
    return data
