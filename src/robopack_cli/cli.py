"""Command line interface for Robopack."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse
from uuid import UUID

from .const import (
    API_BASE_URL_PROD,
    API_KEY_ENV_VAR,
    BASE_URL_ENV_VAR,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    DEFAULT_TIMEOUT_SECONDS,
    PAGINATION_HEADER,
    PACKAGE_STATE_DESCRIPTIONS,
    UPLOAD_STATE_DESCRIPTIONS,
    VALID_DOWNLOAD_FORMATS,
    VALID_IMPORT_SCOPES,
)
from .transform import (
    parse_pagination,
    transform_app,
    transform_apps,
    transform_package,
    transform_packages,
    transform_script_template,
    transform_script_templates,
    transform_template,
    transform_templates,
    transform_tenant,
    transform_tenants,
    transform_upload_operation,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession


class CliInputError(ValueError):
    """Raised for invalid CLI argument combinations."""


class RobopackApiError(RuntimeError):
    """Raised when the API returns a non-success status."""


class RobopackAuthError(RobopackApiError):
    """Raised when authentication fails."""


class RobopackRateLimitError(RobopackApiError):
    """Raised when API rate limit is exceeded."""


class RobopackNotFoundError(RobopackApiError):
    """Raised when the requested endpoint or entity does not exist."""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="robopack",
        description=(
            "Robopack API CLI for apps, packages, tenants, templates, and script templates"
        ),
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv(API_KEY_ENV_VAR),
        help=f"Robopack API key (or env {API_KEY_ENV_VAR})",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv(BASE_URL_ENV_VAR, API_BASE_URL_PROD),
        help=(
            "Base URL (default production). "
            "Examples: https://api.robopack.com/v1, https://api-test.robopack.com/v1"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="Output as JSON"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    app_search_parser = subparsers.add_parser("app-search", help="Search apps")
    app_search_parser.add_argument("--query", required=True, help="Search query string")
    app_search_parser.add_argument(
        "--logo",
        action="store_true",
        help="Include logo data in the response payload",
    )
    _add_paging_arguments(app_search_parser)

    app_showcase_parser = subparsers.add_parser(
        "app-showcase", help="List showcase apps"
    )
    app_showcase_parser.add_argument(
        "--logo",
        action="store_true",
        help="Include logo data in the response payload",
    )
    _add_paging_arguments(app_showcase_parser)

    app_verified_parser = subparsers.add_parser(
        "app-verified", help="List verified apps"
    )
    app_verified_parser.add_argument(
        "--logo",
        action="store_true",
        help="Include logo data in the response payload",
    )
    _add_paging_arguments(app_verified_parser)

    app_get_parser = subparsers.add_parser("app-get", help="Get app details")
    app_get_parser.add_argument("--app-id", required=True, help="Application UUID")

    app_import_parser = subparsers.add_parser(
        "app-import", help="Import an application version as package"
    )
    app_import_parser.add_argument("--app-id", required=True, help="Application UUID")
    app_import_parser.add_argument(
        "--scope",
        default="machine",
        choices=VALID_IMPORT_SCOPES,
        help="Install scope",
    )
    app_import_parser.add_argument(
        "--version-id",
        help="Optional version UUID. If omitted, the latest version is imported",
    )

    package_list_parser = subparsers.add_parser("package-list", help="List packages")
    _add_paging_arguments(package_list_parser)

    package_get_parser = subparsers.add_parser(
        "package-get", help="Get package details"
    )
    package_get_parser.add_argument("--package-id", required=True, help="Package UUID")

    package_download_parser = subparsers.add_parser(
        "package-download", help="Download package artifact"
    )
    package_download_parser.add_argument(
        "--package-id", required=True, help="Package UUID"
    )
    package_download_parser.add_argument(
        "--format",
        default="IntuneWin",
        choices=VALID_DOWNLOAD_FORMATS,
        help="Artifact format",
    )
    package_download_parser.add_argument(
        "--template-id", help="Template UUID used during script generation"
    )
    package_download_parser.add_argument(
        "--no-script-wrap",
        action="store_true",
        help="Disable execution policy bypass wrapper for script formats",
    )
    package_download_parser.add_argument(
        "--output",
        help="Output file path (optional; defaults to API filename or package-based name)",
    )

    tenant_list_parser = subparsers.add_parser("tenant-list", help="List tenants")
    _add_paging_arguments(tenant_list_parser)

    tenant_get_parser = subparsers.add_parser("tenant-get", help="Get tenant details")
    tenant_get_parser.add_argument("--tenant-id", required=True, help="Tenant UUID")

    tenant_upload_parser = subparsers.add_parser(
        "tenant-upload", help="Upload package to tenant"
    )
    tenant_upload_parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    tenant_upload_parser.add_argument("--package-id", required=True, help="Package UUID")
    tenant_upload_parser.add_argument(
        "--upload-as-win32-app",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether MSIX content is uploaded as a Win32 app",
    )
    tenant_upload_parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the upload operation to complete",
    )

    tenant_upload_status_parser = subparsers.add_parser(
        "tenant-upload-status", help="Get upload operation state"
    )
    tenant_upload_status_parser.add_argument(
        "--upload-id", required=True, help="Upload operation UUID"
    )

    template_list_parser = subparsers.add_parser(
        "template-list", help="List available templates"
    )
    _add_paging_arguments(template_list_parser)

    template_get_parser = subparsers.add_parser(
        "template-get", help="Get template details"
    )
    template_get_parser.add_argument(
        "--template-id", required=True, help="Template UUID"
    )

    template_banner_parser = subparsers.add_parser(
        "template-banner", help="Download template banner image"
    )
    template_banner_parser.add_argument(
        "--template-id", required=True, help="Template UUID"
    )
    template_banner_parser.add_argument(
        "--output",
        help="Output file path (optional; defaults to API filename or template-based name)",
    )

    script_template_list_parser = subparsers.add_parser(
        "script-template-list", help="List available script templates"
    )
    _add_paging_arguments(script_template_list_parser)

    script_template_get_parser = subparsers.add_parser(
        "script-template-get", help="Get script template details"
    )
    script_template_get_parser.add_argument(
        "--script-template-id", required=True, help="Script template UUID"
    )

    return parser


def _add_paging_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--items-per-page",
        type=int,
        default=DEFAULT_ITEMS_PER_PAGE,
        help="Items per page",
    )
    parser.add_argument(
        "--page", type=int, default=DEFAULT_PAGE, help="Page index (1-based)"
    )
    parser.add_argument("--sort-by", help="Sort field")
    parser.add_argument("--sort-desc", action="store_true", help="Sort descending")


def validate_args(args: argparse.Namespace) -> None:
    """Validate argument combinations."""
    if not args.api_key:
        raise CliInputError(
            f"API key missing. Use --api-key or {API_KEY_ENV_VAR}."
        )

    parsed = urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CliInputError("--base-url must be a valid http(s) URL.")

    if args.timeout <= 0:
        raise CliInputError("--timeout must be greater than 0.")

    if hasattr(args, "items_per_page") and args.items_per_page <= 0:
        raise CliInputError("--items-per-page must be greater than 0.")

    if hasattr(args, "page") and args.page < 1:
        raise CliInputError("--page must be 1 or greater.")

    _validate_uuid_argument(args, "app_id")
    _validate_uuid_argument(args, "version_id")
    _validate_uuid_argument(args, "package_id")
    _validate_uuid_argument(args, "tenant_id")
    _validate_uuid_argument(args, "template_id")
    _validate_uuid_argument(args, "script_template_id")
    _validate_uuid_argument(args, "upload_id")

    if hasattr(args, "output") and args.output:
        output_path = Path(args.output).expanduser()
        if output_path.exists() and output_path.is_dir():
            raise CliInputError("--output points to a directory; provide a file path.")


def _validate_uuid_argument(args: argparse.Namespace, attribute: str) -> None:
    value = getattr(args, attribute, None)
    if not value:
        return
    try:
        UUID(value)
    except ValueError as error:
        flag_name = attribute.replace("_", "-")
        raise CliInputError(f"--{flag_name} must be a valid UUID.") from error


def _render_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render rows as a plain text table."""
    normalized_rows = [
        ["-" if value is None else str(value) for value in row] for row in rows
    ]
    widths = [len(h) for h in headers]

    for row in normalized_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header_line = " | ".join(
        header.ljust(widths[i]) for i, header in enumerate(headers)
    )
    separator = "-+-".join("-" * width for width in widths)
    body = [
        " | ".join(value.ljust(widths[i]) for i, value in enumerate(row))
        for row in normalized_rows
    ]

    return "\n".join([header_line, separator, *body])


def _print_pagination(pagination: Mapping[str, Any] | None) -> None:
    if not pagination or pagination.get("total_items") is None:
        return

    total_items = pagination.get("total_items")
    current_page = pagination.get("current_page")
    total_pages = pagination.get("total_pages")
    page_size = pagination.get("page_size")

    print(
        "Pagination: "
        f"page {current_page} of {total_pages}, "
        f"items/page {page_size}, total items {total_items}"
    )


def _state_description(value: Any, mapping: Mapping[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    return mapping.get(value, value)


def print_human(command: str, payload: dict[str, Any]) -> None:
    """Print result in human-readable format."""
    print(f"API: {payload['location']['base_url']}")

    if command in {"app-search", "app-showcase", "app-verified"}:
        rows = [
            [
                item.get("app_id"),
                item.get("name"),
                item.get("publisher"),
                item.get("version_count"),
                ",".join(item.get("tags") or []),
            ]
            for item in payload["apps"]
        ]
        print(
            _render_table(
                ["app_id", "name", "publisher", "versions", "tags"],
                rows,
            )
        )
        _print_pagination(payload.get("pagination"))
        return

    if command == "app-get":
        app = payload["app"]
        fields = [
            ("App ID", "app_id"),
            ("Name", "name"),
            ("Publisher", "publisher"),
            ("Language", "language"),
            ("Short description", "short_description"),
            ("Version count", "version_count"),
        ]
        for label, key in fields:
            value = app.get(key)
            print(f"{label}: {'-' if value is None else value}")

        versions = app.get("versions") or []
        if versions:
            rows = [
                [
                    item.get("version_id"),
                    item.get("version"),
                    item.get("created_at"),
                    item.get("short_description"),
                ]
                for item in versions
            ]
            print("Versions:")
            print(
                _render_table(
                    ["version_id", "version", "created_at", "short_description"],
                    rows,
                )
            )
        return

    if command == "app-import":
        print(f"App ID: {payload['app_id']}")
        print(f"Scope: {payload['scope']}")
        print(f"Version ID: {payload.get('version_id') or '-'}")
        print(f"Package ID: {payload.get('package_id') or '-'}")
        return

    if command == "package-list":
        rows = [
            [
                item.get("package_id"),
                item.get("name"),
                item.get("application_name"),
                item.get("version"),
                _state_description(item.get("state"), PACKAGE_STATE_DESCRIPTIONS),
                item.get("scope"),
            ]
            for item in payload["packages"]
        ]
        print(
            _render_table(
                ["package_id", "name", "application", "version", "state", "scope"],
                rows,
            )
        )
        _print_pagination(payload.get("pagination"))
        return

    if command == "package-get":
        package = payload["package"]
        fields = [
            ("Package ID", "package_id"),
            ("Name", "name"),
            ("Application", "application_name"),
            ("Publisher", "application_publisher"),
            ("Version", "version"),
            (
                "State",
                "state",
            ),
            ("Scope", "scope"),
            ("Size (bytes)", "size_bytes"),
            ("Created", "created_at"),
        ]
        for label, key in fields:
            value = package.get(key)
            if key == "state":
                value = _state_description(value, PACKAGE_STATE_DESCRIPTIONS)
            print(f"{label}: {'-' if value is None else value}")
        return

    if command == "package-download":
        print(f"Package ID: {payload['package_id']}")
        print(f"Format: {payload['download_format']}")
        print(f"Output: {payload['output_file']}")
        print(f"Bytes written: {payload['bytes_written']}")
        return

    if command == "tenant-list":
        rows = [
            [
                item.get("tenant_id"),
                item.get("name"),
                item.get("tenant_identifier"),
                item.get("created_at"),
            ]
            for item in payload["tenants"]
        ]
        print(_render_table(["tenant_id", "name", "tenant", "created_at"], rows))
        _print_pagination(payload.get("pagination"))
        return

    if command == "tenant-get":
        tenant = payload["tenant"]
        fields = [
            ("Tenant ID", "tenant_id"),
            ("Name", "name"),
            ("Tenant", "tenant_identifier"),
            ("Client ID", "client_id"),
            ("Created", "created_at"),
        ]
        for label, key in fields:
            value = tenant.get(key)
            print(f"{label}: {'-' if value is None else value}")
        return

    if command in {"tenant-upload", "tenant-upload-status"}:
        upload = payload["upload"]
        fields = [
            ("Upload ID", "upload_id"),
            ("Tenant ID", "tenant_id"),
            ("Package ID", "package_id"),
            (
                "State",
                _state_description(upload.get("state"), UPLOAD_STATE_DESCRIPTIONS),
            ),
            ("Status", upload.get("status")),
            ("Message", upload.get("message")),
        ]
        for label, value in fields:
            print(f"{label}: {'-' if value is None else value}")
        return

    if command == "template-list":
        rows = [
            [
                item.get("template_id"),
                item.get("name"),
                item.get("script_template_count"),
                item.get("updated_at"),
            ]
            for item in payload["templates"]
        ]
        print(
            _render_table(
                ["template_id", "name", "script_templates", "updated_at"],
                rows,
            )
        )
        _print_pagination(payload.get("pagination"))
        return

    if command == "template-get":
        template = payload["template"]
        fields = [
            ("Template ID", "template_id"),
            ("Name", "name"),
            ("Description", "description"),
            ("Script templates", "script_template_count"),
            ("Updated", "updated_at"),
        ]
        for label, key in fields:
            value = template.get(key)
            print(f"{label}: {'-' if value is None else value}")
        return

    if command == "template-banner":
        print(f"Template ID: {payload['template_id']}")
        print(f"Output: {payload['output_file']}")
        print(f"Bytes written: {payload['bytes_written']}")
        return

    if command == "script-template-list":
        print(f"Source endpoint: {payload.get('source_endpoint') or '-'}")
        rows = [
            [
                item.get("script_template_id"),
                item.get("name"),
                item.get("script_source_name"),
                item.get("template_name"),
                item.get("updated_at"),
            ]
            for item in payload["script_templates"]
        ]
        print(
            _render_table(
                [
                    "script_template_id",
                    "name",
                    "script_source",
                    "template",
                    "updated_at",
                ],
                rows,
            )
        )
        _print_pagination(payload.get("pagination"))
        return

    if command == "script-template-get":
        print(f"Source endpoint: {payload.get('source_endpoint') or '-'}")
        script_template = payload["script_template"]
        fields = [
            ("Script template ID", "script_template_id"),
            ("Name", "name"),
            ("Description", "description"),
            ("Template ID", "template_id"),
            ("Template name", "template_name"),
            ("Script source ID", "script_source_id"),
            ("Script source name", "script_source_name"),
            ("Entry point script", "entry_point_script"),
            ("Detection rule script", "detection_rule_script"),
            ("Install command", "install_command"),
            ("Uninstall command", "uninstall_command"),
            ("Updated", "updated_at"),
        ]
        for label, key in fields:
            value = script_template.get(key)
            print(f"{label}: {'-' if value is None else value}")


def _to_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _extract_script_templates_from_templates(
    templates: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for template in templates:
        template_id = template.get("id")
        template_name = template.get("name")
        nested_list = template.get("scriptTemplates")
        candidates: list[Mapping[str, Any]]
        if isinstance(nested_list, list) and nested_list:
            candidates = [item for item in nested_list if isinstance(item, Mapping)]
        else:
            candidates = [template]

        script_source = template.get("scriptSource")
        script_source_name = (
            script_source.get("name") if isinstance(script_source, Mapping) else None
        )

        for raw_item in candidates:
            item = transform_script_template(raw_item)
            item["template_id"] = template_id
            item["template_name"] = template_name

            if item.get("script_template_id") is None:
                item["script_template_id"] = template_id
            if item.get("name") is None:
                item["name"] = template_name
            if item.get("script_source_id") is None:
                item["script_source_id"] = template.get("scriptSourceId")
            if item.get("script_source_name") is None:
                item["script_source_name"] = script_source_name

            extracted.append(item)
    return extracted


def _paging_params(args: argparse.Namespace) -> dict[str, str]:
    params = {
        "itemsPerPage": str(args.items_per_page),
        "page": str(args.page),
    }
    if args.sort_by:
        params["sortBy"] = args.sort_by
    if args.sort_desc:
        params["sortDescending"] = "true"
    return params


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
    }


def _message_from_data(data: Any) -> str | None:
    if isinstance(data, Mapping):
        for key in ("message", "error", "title", "detail"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    if isinstance(data, str) and data.strip():
        return data.strip()
    return None


async def _request_json(
    session: ClientSession,
    method: str,
    url: str,
    *,
    api_key: str,
    params: Mapping[str, str] | None = None,
    json_body: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, str]]:
    async with session.request(
        method,
        url,
        headers=_auth_headers(api_key),
        params=params,
        json=json_body,
    ) as response:
        body_bytes = await response.read()
        headers = dict(response.headers)

        data: Any = None
        body_text = body_bytes.decode("utf-8", errors="replace")
        if body_text:
            try:
                data = json.loads(body_text)
            except json.JSONDecodeError:
                data = body_text

        if response.status in {401, 403}:
            raise RobopackAuthError("Invalid API key or unauthorized request.")

        if response.status == 429:
            raise RobopackRateLimitError("Request limit exceeded.")

        if response.status == 404:
            raise RobopackNotFoundError("Resource or endpoint not found.")

        if response.status >= 400:
            message = _message_from_data(data) or f"HTTP {response.status}"
            raise RobopackApiError(message)

        return data, headers


async def _request_bytes(
    session: ClientSession,
    method: str,
    url: str,
    *,
    api_key: str,
    params: Mapping[str, str] | None = None,
) -> tuple[bytes, dict[str, str]]:
    async with session.request(
        method,
        url,
        headers={"X-API-Key": api_key, "Accept": "*/*"},
        params=params,
    ) as response:
        body = await response.read()
        headers = dict(response.headers)

        if response.status in {401, 403}:
            raise RobopackAuthError("Invalid API key or unauthorized request.")

        if response.status == 429:
            raise RobopackRateLimitError("Request limit exceeded.")

        if response.status == 404:
            raise RobopackNotFoundError("Resource or endpoint not found.")

        if response.status >= 400:
            text = body.decode("utf-8", errors="replace")
            raise RobopackApiError(text.strip() or f"HTTP {response.status}")

        return body, headers


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None

    utf8_match = re.search(r"filename\*=UTF-8''([^;]+)", value, flags=re.IGNORECASE)
    if utf8_match:
        return unquote(utf8_match.group(1).strip('"'))

    match = re.search(r'filename="?([^";]+)"?', value, flags=re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _resolve_output_path(output: str | None, fallback_name: str) -> Path:
    if output:
        path = Path(output).expanduser()
    else:
        path = Path.cwd() / fallback_name

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_base_url(raw_url: str) -> str:
    return raw_url.rstrip("/")


def _base_payload(command: str, base_url: str) -> dict[str, Any]:
    return {
        "command": command,
        "location": {"base_url": base_url},
    }


async def run_command(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the selected command."""
    from aiohttp import ClientSession, ClientTimeout

    base_url = _normalize_base_url(args.base_url)
    timeout = ClientTimeout(total=args.timeout)

    async with ClientSession(timeout=timeout) as session:
        if args.command == "app-search":
            params = _paging_params(args)
            params["query"] = args.query
            if args.logo:
                params["logo"] = "true"
            data, headers = await _request_json(
                session,
                "GET",
                f"{base_url}/app",
                api_key=args.api_key,
                params=params,
            )
            return {
                **_base_payload(args.command, base_url),
                "apps": transform_apps(_to_mapping_list(data)),
                "pagination": parse_pagination(headers.get(PAGINATION_HEADER)),
            }

        if args.command == "app-showcase":
            params = _paging_params(args)
            if args.logo:
                params["logo"] = "true"
            data, headers = await _request_json(
                session,
                "GET",
                f"{base_url}/app/showcase",
                api_key=args.api_key,
                params=params,
            )
            return {
                **_base_payload(args.command, base_url),
                "apps": transform_apps(_to_mapping_list(data)),
                "pagination": parse_pagination(headers.get(PAGINATION_HEADER)),
            }

        if args.command == "app-verified":
            params = _paging_params(args)
            if args.logo:
                params["logo"] = "true"
            data, headers = await _request_json(
                session,
                "GET",
                f"{base_url}/app/verified",
                api_key=args.api_key,
                params=params,
            )
            return {
                **_base_payload(args.command, base_url),
                "apps": transform_apps(_to_mapping_list(data)),
                "pagination": parse_pagination(headers.get(PAGINATION_HEADER)),
            }

        if args.command == "app-get":
            data, _ = await _request_json(
                session,
                "GET",
                f"{base_url}/app/{args.app_id}",
                api_key=args.api_key,
            )
            app_payload = transform_app(data) if isinstance(data, Mapping) else {}
            return {
                **_base_payload(args.command, base_url),
                "app": app_payload,
            }

        if args.command == "app-import":
            params: dict[str, str] = {"scope": args.scope}
            if args.version_id:
                params["versionId"] = args.version_id

            data, _ = await _request_json(
                session,
                "POST",
                f"{base_url}/app/import/{args.app_id}",
                api_key=args.api_key,
                params=params,
            )
            package_id = None
            if isinstance(data, str):
                package_id = data
            elif isinstance(data, Mapping):
                raw_value = data.get("packageId") or data.get("id")
                package_id = str(raw_value) if raw_value is not None else None

            return {
                **_base_payload(args.command, base_url),
                "app_id": args.app_id,
                "scope": args.scope,
                "version_id": args.version_id,
                "package_id": package_id,
            }

        if args.command == "package-list":
            data, headers = await _request_json(
                session,
                "GET",
                f"{base_url}/package",
                api_key=args.api_key,
                params=_paging_params(args),
            )
            return {
                **_base_payload(args.command, base_url),
                "packages": transform_packages(_to_mapping_list(data)),
                "pagination": parse_pagination(headers.get(PAGINATION_HEADER)),
            }

        if args.command == "package-get":
            data, _ = await _request_json(
                session,
                "GET",
                f"{base_url}/package/{args.package_id}",
                api_key=args.api_key,
            )
            package_payload = transform_package(data) if isinstance(data, Mapping) else {}
            return {
                **_base_payload(args.command, base_url),
                "package": package_payload,
            }

        if args.command == "package-download":
            params = {
                "downloadFormat": args.format,
                "isScriptWrappedInExecutionPolicyByPass": str(
                    not args.no_script_wrap
                ).lower(),
            }
            if args.template_id:
                params["templateId"] = args.template_id

            data, headers = await _request_bytes(
                session,
                "GET",
                f"{base_url}/package/{args.package_id}/download",
                api_key=args.api_key,
                params=params,
            )

            filename = _filename_from_content_disposition(
                headers.get("Content-Disposition")
            )
            if filename is None:
                extension_map = {
                    "IntuneWin": "intunewin",
                    "PSADT": "zip",
                    "SourceFiles": "zip",
                    "AppV": "appv",
                    "MSIX": "msix",
                    "CIM": "cim",
                    "VHD": "vhd",
                    "VHDX": "vhdx",
                }
                extension = extension_map.get(args.format, "bin")
                filename = f"{args.package_id}.{extension}"

            output_path = _resolve_output_path(args.output, filename)
            output_path.write_bytes(data)

            return {
                **_base_payload(args.command, base_url),
                "package_id": args.package_id,
                "download_format": args.format,
                "template_id": args.template_id,
                "script_wrapped": not args.no_script_wrap,
                "output_file": str(output_path),
                "bytes_written": len(data),
            }

        if args.command == "tenant-list":
            data, headers = await _request_json(
                session,
                "GET",
                f"{base_url}/tenant",
                api_key=args.api_key,
                params=_paging_params(args),
            )
            return {
                **_base_payload(args.command, base_url),
                "tenants": transform_tenants(_to_mapping_list(data)),
                "pagination": parse_pagination(headers.get(PAGINATION_HEADER)),
            }

        if args.command == "tenant-get":
            data, _ = await _request_json(
                session,
                "GET",
                f"{base_url}/tenant/{args.tenant_id}",
                api_key=args.api_key,
            )
            tenant_payload = transform_tenant(data) if isinstance(data, Mapping) else {}
            return {
                **_base_payload(args.command, base_url),
                "tenant": tenant_payload,
            }

        if args.command == "tenant-upload":
            params = {
                "packageId": args.package_id,
                "uploadAsWin32App": str(args.upload_as_win32_app).lower(),
                "wait": str(args.wait).lower(),
            }
            data, _ = await _request_json(
                session,
                "POST",
                f"{base_url}/tenant/{args.tenant_id}/upload",
                api_key=args.api_key,
                params=params,
            )
            upload_payload = (
                transform_upload_operation(data) if isinstance(data, Mapping) else {}
            )
            return {
                **_base_payload(args.command, base_url),
                "upload": upload_payload,
            }

        if args.command == "tenant-upload-status":
            data, _ = await _request_json(
                session,
                "GET",
                f"{base_url}/tenant/upload/{args.upload_id}",
                api_key=args.api_key,
            )
            upload_payload = (
                transform_upload_operation(data) if isinstance(data, Mapping) else {}
            )
            return {
                **_base_payload(args.command, base_url),
                "upload": upload_payload,
            }

        if args.command == "template-list":
            data, headers = await _request_json(
                session,
                "GET",
                f"{base_url}/template",
                api_key=args.api_key,
                params=_paging_params(args),
            )
            return {
                **_base_payload(args.command, base_url),
                "templates": transform_templates(_to_mapping_list(data)),
                "pagination": parse_pagination(headers.get(PAGINATION_HEADER)),
            }

        if args.command == "template-get":
            data, _ = await _request_json(
                session,
                "GET",
                f"{base_url}/template/{args.template_id}",
                api_key=args.api_key,
            )
            template_payload = (
                transform_template(data) if isinstance(data, Mapping) else {}
            )
            return {
                **_base_payload(args.command, base_url),
                "template": template_payload,
            }

        if args.command == "template-banner":
            data, headers = await _request_bytes(
                session,
                "GET",
                f"{base_url}/template/{args.template_id}/banner",
                api_key=args.api_key,
            )
            filename = _filename_from_content_disposition(
                headers.get("Content-Disposition")
            )
            if filename is None:
                content_type = headers.get("Content-Type", "")
                if "png" in content_type:
                    extension = "png"
                elif "jpeg" in content_type or "jpg" in content_type:
                    extension = "jpg"
                else:
                    extension = "bin"
                filename = f"{args.template_id}-banner.{extension}"

            output_path = _resolve_output_path(args.output, filename)
            output_path.write_bytes(data)

            return {
                **_base_payload(args.command, base_url),
                "template_id": args.template_id,
                "output_file": str(output_path),
                "bytes_written": len(data),
            }

        if args.command == "script-template-list":
            params = _paging_params(args)
            source_endpoint = "script-template"

            try:
                data, headers = await _request_json(
                    session,
                    "GET",
                    f"{base_url}/script-template",
                    api_key=args.api_key,
                    params=params,
                )
                script_templates = transform_script_templates(_to_mapping_list(data))
            except RobopackNotFoundError:
                source_endpoint = "template"
                data, headers = await _request_json(
                    session,
                    "GET",
                    f"{base_url}/template",
                    api_key=args.api_key,
                    params=params,
                )
                script_templates = _extract_script_templates_from_templates(
                    _to_mapping_list(data)
                )

            return {
                **_base_payload(args.command, base_url),
                "source_endpoint": source_endpoint,
                "script_templates": script_templates,
                "pagination": parse_pagination(headers.get(PAGINATION_HEADER)),
            }

        if args.command == "script-template-get":
            source_endpoint = "script-template"

            try:
                data, _ = await _request_json(
                    session,
                    "GET",
                    f"{base_url}/script-template/{args.script_template_id}",
                    api_key=args.api_key,
                )
                payload = (
                    transform_script_template(data) if isinstance(data, Mapping) else {}
                )
            except RobopackNotFoundError:
                source_endpoint = "template"
                data, _ = await _request_json(
                    session,
                    "GET",
                    f"{base_url}/template/{args.script_template_id}",
                    api_key=args.api_key,
                )
                if isinstance(data, Mapping):
                    nested_templates = _extract_script_templates_from_templates([data])
                    payload = next(
                        (
                            item
                            for item in nested_templates
                            if item.get("script_template_id")
                            == args.script_template_id
                        ),
                        nested_templates[0] if nested_templates else {},
                    )
                    if not payload:
                        payload = transform_script_template(data)
                        payload["template_id"] = data.get("id")
                        payload["template_name"] = data.get("name")
                else:
                    payload = {}

            return {
                **_base_payload(args.command, base_url),
                "source_endpoint": source_endpoint,
                "script_template": payload,
            }

        raise RobopackApiError(f"Command not implemented: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    try:
        from aiohttp import ClientError
    except ModuleNotFoundError:
        ClientError = OSError

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_args(args)
        payload = asyncio.run(run_command(args))
    except CliInputError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    except RobopackAuthError:
        print("Error: Invalid API key.", file=sys.stderr)
        return 2
    except RobopackRateLimitError:
        print("Error: Request limit exceeded.", file=sys.stderr)
        return 2
    except ModuleNotFoundError as error:
        missing = error.name or "unknown module"
        print(
            f"Error: Missing runtime dependency '{missing}'. Install project dependencies first.",
            file=sys.stderr,
        )
        return 1
    except (RobopackApiError, ClientError, asyncio.TimeoutError, OSError) as error:
        print(f"Error while calling Robopack API: {error}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(args.command, payload)

    return 0
