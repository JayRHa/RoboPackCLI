"""Transform raw Robopack responses into normalized CLI payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _dig(data: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    """Read nested dict fields safely."""
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _normalize_scope(machine_scope: Any, user_scope: Any) -> str | None:
    machine_enabled = bool(machine_scope)
    user_enabled = bool(user_scope)
    if machine_enabled and user_enabled:
        return "machine,user"
    if machine_enabled:
        return "machine"
    if user_enabled:
        return "user"
    return None


def parse_pagination(header_value: str | None) -> dict[str, Any]:
    """Parse the X-Pagination header into a stable normalized shape."""
    payload: dict[str, Any] = {
        "total_items": None,
        "current_page": None,
        "total_pages": None,
        "page_size": None,
        "has_next_page": None,
        "has_previous_page": None,
    }
    if not header_value:
        return payload

    try:
        data = json.loads(header_value)
    except json.JSONDecodeError:
        return payload

    if not isinstance(data, Mapping):
        return payload

    # New API shape: totalCount/itemsPerPage/page/totalPages/hasNext/hasPrevious
    # Older shape: totalItems/pageSize/currentPage/...
    payload["total_items"] = data.get("totalItems", data.get("totalCount"))
    payload["current_page"] = data.get("currentPage", data.get("page"))
    payload["total_pages"] = data.get("totalPages")
    payload["page_size"] = data.get("pageSize", data.get("itemsPerPage"))
    payload["has_next_page"] = data.get("hasNextPage", data.get("hasNext"))
    payload["has_previous_page"] = data.get(
        "hasPreviousPage", data.get("hasPrevious")
    )
    return payload


def transform_app_version(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an app version payload."""
    return {
        "version_id": data.get("id"),
        "version": data.get("version"),
        "created_at": data.get("createdDate") or data.get("timestamp"),
        "updated_at": data.get("updatedDate") or data.get("timestamp"),
        "description": data.get("description"),
        "short_description": data.get("shortDescription"),
        "machine_scope": data.get("machineScope"),
        "user_scope": data.get("userScope"),
        "store_app": data.get("storeApp"),
    }


def transform_app(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an app payload."""
    versions_raw = data.get("versions") if isinstance(data.get("versions"), list) else []
    tags_raw = data.get("tags") if isinstance(data.get("tags"), list) else []
    first_version_short_description = (
        versions_raw[0].get("shortDescription")
        if versions_raw and isinstance(versions_raw[0], Mapping)
        else None
    )

    return {
        "app_id": data.get("id"),
        "identifier": data.get("identifier"),
        "name": data.get("name"),
        "publisher": data.get("publisher") or data.get("publisherName"),
        "publisher_id": data.get("publisherId"),
        "short_description": data.get("shortDescription")
        or first_version_short_description,
        "description": data.get("description"),
        "language": data.get("language"),
        "logo_url": data.get("logoUrl"),
        "logo_data": data.get("logoData"),
        "has_logo_data": data.get("logoData") is not None,
        "latest_version": data.get("version"),
        "versions": [transform_app_version(item) for item in versions_raw],
        "version_count": len(versions_raw) or (1 if data.get("version") else 0),
        "tags": [str(tag) for tag in tags_raw],
        "store_app": data.get("storeApp"),
        "verified": data.get("verified"),
        "machine_scope": data.get("machineScope"),
        "user_scope": data.get("userScope"),
        "flags": data.get("flags"),
        "created_at": data.get("createdDate") or data.get("created"),
        "updated_at": data.get("updatedDate")
        or data.get("updated")
        or data.get("lastUpdated"),
    }


def transform_apps(data: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of apps."""
    return [transform_app(item) for item in data]


def transform_package(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a package payload."""
    import_info = _dig(data, "importInfo", default={})
    if not isinstance(import_info, Mapping):
        import_info = {}
    app_info = _dig(import_info, "app", default={})
    if not isinstance(app_info, Mapping):
        app_info = {}
    program_info = _dig(import_info, "program", default={})
    if not isinstance(program_info, Mapping):
        program_info = {}

    machine_scope = data.get("machineScope")
    user_scope = data.get("userScope")
    issues_raw = data.get("issues")

    return {
        "package_id": data.get("id"),
        "name": data.get("fullProductName") or data.get("productName") or data.get("name"),
        "application_name": app_info.get("name")
        or data.get("productName")
        or _dig(data, "application", "name"),
        "application_publisher": app_info.get("publisher")
        or data.get("manufacturer")
        or _dig(data, "application", "publisher"),
        "version": data.get("productVersion")
        or data.get("latestVersion")
        or data.get("version"),
        "created_at": data.get("createdDate") or data.get("created"),
        "updated_at": data.get("updatedDate")
        or data.get("updated")
        or data.get("lastUpdated"),
        "state": data.get("state"),
        "scope": data.get("scope") or _normalize_scope(machine_scope, user_scope),
        "download_url": data.get("downloadUrl"),
        "output_formats": data.get("outputFormats")
        if isinstance(data.get("outputFormats"), list)
        else [],
        "size_bytes": data.get("size"),
        "description": app_info.get("description") or data.get("description"),
        "app_id": data.get("appId"),
        "product_name": data.get("productName"),
        "full_product_name": data.get("fullProductName"),
        "file_name": data.get("fileName"),
        "manufacturer": data.get("manufacturer"),
        "latest_version": data.get("latestVersion"),
        "download_available": data.get("downloadAvailable"),
        "new_version_available": data.get("newVersionAvailable"),
        "is_custom": data.get("isCustom"),
        "source": data.get("source"),
        "machine_scope": machine_scope,
        "user_scope": user_scope,
        "error_details": data.get("errorDetails"),
        "issues": issues_raw if isinstance(issues_raw, list) else [],
        "install_command": _dig(program_info, "installCommand"),
        "uninstall_command": _dig(program_info, "uninstallCommand"),
    }


def transform_packages(data: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of packages."""
    return [transform_package(item) for item in data]


def transform_tenant(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a tenant payload."""
    return {
        "tenant_id": data.get("id"),
        "name": data.get("name") or data.get("displayName"),
        "tenant_identifier": data.get("tenantId") or data.get("defaultDomain"),
        "client_id": data.get("clientId"),
        "created_at": data.get("createdDate") or data.get("created"),
        "updated_at": data.get("updatedDate") or data.get("updated"),
        "admin_consent_granted": data.get("adminConsentGranted"),
        "background_color": data.get("backgroundColor"),
        "flags": data.get("flags"),
    }


def transform_tenants(data: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of tenants."""
    return [transform_tenant(item) for item in data]


def transform_upload_operation(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a tenant upload operation payload."""
    return {
        "upload_id": data.get("id"),
        "tenant_id": data.get("tenantId"),
        "package_id": data.get("packageId"),
        "created_at": data.get("createdDate") or data.get("created"),
        "updated_at": data.get("updatedDate")
        or data.get("updated")
        or data.get("completedAt"),
        "started_at": data.get("startedAt"),
        "completed_at": data.get("completedAt"),
        "supports_progress": data.get("supportsProgress"),
        "progress": data.get("progress"),
        "state": data.get("state"),
        "status": data.get("status"),
        "message": data.get("message") or data.get("errorDetails"),
    }


def transform_template(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a template payload."""
    script_template_field = data.get("scriptTemplate")
    script_templates_field = data.get("scriptTemplates")
    if isinstance(script_templates_field, list):
        script_template_count = len(script_templates_field)
    elif isinstance(script_template_field, Mapping):
        script_template_count = 1
    else:
        script_template_count = 0

    return {
        "template_id": data.get("id"),
        "name": data.get("name"),
        "description": data.get("description"),
        "created_at": data.get("createdDate") or data.get("created"),
        "updated_at": data.get("updatedDate") or data.get("updated"),
        "script_template_count": script_template_count,
        "script_source_id": data.get("scriptSourceId") or _dig(data, "scriptSource", "id"),
        "script_source_name": _dig(data, "scriptSource", "name"),
        "has_banner_image": data.get("hasBannerImage"),
        "enabled": data.get("enabled"),
        "shared": data.get("shared"),
        "flags": data.get("flags"),
        "organization_id": data.get("organizationId"),
        "organization_name": data.get("organizationName"),
    }


def transform_templates(data: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of templates."""
    return [transform_template(item) for item in data]


def transform_script_template(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a script-template payload."""
    configuration = _dig(data, "configuration", default={})
    if (not isinstance(configuration, Mapping)) or not configuration:
        configuration = _dig(data, "scriptTemplate", default={})
    if not isinstance(configuration, Mapping):
        configuration = {}

    installation_progress = _dig(configuration, "psadtInstallationProgress", default={})
    if not isinstance(installation_progress, Mapping):
        installation_progress = {}
    installation_welcome = _dig(configuration, "psadtInstallationWelcome", default={})
    if not isinstance(installation_welcome, Mapping):
        installation_welcome = {}

    return {
        "script_template_id": data.get("id"),
        "name": data.get("name"),
        "description": data.get("description"),
        "created_at": data.get("createdDate") or data.get("created"),
        "updated_at": data.get("updatedDate") or data.get("updated"),
        "script_source_id": _dig(data, "scriptSource", "id")
        or data.get("scriptSourceId"),
        "script_source_name": _dig(data, "scriptSource", "name")
        or data.get("scriptSourceName"),
        "entry_point_script": _dig(configuration, "entryPointScript"),
        "detection_rule_script": _dig(configuration, "detectionRuleScript"),
        "install_command": _dig(configuration, "installCommand"),
        "uninstall_command": _dig(configuration, "uninstallCommand"),
        "company_name": _dig(configuration, "companyName"),
        "script_template_flags": _dig(configuration, "flags"),
        "log_file_directory": _dig(configuration, "logFileDirectory"),
        "log_file_directory_msi": _dig(configuration, "logFileDirectoryMsi"),
        "psadt_installation_progress_show": _dig(installation_progress, "show"),
        "psadt_installation_progress_status_message": _dig(
            installation_progress, "statusMessage"
        ),
        "psadt_installation_welcome_show": _dig(installation_welcome, "show"),
    }


def transform_script_templates(data: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of script-template payloads."""
    return [transform_script_template(item) for item in data]
