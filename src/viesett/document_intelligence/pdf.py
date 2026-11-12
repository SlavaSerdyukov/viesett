import asyncio
import io
import logging
import os
import sys
import unicodedata
from dataclasses import dataclass

from pydantic import ValidationError
from pypdf import PdfReader, overwrite_configuration
from pypdf.errors import LimitReachedError

from viesett.core.config import PROJECT_ROOT
from viesett.domain.intelligence import PageText, TextPage


class ExtractionFailure(Exception):
    def __init__(self, code: str, *, retry: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retry = retry


@dataclass(frozen=True)
class PdfLimits:
    max_bytes: int
    max_pages: int
    max_characters: int
    max_stream_bytes: int
    timeout: float = 8


def extract_text(content: bytes, limits: PdfLimits) -> PageText:
    """Called in the disposable parser process; never in the API event loop."""
    logging.getLogger("pypdf").disabled = True
    if len(content) > limits.max_bytes:
        raise ExtractionFailure("pdf_input_limit")
    overwrite_configuration(
        zlib_maximum_output_length=limits.max_stream_bytes,
        lzw_maximum_output_length=limits.max_stream_bytes,
        run_length_maximum_output_length=limits.max_stream_bytes,
        maximum_declared_stream_length=limits.max_stream_bytes,
        array_based_stream_maximum_output_length=limits.max_stream_bytes,
        stream_decoding_work_maximum_length=limits.max_stream_bytes * 4,
    )
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ExtractionFailure("encrypted_pdf")
        if not 0 < len(reader.pages) <= limits.max_pages:
            raise ExtractionFailure("pdf_page_limit")
        pages = []
        total = 0
        for number, page in enumerate(reader.pages, 1):
            stream = page.get_contents()
            if stream is not None and len(stream.get_data()) > limits.max_stream_bytes:
                raise ExtractionFailure("pdf_stream_limit")
            text = unicodedata.normalize("NFC", page.extract_text() or "").replace("\r\n", "\n")
            text = text.replace("\r", "\n").replace("\x00", "")
            total += len(text)
            if total > limits.max_characters:
                raise ExtractionFailure("pdf_text_limit")
            # A tiny header over a scan is not a usable text layer. Mixed scans
            # also require OCR; never call a partial extraction complete.
            if sum(c.isalnum() for c in text) < 30 and (page.get("/Resources") or text.strip()):
                raise ExtractionFailure("ocr_required")
            pages.append(TextPage(number=number, text=text))
        if sum(sum(c.isalnum() for c in p.text) for p in pages) < 30:
            raise ExtractionFailure("ocr_required")
        return PageText(pages=pages)
    except ExtractionFailure:
        raise
    except LimitReachedError:
        raise ExtractionFailure("pdf_stream_limit") from None
    except Exception:
        raise ExtractionFailure("malformed_pdf") from None


async def extract_isolated(content: bytes, limits: PdfLimits) -> PageText:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "viesett.document_intelligence.worker",
        str(limits.max_bytes),
        str(limits.max_pages),
        str(limits.max_characters),
        str(limits.max_stream_bytes),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    try:
        async with asyncio.timeout(limits.timeout):
            output, _ = await process.communicate(content)
        if process.returncode != 0:
            code = output.decode("ascii", errors="ignore")
            if code not in {
                "pdf_input_limit",
                "pdf_page_limit",
                "pdf_stream_limit",
                "pdf_text_limit",
                "ocr_required",
                "encrypted_pdf",
                "malformed_pdf",
            }:
                code = "parser_process_failed"
            raise ExtractionFailure(code, retry=code == "parser_process_failed")
        if len(output) > limits.max_characters * 12 + limits.max_pages * 100 + 1024:
            raise ExtractionFailure("pdf_text_limit")
        return PageText.model_validate_json(output)
    except TimeoutError:
        raise ExtractionFailure("parser_timeout", retry=True) from None
    except ValidationError:
        raise ExtractionFailure("parser_output_invalid", retry=True) from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
