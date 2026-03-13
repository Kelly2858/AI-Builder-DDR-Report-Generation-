"""
DDR Generation Pipeline — Orchestrates the full document-to-report workflow.

Usage:
    python pipeline.py --inspection "Sample Report.pdf" --thermal "Thermal Images.pdf"
    python pipeline.py -i "Sample Report.pdf" -t "Thermal Images.pdf" -o "output/my_report.html"
"""
import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from parsers.pdf_parser import extract_all
from ai_engine.extractor import extract_inspection_data, extract_thermal_data
from ai_engine.merger import merge_and_generate_ddr
from report_generator.ddr_builder import build_html_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(config.OUTPUT_DIR / "pipeline.log"), mode="w")
    ]
)
logger = logging.getLogger("DDR-Pipeline")


def generate_ddr(inspection_path: str, thermal_path: str, output_path: str = None) -> str:
    """
    Generate a DDR report from inspection and thermal documents.
    
    Args:
        inspection_path: Path to inspection report PDF
        thermal_path: Path to thermal report PDF
        output_path: Path for output HTML report
    
    Returns:
        Path to the generated HTML report
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("DDR GENERATION PIPELINE STARTED")
    logger.info("=" * 60)
    
    # ─── Step 1: Parse Documents ─────────────────────────────────
    logger.info("STEP 1/4: Parsing documents...")
    
    inspection_img_dir = str(config.EXTRACTED_IMAGES_DIR / "inspection")
    thermal_img_dir = str(config.EXTRACTED_IMAGES_DIR / "thermal")
    
    logger.info(f"  Parsing inspection report: {inspection_path}")
    inspection_doc = extract_all(inspection_path, inspection_img_dir)
    logger.info(f"  ✓ Inspection: {inspection_doc.page_count} pages, "
                f"{len(inspection_doc.images)} images, {len(inspection_doc.full_text)} chars")
    
    logger.info(f"  Parsing thermal report: {thermal_path}")
    thermal_doc = extract_all(thermal_path, thermal_img_dir)
    logger.info(f"  ✓ Thermal: {thermal_doc.page_count} pages, "
                f"{len(thermal_doc.images)} images, {len(thermal_doc.full_text)} chars")
    
    # ─── Step 2: AI Extraction ───────────────────────────────────
    logger.info("STEP 2/4: Extracting structured data using Gemini AI...")
    
    logger.info("  Extracting inspection data...")
    inspection_data = extract_inspection_data(inspection_doc.full_text)
    logger.info(f"  ✓ Inspection data extracted: {len(inspection_data.get('observations', []))} observations")
    
    logger.info("  Extracting thermal data...")
    thermal_data = extract_thermal_data(thermal_doc.full_text)
    logger.info(f"  ✓ Thermal data extracted: {len(thermal_data.get('thermal_findings', []))} findings")
    
    # ─── Step 3: Merge & Generate DDR ────────────────────────────
    logger.info("STEP 3/4: Merging data and generating DDR structure...")
    
    ddr_data = merge_and_generate_ddr(
        inspection_data=inspection_data,
        thermal_data=thermal_data,
        inspection_images=inspection_doc.images,
        thermal_images=thermal_doc.images
    )
    
    # Count sections
    section_counts = {
        "area_observations": len(ddr_data.get("area_observations", [])),
        "root_causes": len(ddr_data.get("root_causes", [])),
        "severity_assessment": len(ddr_data.get("severity_assessment", [])),
        "recommended_actions": len(ddr_data.get("recommended_actions", [])),
        "additional_notes": len(ddr_data.get("additional_notes", [])),
        "missing_information": len(ddr_data.get("missing_information", [])),
        "data_conflicts": len(ddr_data.get("data_conflicts", []))
    }
    logger.info(f"  ✓ DDR structure generated: {section_counts}")
    
    # ─── Step 4: Generate HTML Report ────────────────────────────
    logger.info("STEP 4/4: Building HTML report...")
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(config.OUTPUT_DIR / f"DDR_Report_{timestamp}.html")
    
    html = build_html_report(ddr_data, output_path)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info(f"DDR GENERATION COMPLETE in {elapsed:.1f} seconds")
    logger.info(f"Report saved to: {output_path}")
    logger.info("=" * 60)
    
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Detailed Diagnostic Report (DDR) from inspection documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py -i "Sample Report.pdf" -t "Thermal Images.pdf"
  python pipeline.py -i report.pdf -t thermal.pdf -o output/my_ddr.html
        """
    )
    parser.add_argument(
        "-i", "--inspection",
        required=True,
        help="Path to inspection report PDF"
    )
    parser.add_argument(
        "-t", "--thermal",
        required=True,
        help="Path to thermal report PDF"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output HTML file path (default: output/DDR_Report_<timestamp>.html)"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.inspection):
        print(f"ERROR: Inspection report not found: {args.inspection}")
        sys.exit(1)
    if not os.path.exists(args.thermal):
        print(f"ERROR: Thermal report not found: {args.thermal}")
        sys.exit(1)
    
    try:
        output = generate_ddr(args.inspection, args.thermal, args.output)
        print(f"\n✅ DDR Report generated successfully!")
        print(f"📄 Open in browser: {output}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\n❌ Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
