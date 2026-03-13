"""
Flask Web Application for DDR Report Generation.
Provides a web UI for uploading documents and viewing generated reports.
"""
import os
import sys
import uuid
import logging
import threading
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from pipeline import generate_ddr

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("DDR-WebApp")

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

# Store report generation status
report_status = {}  # {report_id: {"status": "processing"|"done"|"error", "output": path, "error": msg}}


@app.route("/")
def index():
    """Render the upload page."""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """Handle file upload and trigger DDR generation."""
    # Validate files
    if "inspection" not in request.files or "thermal" not in request.files:
        return jsonify({"error": "Both inspection and thermal reports are required"}), 400
    
    inspection_file = request.files["inspection"]
    thermal_file = request.files["thermal"]
    
    if inspection_file.filename == "" or thermal_file.filename == "":
        return jsonify({"error": "Both files must be selected"}), 400
    
    # Save uploaded files
    report_id = str(uuid.uuid4())[:8]
    upload_dir = config.UPLOAD_DIR / report_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    inspection_path = str(upload_dir / inspection_file.filename)
    thermal_path = str(upload_dir / thermal_file.filename)
    
    inspection_file.save(inspection_path)
    thermal_file.save(thermal_path)
    
    # Set output path
    output_path = str(config.OUTPUT_DIR / f"DDR_Report_{report_id}.html")
    
    # Start processing in background
    report_status[report_id] = {"status": "processing", "output": None, "error": None}
    
    thread = threading.Thread(
        target=_process_report,
        args=(report_id, inspection_path, thermal_path, output_path)
    )
    thread.daemon = True
    thread.start()
    
    return redirect(url_for("processing", report_id=report_id))


def _process_report(report_id, inspection_path, thermal_path, output_path):
    """Process report generation in background."""
    try:
        result = generate_ddr(inspection_path, thermal_path, output_path)
        report_status[report_id] = {"status": "done", "output": result, "error": None}
        logger.info(f"Report {report_id} generation complete")
    except Exception as e:
        logger.error(f"Report {report_id} generation failed: {e}", exc_info=True)
        report_status[report_id] = {"status": "error", "output": None, "error": str(e)}


@app.route("/processing/<report_id>")
def processing(report_id):
    """Show processing status page."""
    return render_template("processing.html", report_id=report_id)


@app.route("/status/<report_id>")
def status(report_id):
    """Return report generation status as JSON."""
    if report_id not in report_status:
        return jsonify({"status": "not_found"}), 404
    return jsonify(report_status[report_id])


@app.route("/report/<report_id>")
def view_report(report_id):
    """View the generated DDR report."""
    if report_id not in report_status:
        return "Report not found", 404
    
    info = report_status[report_id]
    if info["status"] != "done":
        return redirect(url_for("processing", report_id=report_id))
    
    # Serve the HTML report directly
    return send_file(info["output"])


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  DDR Report Generator — Web Interface")
    print("=" * 50)
    print(f"  Open: http://localhost:{config.FLASK_PORT}")
    print("=" * 50 + "\n")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
