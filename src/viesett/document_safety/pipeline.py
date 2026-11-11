import asyncio
import re
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException

from viesett.domain.types import DocumentStatus


class MalwareScanner(Protocol):
    production_ready: bool

    async def clean(self, content: bytes) -> bool: ...


class SensitiveDocumentGate(Protocol):
    production_ready: bool

    async def permitted(self, filename: str, content: bytes) -> bool: ...


class UnavailableScanner:
    production_ready = False

    async def clean(self, content: bytes) -> bool:
        raise RuntimeError("Scanner unavailable")


class DevelopmentScanner:
    """Deterministic test/development double, NOT an antivirus product."""

    production_ready = False

    async def clean(self, content: bytes) -> bool:
        return b"EICAR" not in content and b"/JavaScript" not in content


class ConservativeSensitiveGate:
    """Best-effort clear markers only; cannot identify arbitrary scanned/encrypted files."""

    production_ready = False
    markers = (
        b"passport",
        b"identity card",
        b"national register",
        b"rijksregisternummer",
        b"belgian eid",
        b"medical record",
        b"bank statement",
        b"health record",
        b"genetic test",
        b"biometric template",
        b"sexual orientation",
        b"religious beliefs",
        b"political opinions",
    )

    async def permitted(self, filename: str, content: bytes) -> bool:
        sample = filename.lower().encode() + b"\n" + content.lower()
        national_identifier = re.search(
            rb"\b\d{2}[. ]?\d{2}[. ]?\d{2}[- ]?\d{3}[. ]?\d{2}\b", sample
        )
        return national_identifier is None and not any(marker in sample for marker in self.markers)


def sanitize_filename(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^a-zA-Z0-9._ -]", "_", name).strip(" .")[:180]
    return name or "document.pdf"


def validate_pdf(content: bytes, claimed_type: str) -> None:
    # This milestone deliberately accepts PDF only. Signature + EOF are type checks,
    # not a substitute for antivirus or a sandboxed parser.
    if claimed_type.split(";")[0].strip().lower() != "application/pdf":
        raise HTTPException(415, "Only PDF property documents are supported")
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
        raise HTTPException(415, "File content does not match PDF media type")


@dataclass(frozen=True)
class SafetyOutcome:
    status: DocumentStatus
    reason: str


class SafetyPipeline:
    def __init__(self, scanner: MalwareScanner, gate: SensitiveDocumentGate) -> None:
        self.scanner = scanner
        self.gate = gate

    async def inspect(self, filename: str, content: bytes) -> SafetyOutcome:
        try:
            async with asyncio.timeout(10):
                if not await self.scanner.clean(content):
                    return SafetyOutcome(DocumentStatus.REJECTED, "malware_or_active_content")
                if not await self.gate.permitted(filename, content):
                    return SafetyOutcome(DocumentStatus.QUARANTINED, "sensitive_document")
        except Exception:
            # Provider exceptions may contain uploaded bytes. Never log or echo them.
            return SafetyOutcome(DocumentStatus.QUARANTINED, "safety_check_unavailable")
        return SafetyOutcome(DocumentStatus.READY, "checks_passed")
