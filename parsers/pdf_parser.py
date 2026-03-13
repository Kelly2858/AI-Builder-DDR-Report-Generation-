"""
PDF Parser Module — Extracts text and images from PDF documents using PyMuPDF.
"""
import fitz  # PyMuPDF
import os
import io
import base64
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    """Represents an image extracted from a document."""
    image_path: str          # Path to saved image file
    page_number: int         # Page where image was found (1-indexed)
    image_index: int         # Index of image on page
    width: int               # Image width in pixels
    height: int              # Image height in pixels
    caption: str = ""        # Nearby text that may serve as a caption
    base64_data: str = ""    # Base64 encoded image data for embedding
    context_text: str = ""   # Text near the image on the page


@dataclass
class ParsedDocument:
    """Represents a fully parsed document with text and images."""
    filename: str
    full_text: str
    pages: dict                          # {page_num: text}
    images: List[ExtractedImage] = field(default_factory=list)
    page_count: int = 0


def extract_text(filepath: str) -> str:
    """Extract all text from a PDF file."""
    doc = fitz.open(filepath)
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text("text"))
    doc.close()
    return "\n\n".join(text_parts)


def extract_text_by_pages(filepath: str) -> dict:
    """Extract text organized by page number (1-indexed)."""
    doc = fitz.open(filepath)
    pages = {}
    for i, page in enumerate(doc):
        pages[i + 1] = page.get_text("text")
    doc.close()
    return pages


def extract_images(filepath: str, output_dir: str, min_size: int = 5000) -> List[ExtractedImage]:
    """
    Extract all images from a PDF file.
    
    Args:
        filepath: Path to PDF file
        output_dir: Directory to save extracted images
        min_size: Minimum image size in bytes to include
    
    Returns:
        List of ExtractedImage objects
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(filepath)
    extracted = []
    basename = Path(filepath).stem

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if base_image is None:
                    continue

                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", "png")

                # Filter out tiny images (icons, bullets, etc.)
                if len(image_bytes) < min_size:
                    continue

                # Save the image
                img_filename = f"{basename}_page{page_num + 1}_img{img_idx + 1}.{image_ext}"
                img_path = os.path.join(output_dir, img_filename)
                with open(img_path, "wb") as f:
                    f.write(image_bytes)

                # Get image dimensions
                try:
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    width, height = pil_img.size
                except Exception:
                    width, height = base_image.get("width", 0), base_image.get("height", 0)

                # Encode as base64 for HTML embedding
                b64_data = base64.b64encode(image_bytes).decode("utf-8")
                mime_type = f"image/{image_ext}" if image_ext != "jpg" else "image/jpeg"

                # Extract context text (text near the image on the page)
                context = _extract_context_near_image(page, page_text)

                extracted.append(ExtractedImage(
                    image_path=img_path,
                    page_number=page_num + 1,
                    image_index=img_idx + 1,
                    width=width,
                    height=height,
                    caption=f"Image from page {page_num + 1}",
                    base64_data=f"data:{mime_type};base64,{b64_data}",
                    context_text=context
                ))
                logger.info(f"Extracted image: {img_filename} ({width}x{height}, {len(image_bytes)} bytes)")

            except Exception as e:
                logger.warning(f"Failed to extract image xref={xref} from page {page_num + 1}: {e}")
                continue

    doc.close()
    logger.info(f"Total images extracted from {filepath}: {len(extracted)}")
    return extracted


def _extract_context_near_image(page, page_text: str) -> str:
    """Extract text context near an image on a page for image-to-section mapping."""
    # Return the full page text as context — the AI will determine relevance
    lines = page_text.strip().split("\n")
    # Return up to 20 lines of context
    return "\n".join(lines[:20])


def extract_all(filepath: str, output_dir: str, min_size: int = 5000) -> ParsedDocument:
    """
    Extract both text and images from a PDF file.
    
    Args:
        filepath: Path to PDF file
        output_dir: Directory to save extracted images
        min_size: Minimum image size in bytes
    
    Returns:
        ParsedDocument with text and images
    """
    logger.info(f"Parsing document: {filepath}")
    
    pages = extract_text_by_pages(filepath)
    full_text = "\n\n".join(f"--- Page {k} ---\n{v}" for k, v in sorted(pages.items()))
    images = extract_images(filepath, output_dir, min_size)
    
    doc = fitz.open(filepath)
    page_count = len(doc)
    doc.close()

    parsed = ParsedDocument(
        filename=os.path.basename(filepath),
        full_text=full_text,
        pages=pages,
        images=images,
        page_count=page_count
    )
    
    logger.info(f"Parsed {parsed.filename}: {page_count} pages, {len(images)} images, {len(full_text)} chars")
    return parsed
