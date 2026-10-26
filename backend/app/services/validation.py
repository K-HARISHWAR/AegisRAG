"""Upload validation: file size limits, extension allowlists, magic signatures, and checksums."""

import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import NamedTuple

from app.core.config import get_settings

settings = get_settings()


class ValidatedFile(NamedTuple):
    """Result of successful file upload validation."""

    sanitized_filename: str
    file_type: str
    file_size_bytes: int
    checksum_sha256: str


class FileValidationError(ValueError):
    """Exception raised when an uploaded file violates security or format policies."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and filesystem attacks."""
    # Strip path components
    clean_name = Path(filename).name.strip()
    # Replace dangerous characters with underscore
    clean_name = re.sub(r'[^\w\s\.\-_]', '_', clean_name)
    # Collapse consecutive spaces
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()

    if not clean_name or clean_name.startswith('.'):
        clean_name = f"document_{clean_name}"

    # Limit filename length
    if len(clean_name) > 200:
        stem = Path(clean_name).stem[:190]
        ext = Path(clean_name).suffix
        clean_name = f"{stem}{ext}"

    return clean_name


def _verify_magic_signature(file_bytes: bytes, file_type: str) -> None:
    """Verify file magic bytes to prevent renamed malicious payloads."""
    if file_type == "pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise FileValidationError("Invalid PDF signature: file header does not match PDF specification.")

    elif file_type in ("docx", "xlsx"):
        # Both docx and xlsx are OpenXML zip packages starting with PK\x03\x04
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise FileValidationError(
                f"Invalid {file_type.upper()} signature: file is not a valid OpenXML package."
            )

        # Inspect internal zip package structure safely
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                namelist = zf.namelist()
                if "[Content_Types].xml" not in namelist:
                    raise FileValidationError(
                        f"Corrupt or spoofed {file_type.upper()}: missing [Content_Types].xml"
                    )

                if file_type == "docx":
                    if not any(name.startswith("word/") for name in namelist):
                        raise FileValidationError(
                            "Corrupt or spoofed DOCX: missing Word document structures."
                        )
                elif file_type == "xlsx":
                    if not any(name.startswith("xl/") for name in namelist):
                        raise FileValidationError(
                            "Corrupt or spoofed XLSX: missing Excel workbook structures."
                        )
        except zipfile.BadZipFile:
            raise FileValidationError(f"Corrupt {file_type.upper()}: archive is damaged or unreadable.")


def validate_file_upload(
    filename: str,
    file_bytes: bytes,
    max_size_mb: int | None = None,
) -> ValidatedFile:
    """Perform comprehensive security and format validation on uploaded file."""
    limit_mb = max_size_mb or settings.MAX_FILE_SIZE_MB
    max_bytes = limit_mb * 1024 * 1024
    file_size = len(file_bytes)

    # 1. Enforce size limit
    if file_size == 0:
        raise FileValidationError("Uploaded file is empty (0 bytes).")
    if file_size > max_bytes:
        raise FileValidationError(
            f"File size exceeds maximum allowed limit of {limit_mb} MB (received {file_size / (1024*1024):.1f} MB).",
            status_code=413,
        )

    # 2. Sanitize filename and extract extension
    sanitized = sanitize_filename(filename)
    extension = Path(sanitized).suffix.lower().lstrip(".")

    # 3. Enforce extension allowlist
    allowed = set(settings.ALLOWED_EXTENSIONS)
    if extension not in allowed:
        raise FileValidationError(
            f"Unsupported file type '.{extension}'. Allowed file types are: {', '.join(sorted(allowed))}."
        )

    # 4. Verify actual file signature / magic bytes
    _verify_magic_signature(file_bytes, extension)

    # 5. Compute SHA-256 checksum for tamper-proofing and deduplication
    checksum = hashlib.sha256(file_bytes).hexdigest()

    return ValidatedFile(
        sanitized_filename=sanitized,
        file_type=extension,
        file_size_bytes=file_size,
        checksum_sha256=checksum,
    )
