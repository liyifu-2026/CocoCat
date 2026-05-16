"""KB image pipeline — extract + caption + cache images from documents."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("cococat.ingest.image")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
MAX_CAPTION_CACHE = 1000


class ImagePipeline:
    """Extracts and captions images from KB source documents.

    - Detects image files in raw/sources/
    - Captions via vision LLM with SHA256 cache
    - Injects captions into wiki source-summary pages
    """

    def __init__(self, vision_llm: Any | None = None, kb_dir: str = ""):
        self._llm = vision_llm
        self._kb_dir = kb_dir
        self._cache_path = os.path.join(kb_dir, ".llm-wiki", "image-caption-cache.json") if kb_dir else ""
        self._cache: dict[str, str] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self._cache_path and os.path.exists(self._cache_path):
            try:
                with open(self._cache_path, encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    def _save_cache(self) -> None:
        if self._cache_path:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)

    def find_images(self, source_dir: str) -> list[str]:
        """Find image files in a source directory."""
        if not os.path.isdir(source_dir):
            return []
        images = []
        for fname in sorted(os.listdir(source_dir)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                images.append(os.path.join(source_dir, fname))
        return images

    def hash_image(self, image_path: str) -> Optional[str]:
        """SHA256 hash of image file content."""
        if not os.path.exists(image_path):
            return None
        with open(image_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def get_cached_caption(self, image_hash: str) -> Optional[str]:
        """Return cached caption for an image hash."""
        return self._cache.get(image_hash)

    def set_cached_caption(self, image_hash: str, caption: str) -> None:
        self._cache[image_hash] = caption
        if len(self._cache) > MAX_CAPTION_CACHE:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._save_cache()

    def extract_embedded_images(self, source_dir: str, source_filename: str) -> list[str]:
        """Extract embedded images from PDF/PPTX/DOCX source files.

        Uses the same extraction tools as the text pipeline:
        - PDF: PyMuPDF page images
        - DOCX: python-docx inline images
        - PPTX: python-pptx slide images

        Images are saved to raw/sources/{filename}_images/ directory.
        Returns list of extracted image paths.
        """

        source_path = os.path.join(source_dir, source_filename)
        if not os.path.exists(source_path):
            return []

        ext = os.path.splitext(source_filename)[1].lower()
        if ext not in (".pdf", ".docx", ".pptx"):
            return []

        images_dir = os.path.join(source_dir, f"{source_filename}_images")
        os.makedirs(images_dir, exist_ok=True)

        extracted: list[str] = []

        try:
            if ext == ".pdf":
                extracted = self._extract_pdf_images(source_path, images_dir)
            elif ext == ".docx":
                extracted = self._extract_docx_images(source_path, images_dir)
            elif ext == ".pptx":
                extracted = self._extract_pptx_images(source_path, images_dir)
        except Exception:
            logger.exception("Image extraction failed for %s", source_filename)

        return extracted

    def _extract_pdf_images(self, source_path: str, images_dir: str) -> list[str]:
        """Extract images from PDF using PyMuPDF."""
        try:
            import fitz
        except ImportError:
            return []

        doc = fitz.open(source_path)
        extracted = []
        for page_num, page in enumerate(doc):
            for img_idx, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                ext = base_image["ext"]
                fname = f"page{page_num+1}_img{img_idx+1}.{ext}"
                path = os.path.join(images_dir, fname)
                with open(path, "wb") as f:
                    f.write(img_bytes)
                extracted.append(path)
        doc.close()
        return extracted

    def _extract_docx_images(self, source_path: str, images_dir: str) -> list[str]:
        """Extract images from DOCX using python-docx."""
        try:
            from docx import Document
        except ImportError:
            return []

        doc = Document(source_path)
        extracted = []
        for i, rel in enumerate(doc.part.rels.values()):
            if "image" in rel.reltype:
                img = rel.target_part
                ext = os.path.splitext(img.partname)[1] or ".png"
                fname = f"image_{i+1}{ext}"
                path = os.path.join(images_dir, fname)
                with open(path, "wb") as f:
                    f.write(img.blob)
                extracted.append(path)
        return extracted

    def _extract_pptx_images(self, source_path: str, images_dir: str) -> list[str]:
        """Extract images from PPTX using python-pptx."""
        try:
            from pptx import Presentation
        except ImportError:
            return []

        prs = Presentation(source_path)
        extracted = []
        for slide_num, slide in enumerate(prs.slides):
            for shape_num, shape in enumerate(slide.shapes):
                if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
                    img = shape.image
                    ext = img.content_type.split("/")[-1] or "png"
                    fname = f"slide{slide_num+1}_img{shape_num+1}.{ext}"
                    path = os.path.join(images_dir, fname)
                    with open(path, "wb") as f:
                        f.write(img.blob)
                    extracted.append(path)
        return extracted

    async def caption_image(self, image_path: str) -> Optional[str]:
        """Generate caption for an image using vision LLM.

        Checks cache first. Returns None if no vision LLM configured.
        """
        if not self._llm:
            return None

        image_hash = self.hash_image(image_path)
        if not image_hash:
            return None

        # Check cache
        cached = self.get_cached_caption(image_hash)
        if cached:
            logger.debug("Caption cache hit for %s", os.path.basename(image_path))
            return cached

        # Read image as base64
        import base64
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        # Determine mime type
        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
        mime_type = mime_map.get(ext, "image/png")

        try:
            result = await self._llm.chat(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in 1-2 sentences. Focus on what it contains and its purpose."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_data}"}},
                    ],
                }],
            )
            caption = result.content or ""
        except Exception:
            logger.exception("Image captioning failed for %s", image_path)
            return None

        # Cache the result
        self.set_cached_caption(image_hash, caption)
        return caption
