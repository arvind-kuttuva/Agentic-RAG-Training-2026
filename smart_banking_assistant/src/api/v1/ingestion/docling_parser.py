import base64
import io
import os


from dotenv import load_dotenv
from docling.datamodel.base_models import InputFormat
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from docling.datamodel.pipeline_options import (
   AcceleratorDevice,
   AcceleratorOptions,
   PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from datetime import datetime


load_dotenv()


# ---------------------------------------------------------------------------
# Docling label taxonomy (DocItemLabel enum values we care about):
#
#   section_header  — numbered or unnumbered section headings
#   title           — document-level title
#   text / paragraph— body paragraphs
#   list_item       — bullet / numbered list items
#   caption         — figure / table captions (emitted as separate nodes)
#   footnote        — footnotes at the bottom of a page
#   table           — tabular data (Docling reconstructs cell structure)
#   picture         — embedded raster / vector images
#   chart           — chart/graph images (rendered image, no raw data)
#   page_header     — running header printed on every page  ← NOISE, skipped
#   page_footer     — running footer printed on every page  ← NOISE, skipped
# ---------------------------------------------------------------------------




def parse_document(file_path: str) -> list[dict]:
   """Parse a PDF into a flat list of typed content chunks using Docling.


   Each chunk is a dict with three keys:
     content      — text or markdown representation of the element
     content_type — one of: "text", "table", "image"
     metadata     — dict with: content_type, element_type, section,
                    source_page, document_name, image_base64


   The metadata is passed to PGVector, so every
   retrieved chunk tells the query layer what kind of content it is
   and where in the document it came from.
   """


   # ── Step 1: Configure Docling pipeline ───────────────────────────────────
   # do_ocr=True          — run OCR on scanned/rasterised pages so text is
   #                        extractable even when not embedded in the PDF
   # do_table_structure   — detect table grid lines and reconstruct rows/cols
   # generate_picture_images — render each picture element to a PIL Image so
   #                           we can base64-encode it for storage
   #
   # accelerator_options — pin inference to CPU. On Apple Silicon the default
   #   (AUTO) selects the MPS/Metal backend, but Docling's layout model runs in
   #   float64 and MPS rejects float64 ("Cannot convert a MPS Tensor to float64
   #   dtype"), crashing the layout stage. CPU supports float64, so forcing it
   #   here keeps ingestion working on Macs. CUDA/CPU machines are unaffected.
   pipeline_options = PdfPipelineOptions(
       do_ocr=True,
       do_table_structure=True,
       generate_picture_images=True,
       accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU),
   )


   converter = DocumentConverter(
       allowed_formats=[InputFormat.PDF],
       format_options={
           InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
       },
   )


   # ── Step 2: Convert the PDF ───────────────────────────────────────────────
   # converter.convert() runs the full Docling pipeline:
   #   layout analysis → OCR → table structure → picture rendering
   # result.document is a DoclingDocument with a typed element tree.
   result = converter.convert(file_path)
   doc = result.document


   parsed_chunks: list[dict] = []
   # Tracks the most recently seen section heading so every chunk carries
   # the section name it belongs to — useful for filtered retrieval.
   current_section: str | None = None
   document_name = os.path.basename(file_path)


   # ── Step 3: Walk the document element tree ────────────────────────────────
   # iterate_items() yields (level, node) tuples in Docling >= 2.x.
   # level is the heading depth (1 = top-level); node is the DocItem.
   for item in doc.iterate_items():
       if isinstance(item, tuple):
           node, _ = item  # iterate_items() yields (node, level); discard level
       else:
           node = item     # older Docling versions yield bare nodes


       # label is a DocItemLabel enum value — convert to lowercase string
       # for pattern matching (e.g. "section_header", "table", "picture")
       label = str(getattr(node, "label", "")).lower()


       # ── Skip page headers/footers ─────────────────────────────────────────
       # These repeat on every page (document title, page number, date stamp)
       # and would pollute retrieval results with irrelevant noise.
       if label in ("page_header", "page_footer"):
           continue


       # ── Extract page number and bounding box from provenance ──────────────
       # prov is a list of ProvenanceItem; prov[0] covers the first (usually
       # only) occurrence of the element. bbox gives the element's position
       # on the page as left/top/right/bottom coordinates (0–1 normalised or
       # absolute, depending on Docling version).
       prov = getattr(node, "prov", None)
       page_no = prov[0].page_no if prov else None
       position: dict | None = None
       if prov and hasattr(prov[0], "bbox") and prov[0].bbox is not None:
           b = prov[0].bbox
           position = {"l": b.l, "t": b.t, "r": b.r, "b": b.b}


       def _infer_product_category(section: str | None, text: str | None = None) -> str | None:
            """Simple rule-based classification based on section/content."""
            src = f"{section or ''} {text or ''}".lower()

            if any(k in src for k in ["personal loan"]):
                return "personal loan"
            if any(k in src for k in ["home loan"]): 
                return "home loan"
            if any(k in src for k in ["fixed deposit", "fd", "deposit"]):
                return "deposit"
            if any(k in src for k in ["credit card", "card"]):
                return "card"
            if any(k in src for k in ["regulatory"]):
                return "regulatory"
            return None
 

       def _make_metadata(content_type: str, element_type: str, text: str = None, img_b64=None):
           """Build a metadata dict that is stored alongside every chunk.


           content_type  — "text" | "table" | "image"  (used by the query
                           layer to decide how to render retrieved content)
           element_type  — raw Docling label ("section_header", "table", …)
           img_b64       — base64-encoded PNG string for image elements;
                           None for text and table elements
           """
           return {
               "content_type": content_type,
               "element_type": element_type,
               "section": current_section,
               "source_page": page_no,
               "document_name": document_name,
               "position": position,       # bounding box stored in JSONB position column
               "image_base64": img_b64,    # decoded to BYTEA by db.store_chunks()
               "product_category": _infer_product_category(current_section, text),
               "created_at": datetime.utcnow().isoformat(),
           }


       # ── Section headings & document title ─────────────────────────────────
       # Update current_section so all subsequent chunks carry the correct
       # section name until the next heading is encountered.
       if "section_header" in label or label == "title":
           text = getattr(node, "text", "").strip()
           if text:
               current_section = text
               parsed_chunks.append(
                   {
                       "content": text,
                       "content_type": "text",
                       "metadata": _make_metadata("text", label, text),
                   }
               )


       # ── Tables ────────────────────────────────────────────────────────────
       # Convert table cells to clean "Header: value" plain text rows so
       # that no markdown pipe/dash symbols pollute the vector store.
       # Strategy:
       #   1. export_to_dataframe() — preferred; yields a pandas DataFrame
       #      with header row and typed cell values from Docling's grid.
       #   2. Fallback: export_to_html() stripped of tags, then plain text.
       # Each table row is serialised as "Col1: val1 | Col2: val2" so the
       # column context travels with every value and embeddings are meaningful.
       elif "table" in label:
           table_text = ""
           if hasattr(node, "export_to_dataframe"):
               try:
                   df = node.export_to_dataframe()
                   if df is not None and not df.empty:
                       rows_text: list[str] = []
                       headers = [str(c).strip() for c in df.columns]
                       for _, row in df.iterrows():
                           pairs = [
                               f"{h}: {str(v).strip()}"
                               for h, v in zip(headers, row)
                               if str(v).strip() not in ("", "nan", "None")
                           ]
                           if pairs:
                               rows_text.append("  |  ".join(pairs))
                       table_text = "\n".join(rows_text)
               except Exception:
                   pass


           # Fallback: strip HTML tags from export_to_html()
           if not table_text and hasattr(node, "export_to_html"):
               try:
                   import re as _re
                   raw_html = node.export_to_html(doc)
                   table_text = _re.sub(r"<[^>]+>", " ", raw_html or "")
                   table_text = _re.sub(r"\s+", " ", table_text).strip()
               except Exception:
                   pass


           # Last resort: raw text attribute
           if not table_text:
               table_text = getattr(node, "text", "")


           if table_text and table_text.strip():
               new_chunk = {
                    "content": table_text.strip(),
                    "content_type": "table",
                    "metadata": _make_metadata("table", "table", table_text),
               }

               if parsed_chunks and _is_table_continuation(
                    parsed_chunks[-1], 
                    table_text, 
                    new_chunk["metadata"]
               ):
                    prev = parsed_chunks[-1]
                    # ✅ merge into previous table
                    prev["content"] += "\n" + table_text.strip()

                    curr_page = new_chunk["metadata"].get("source_page")
                    if curr_page:
                        prev["metadata"]["source_page_end"] = curr_page
               else:
                    parsed_chunks.append(new_chunk)



       # ── Pictures, figures, and charts ─────────────────────────────────────
       # Charts are rendered images in Docling (no structured data is
       # extracted), so they are handled identically to pictures.
       # Extraction strategy:
       #   1. get_image(doc) — preferred; uses pre-rendered PIL Images
       #      produced when generate_picture_images=True
       #   2. .image.pil_image — fallback attribute on some Docling versions
       # The PIL Image is encoded as a base64 PNG and stored in metadata so
       # the OpenAI vision model can receive it directly during generation.
       elif "picture" in label or "figure" in label or label == "chart":
           img_b64 = None
           # .text on a PictureItem is the inline caption, if any
           caption = getattr(node, "text", "") or ""


           try:
               if hasattr(node, "get_image"):
                   pil_img = node.get_image(doc)
                   if pil_img:
                       buf = io.BytesIO()
                       pil_img.save(buf, format="PNG")
                       img_b64 = base64.b64encode(buf.getvalue()).decode()


               # Fallback path for older Docling versions
               if img_b64 is None and hasattr(node, "image") and node.image:
                   pil_img = getattr(node.image, "pil_image", None)
                   if pil_img:
                       buf = io.BytesIO()
                       pil_img.save(buf, format="PNG")
                       img_b64 = base64.b64encode(buf.getvalue()).decode()
           except Exception:
               # Image extraction is best-effort; a missing image is not
               # fatal — the caption / placeholder text is still indexed.
               pass


           # Use an OpenAI vision model to generate a rich description for this
           # image. This becomes the chunk's searchable text content — far more
           # useful than a sparse caption like "Figure 3" for embedding and
           # retrieval. Falls back to Docling caption → placeholder on failure.
           if img_b64:
               description = ''  # write your logic to get caption for the image from VLM
               content = '' # the description from vlm
           else:
               content = caption.strip() or f"[Image on page {page_no}]"
           parsed_chunks.append(
               {
                   "content": content,
                   "content_type": "image_caption",
                   "metadata": _make_metadata("image_caption", "picture", content, img_b64),
               }
           )


       # ── Plain text: paragraphs, list items, captions, footnotes, etc. ─────
       # Everything that is not a heading, table, or image falls here.
       # Empty nodes (layout artefacts with no text) are silently dropped.
       else:
           text = getattr(node, "text", "")
           if text and text.strip():
               parsed_chunks.append(
                   {
                       "content": text.strip(),
                       "content_type": "text",
                       "metadata": _make_metadata("text", label, text),
                   }
               )


   return parsed_chunks

def _is_table_continuation(prev_chunk, curr_text, curr_meta):
   if not prev_chunk:
        return False

   if prev_chunk["content_type"] != "table":
        return False

    # ✅ same section
   if prev_chunk["metadata"].get("section") != curr_meta.get("section"):
        return False

   prev_page = prev_chunk["metadata"].get("source_page")
   curr_page = curr_meta.get("source_page")

    # ✅ allow same page OR next page
   if prev_page and curr_page and curr_page - prev_page > 1:
        return False

    # ✅ check row structure similarity
   prev_lines = prev_chunk["content"].split("\n")[-3:]
   curr_lines = curr_text.split("\n")[:3]

   def avg_pipe_count(lines):
        return sum(line.count("|") for line in lines) / max(len(lines), 1)

   prev_cols = avg_pipe_count(prev_lines)
   curr_cols = avg_pipe_count(curr_lines)

   if abs(prev_cols - curr_cols) <= 1:
        return True

    # ✅ fallback: missing header pattern
   first_line = curr_lines[0].lower()

   if not any(k in first_line for k in ["rate", "amount", "tenure", "interest"]):
        return True

   return False