"""Constants and mappings for the Robopack CLI."""

from __future__ import annotations

from typing import Final

API_BASE_URL_PROD: Final = "https://api.robopack.com/v1"
API_BASE_URL_TEST: Final = "https://api-test.robopack.com/v1"
API_KEY_ENV_VAR: Final = "ROBOPACK_API_KEY"
BASE_URL_ENV_VAR: Final = "ROBOPACK_BASE_URL"
PAGINATION_HEADER: Final = "X-Pagination"

DEFAULT_ITEMS_PER_PAGE: Final = 50
DEFAULT_PAGE: Final = 1
DEFAULT_TIMEOUT_SECONDS: Final = 30

VALID_DOWNLOAD_FORMATS: Final[tuple[str, ...]] = (
    "IntuneWin",
    "PSADT",
    "SourceFiles",
    "AppV",
    "MSIX",
    "CIM",
    "VHD",
    "VHDX",
)

VALID_IMPORT_SCOPES: Final[tuple[str, ...]] = ("machine", "user")

PACKAGE_STATE_DESCRIPTIONS: Final[dict[str, str]] = {
    "Pending": "Import queued",
    "Running": "Import in progress",
    "Completed": "Package ready",
    "Error": "Import failed",
    "WaitingForContent": "Waiting for package content upload",
}

UPLOAD_STATE_DESCRIPTIONS: Final[dict[str, str]] = {
    "Pending": "Upload queued",
    "Running": "Upload in progress",
    "Completed": "Upload completed",
    "Error": "Upload failed",
    "Canceled": "Upload canceled",
}
