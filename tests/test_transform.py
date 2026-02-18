"""Tests for transformation helpers."""

from __future__ import annotations

from robopack_cli.transform import (
    parse_pagination,
    transform_app,
    transform_package,
    transform_script_template,
    transform_script_templates,
    transform_template,
    transform_tenant,
    transform_upload_operation,
)


def test_parse_pagination() -> None:
    raw = (
        '{"totalItems":120,"currentPage":2,"totalPages":6,'
        '"pageSize":20,"hasNextPage":true,"hasPreviousPage":true}'
    )

    transformed = parse_pagination(raw)

    assert transformed["total_items"] == 120
    assert transformed["current_page"] == 2
    assert transformed["total_pages"] == 6
    assert transformed["has_next_page"] is True


def test_parse_pagination_current_api_shape() -> None:
    raw = (
        '{"totalCount":21,"itemsPerPage":3,"page":1,'
        '"totalPages":7,"hasNext":true,"hasPrevious":false}'
    )

    transformed = parse_pagination(raw)

    assert transformed["total_items"] == 21
    assert transformed["current_page"] == 1
    assert transformed["page_size"] == 3
    assert transformed["has_previous_page"] is False


def test_transform_app() -> None:
    raw = {
        "id": "9eab3951-90a2-4ef5-b0f6-2f34db4499f0",
        "name": "7-Zip",
        "publisher": "7-Zip Team",
        "shortDescription": "File archiver",
        "description": "Compression utility",
        "language": "en",
        "logoUrl": "https://cdn.example/logo.png",
        "logoData": "BASE64",
        "tags": ["archive", "utility"],
        "versions": [
            {
                "id": "7679e579-c4d9-47b8-95e0-c76457ce6a1f",
                "version": "24.09",
                "createdDate": "2025-01-01T00:00:00Z",
                "shortDescription": "Latest",
            }
        ],
    }

    transformed = transform_app(raw)

    assert transformed["app_id"] == raw["id"]
    assert transformed["name"] == "7-Zip"
    assert transformed["has_logo_data"] is True
    assert transformed["version_count"] == 1
    assert transformed["versions"][0]["version"] == "24.09"


def test_transform_package() -> None:
    raw = {
        "id": "f13474e4-bff6-4637-9b1f-f7ce68b56dab",
        "name": "7-Zip IntuneWin",
        "version": "24.09",
        "state": "Completed",
        "scope": "machine",
        "downloadUrl": "https://cdn.example/file.intunewin",
        "size": 123456,
        "outputFormats": ["IntuneWin"],
        "application": {
            "name": "7-Zip",
            "publisher": "7-Zip Team",
        },
    }

    transformed = transform_package(raw)

    assert transformed["package_id"] == raw["id"]
    assert transformed["application_name"] == "7-Zip"
    assert transformed["state"] == "Completed"
    assert transformed["size_bytes"] == 123456


def test_transform_package_current_api_shape() -> None:
    raw = {
        "id": "3c8574eb-c0f6-426f-e557-08de6eb82a5e",
        "appId": "434e3c72-0b7c-42b2-e7a3-08dc2999ac31",
        "created": "2026-02-18T21:12:10.3492918+01:00",
        "productName": "!Dice",
        "manufacturer": "maxwinphone",
        "productVersion": "1.1.0.0",
        "state": "Completed",
        "fullProductName": "!Dice 1.1.0.0",
        "fileName": "!Dice 1.1.0.0.psadt.zip",
        "size": 8850434,
        "downloadAvailable": True,
        "newVersionAvailable": False,
        "latestVersion": "1.1.0.0",
        "source": 2,
        "isCustom": False,
        "userScope": False,
        "machineScope": True,
        "importInfo": {
            "app": {
                "publisher": "maxwinphone",
                "name": "!Dice",
                "description": "Simple Dice app",
            },
            "program": {
                "installCommand": "Deploy-Application.exe -DeployMode Silent",
                "uninstallCommand": "Deploy-Application.exe Uninstall -DeployMode Silent",
            },
        },
    }

    transformed = transform_package(raw)

    assert transformed["application_name"] == "!Dice"
    assert transformed["application_publisher"] == "maxwinphone"
    assert transformed["version"] == "1.1.0.0"
    assert transformed["scope"] == "machine"
    assert transformed["file_name"] == "!Dice 1.1.0.0.psadt.zip"
    assert transformed["install_command"] == "Deploy-Application.exe -DeployMode Silent"


def test_transform_tenant() -> None:
    raw = {
        "id": "ac6f8991-f31f-4039-9fce-6dbf7eb3f4bd",
        "name": "Contoso",
        "tenantId": "contoso.onmicrosoft.com",
        "clientId": "9fbce9ee-f3d7-41b9-a34f-45fce3345683",
        "createdDate": "2025-01-05T00:00:00Z",
    }

    transformed = transform_tenant(raw)

    assert transformed["tenant_id"] == raw["id"]
    assert transformed["tenant_identifier"] == "contoso.onmicrosoft.com"
    assert transformed["client_id"] == raw["clientId"]


def test_transform_tenant_current_api_shape() -> None:
    raw = {
        "id": "f849cde7-f11d-4ef5-a31d-7fca98b21bf5",
        "created": "2024-10-11T18:22:10.0623956+02:00",
        "displayName": "Modern Device Management",
        "defaultDomain": "ModernDevMgmt.onmicrosoft.com",
        "backgroundColor": "#0af0ba",
        "flags": 1,
        "adminConsentGranted": True,
    }

    transformed = transform_tenant(raw)

    assert transformed["name"] == "Modern Device Management"
    assert transformed["tenant_identifier"] == "ModernDevMgmt.onmicrosoft.com"
    assert transformed["background_color"] == "#0af0ba"
    assert transformed["admin_consent_granted"] is True


def test_transform_upload_operation() -> None:
    raw = {
        "id": "80ae1e16-9199-4608-b2e9-8e6c55f7f1ab",
        "tenantId": "ac6f8991-f31f-4039-9fce-6dbf7eb3f4bd",
        "packageId": "f13474e4-bff6-4637-9b1f-f7ce68b56dab",
        "state": "Running",
        "status": "Uploading",
        "message": "In progress",
    }

    transformed = transform_upload_operation(raw)

    assert transformed["upload_id"] == raw["id"]
    assert transformed["state"] == "Running"
    assert transformed["message"] == "In progress"


def test_transform_upload_operation_current_api_shape() -> None:
    raw = {
        "id": "2e85f0df-a796-4ce2-d23f-08de6eb7fd31",
        "created": "2026-02-18T22:04:30.6584752+01:00",
        "startedAt": "2026-02-18T22:04:30.8791324+01:00",
        "completedAt": None,
        "supportsProgress": False,
        "progress": None,
        "state": "Running",
    }

    transformed = transform_upload_operation(raw)

    assert transformed["created_at"] == "2026-02-18T22:04:30.6584752+01:00"
    assert transformed["started_at"] == "2026-02-18T22:04:30.8791324+01:00"
    assert transformed["supports_progress"] is False
    assert transformed["state"] == "Running"


def test_transform_template() -> None:
    raw = {
        "id": "f2cb325c-c20d-4144-b0de-1a1f3b8f74a5",
        "name": "Default",
        "description": "Default deployment template",
        "scriptTemplates": [{"id": "1"}, {"id": "2"}],
        "updatedDate": "2025-01-07T00:00:00Z",
    }

    transformed = transform_template(raw)

    assert transformed["template_id"] == raw["id"]
    assert transformed["name"] == "Default"
    assert transformed["script_template_count"] == 2


def test_transform_template_current_api_shape() -> None:
    raw = {
        "id": "152fc3a7-99e0-4c89-021e-08dc33bd3e59",
        "created": "2024-02-22T16:52:02.8129858+01:00",
        "updated": "2025-04-10T14:41:52.6892291+02:00",
        "name": "Default (PSADT 3.10.2)",
        "enabled": True,
        "organizationId": None,
        "organizationName": None,
        "shared": True,
        "flags": 10,
        "scriptSourceId": "7df70e1b-c7a1-43cc-b7d7-08dcd0f6803a",
        "scriptSource": {"id": "7df70e1b-c7a1-43cc-b7d7-08dcd0f6803a", "name": "PSADT"},
        "scriptTemplate": {"flags": 1},
        "hasBannerImage": False,
    }

    transformed = transform_template(raw)

    assert transformed["updated_at"] == "2025-04-10T14:41:52.6892291+02:00"
    assert transformed["script_template_count"] == 1
    assert transformed["script_source_name"] == "PSADT"
    assert transformed["has_banner_image"] is False


def test_transform_script_template() -> None:
    raw = {
        "id": "8b52b041-b6e1-466e-b198-903b4f6a1eb7",
        "name": "PSADT install",
        "description": "Install script",
        "createdDate": "2025-01-08T00:00:00Z",
        "updatedDate": "2025-01-09T00:00:00Z",
        "scriptSource": {
            "id": "d7a3ed67-0f3e-4118-8e6e-f2f5f21f60ca",
            "name": "PSADT Source",
        },
        "configuration": {
            "entryPointScript": "Deploy-Application.ps1",
            "detectionRuleScript": "Detect.ps1",
            "installCommand": "Deploy-Application.exe Install",
            "uninstallCommand": "Deploy-Application.exe Uninstall",
        },
    }

    transformed = transform_script_template(raw)

    assert transformed["script_template_id"] == raw["id"]
    assert transformed["script_source_name"] == "PSADT Source"
    assert transformed["entry_point_script"] == "Deploy-Application.ps1"
    assert transformed["install_command"] == "Deploy-Application.exe Install"


def test_transform_script_templates() -> None:
    raw = [
        {"id": "8b52b041-b6e1-466e-b198-903b4f6a1eb7", "name": "First"},
        {"id": "43e611a4-c7ab-4b14-9466-a4f6e4f8c733", "name": "Second"},
    ]

    transformed = transform_script_templates(raw)

    assert transformed[0]["script_template_id"] == raw[0]["id"]
    assert transformed[1]["name"] == "Second"


def test_transform_script_template_from_template_shape() -> None:
    raw = {
        "id": "152fc3a7-99e0-4c89-021e-08dc33bd3e59",
        "name": "Default (PSADT 3.10.2)",
        "created": "2024-02-22T16:52:02.8129858+01:00",
        "updated": "2025-04-10T14:41:52.6892291+02:00",
        "scriptSourceId": "7df70e1b-c7a1-43cc-b7d7-08dcd0f6803a",
        "scriptSource": {"id": "7df70e1b-c7a1-43cc-b7d7-08dcd0f6803a", "name": "PSADT"},
        "scriptTemplate": {
            "flags": 1,
            "companyName": "Contoso",
            "logFileDirectory": "C:/Windows/Logs",
            "psadtInstallationProgress": {"show": False, "statusMessage": None},
        },
    }

    transformed = transform_script_template(raw)

    assert transformed["script_template_id"] == raw["id"]
    assert transformed["name"] == "Default (PSADT 3.10.2)"
    assert transformed["script_source_name"] == "PSADT"
    assert transformed["company_name"] == "Contoso"
    assert transformed["script_template_flags"] == 1
