"""PDF/image preparation inside the resource-limited parser process.

PDFium renders static pages without initializing forms, JavaScript or network
callbacks. Pillow normalizes local raster bytes; no external references resolve.
"""

import base64
import io
import math
import warnings
from contextlib import closing

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from app.services.strixy_office import PreparationFailure

VISUAL_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def image_data(image, limits):
    if image.width * image.height > limits["visual_max_pixels"]:
        raise PreparationFailure("visual_pixel_limit")
    reduced = max(image.size) > limits["visual_max_dimension"]
    image = ImageOps.exif_transpose(image)
    image.thumbnail((limits["visual_max_dimension"],) * 2)
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, "white")
    background.alpha_composite(rgba)
    output = io.BytesIO()
    background.convert("RGB").save(output, format="PNG")
    data = base64.b64encode(output.getvalue()).decode("ascii")
    return data, reduced


def prepare_visual(path, limits, start):
    result = {
        "fields": {},
        "images": [],
        "pages": [],
        "total_units": 0,
        "state": "read",
        "reason": None,
        "units_read": 0,
        "next_unit": start,
        "unexamined_from": None,
    }
    if not limits["supports_vision"]:
        return result | {"state": "unavailable", "reason": "vision_unavailable"}
    budget = min(
        limits["visual_max_input_bytes"], limits["attachment_max_expanded_bytes"]
    )
    maximum = min(limits["visual_max_images"], limits["attachment_max_units"])

    def accept(index, image, text="", reduced=False):
        nonlocal budget
        locator = f"page:{index + 1}" if path.suffix == ".pdf" else "image:1"
        if len(result["images"]) >= maximum:
            raise PreparationFailure("attachment_unit_limit")
        data, resized = image_data(image, limits)
        size = len(data) + len(text.encode())
        if size > budget:
            raise PreparationFailure("visual_input_limit")
        budget -= size
        field = (
            "attachment:" + locator + ":image"
            if path.suffix == ".pdf"
            else "attachment:image:1"
        )
        result["images"].append({"field": field, "data": data})
        if text:
            result["fields"]["attachment:" + locator + ":text"] = text
        state = "partly_read" if resized or reduced else "read"
        result["pages"].append(
            {
                "unit": index + 1,
                "state": state,
                "reason": (
                    "visual_resolution_reduced" if state == "partly_read" else None
                ),
            }
        )
        result["units_read"] += 1
        result["next_unit"] = index + 1
        if state == "partly_read":
            result["state"], result["reason"] = state, "visual_resolution_reduced"

    try:
        if path.suffix == ".pdf":
            with pdfium.PdfDocument(path) as document:
                if pdfium.raw.FPDF_GetSecurityHandlerRevision(document) >= 0:
                    raise PreparationFailure("encrypted_file")
                result["total_units"] = len(document)
                if not len(document) or start >= len(document):
                    raise PreparationFailure("unreadable_file")
                end = min(len(document), start + maximum)
                for index in range(start, end):
                    try:
                        with closing(document[index]) as page:
                            width, height = page.get_size()
                            if not all(
                                math.isfinite(v) and v > 0 for v in (width, height)
                            ):
                                raise PreparationFailure("unreadable_page")
                            scale = min(
                                2, limits["visual_max_dimension"] / max(width, height)
                            )
                            if (
                                math.ceil(width * scale) * math.ceil(height * scale)
                                > limits["visual_max_pixels"]
                            ):
                                raise PreparationFailure("visual_pixel_limit")
                            with closing(page.get_textpage()) as textpage:
                                if (
                                    textpage.count_chars()
                                    > limits["attachment_max_expanded_bytes"]
                                ):
                                    raise PreparationFailure(
                                        "attachment_expansion_limit"
                                    )
                                text = textpage.get_text_bounded()
                            with closing(
                                page.render(scale=scale, draw_annots=True)
                            ) as bitmap:
                                accept(index, bitmap.to_pil(), text, reduced=scale < 2)
                    except (pdfium.PdfiumError, PreparationFailure) as error:
                        reason = (
                            error.code
                            if isinstance(error, PreparationFailure)
                            else "unreadable_page"
                        )
                        result["pages"].append(
                            {
                                "unit": index + 1,
                                "state": "unavailable",
                                "reason": reason,
                            }
                        )
                        result["state"], result["reason"] = "partly_read", reason
                        result["next_unit"] = index + 1
                        if reason == "visual_input_limit":
                            result["next_unit"] = index
                            end = index
                            break
                if end < len(document):
                    result["state"] = "partly_read"
                    if result["reason"] != "visual_input_limit":
                        result["reason"] = "attachment_unit_limit"
                    result["unexamined_from"] = end + 1
                if document.get_formtype():
                    result["state"] = "partly_read"
                    result["warnings"] = ["interactive_content_unexamined"]
        else:
            result["total_units"] = 1
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    expected = {
                        ".png": "PNG",
                        ".jpg": "JPEG",
                        ".jpeg": "JPEG",
                        ".webp": "WEBP",
                    }[path.suffix]
                    if image.format != expected:
                        raise PreparationFailure("unreadable_file")
                    if getattr(image, "n_frames", 1) != 1:
                        raise PreparationFailure("animated_image_unsupported")
                    accept(0, image)
    except pdfium.PdfiumError as error:
        raise PreparationFailure(
            "encrypted_file" if error.err_code == 4 else "unreadable_file"
        ) from None
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise PreparationFailure("visual_pixel_limit") from None
    return result
