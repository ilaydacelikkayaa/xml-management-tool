import requests
import os
import xml.etree.ElementTree as ET
import shutil
from dotenv import load_dotenv
import winrm
import getpass
import base64
import re
import io
import logging
import time
from requests_ntlm import HttpNtlmAuth
from dateutil.relativedelta import relativedelta
from datetime import date
from uuid import uuid4
import json
import tempfile
from pathlib import Path
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
windows_ip = os.getenv("WINRM_HOST")
username = r"WIN-9B0E3EPO4LV\Administrator"

load_dotenv(override=True)
server_url = os.getenv("AZURE_DEVOPS_SERVER_URL")
token = os.getenv("AZURE_DEVOPS_PAT")


# A


def get_project_ntlm(collection_name: str):
    username = os.getenv("AZURE_DEVOPS_WINDOWS_USER")
    password = os.getenv("AZURE_DEVOPS_WINDOWS_PASSWORD")

    if not username or not password:
        raise ValueError("Windows kimlik bilgileri tanımlı değil.")

    url = (
        f"{server_url.rstrip('/')}/{collection_name}" "/_apis/projects?api-version=7.0"
    )

    session = requests.Session()
    session.trust_env = False
    session.auth = HttpNtlmAuth(username, password)

    response = session.get(url, timeout=15)
    response.raise_for_status()

    return response.json()


def get_work_item_ids(
    project_name: str,
    work_item_type: str,
    start_date: date | None = None,
    *,
    collection_name: str,
):
    safe_project_name = escape_wiql_value(project_name)
    safe_work_item_type = escape_wiql_value(work_item_type)

    wiql_body = {
        "query": (
            "Select [System.Id] From WorkItems "
            f"WHERE [System.WorkItemType] = '{safe_work_item_type}' "
            f"AND [System.TeamProject] = '{safe_project_name}' "
            f"AND [System.CreatedDate] >= '{start_date}'"
        )
    }

    wiql_url = (
        f"{server_url.rstrip('/')}/{collection_name}" "/_apis/wit/wiql?api-version=7.0"
    )

    logger.info("WIQL query: %s", wiql_body["query"])

    start = time.perf_counter()

    try:
        request = requests.post(
            auth=("", os.getenv("AZURE_DEVOPS_PAT")),
            url=wiql_url,
            json=wiql_body,
            timeout=15,
        )

        logger.info("WIQL HTTP status: %s", request.status_code)

        if request.status_code >= 400:
            logger.error("WIQL HTTP error: %s", request.status_code)
            logger.error("WIQL response: %s", request.text[:500])

        request.raise_for_status()

    except requests.exceptions.ReadTimeout:
        logger.error("WIQL request timed out")
        raise

    finally:
        elapsed = time.perf_counter() - start
        logger.info("WIQL request duration: %.2f seconds", elapsed)

    result = request.json()

    ids = []

    for i in result["workItems"]:
        ids.append(i["id"])

    return ids


def get_work_items(ids: list, *, collection_name: str):

    if not ids:
        return []

    id_strings = []
    for i in ids:
        id_strings.append(str(i))

    ids_csv = ",".join(id_strings)

    second_url = (
        f"{server_url.rstrip('/')}/{collection_name}/"
        f"_apis/wit/workitems?ids={ids_csv}&api-version=7.0"
    )

    request = requests.get(
        auth=("", os.getenv("AZURE_DEVOPS_PAT")),
        url=second_url,
        timeout=15,
    )

    request.raise_for_status()
    result = request.json()

    return result["value"]


def analyze_work_items(work_items: list, field_ref: str):
    filled = 0

    for i in work_items:
        field_value = i["fields"].get(field_ref)

        if field_value is not None:
            filled += 1

    total = len(work_items)
    if total == 0:
        return {"field_ref": field_ref, "total": 0, "filled": 0, "empty": 0, "rate": 0}
    empty = total - filled
    rate = (filled / total) * 100

    return {
        "field_ref": field_ref,
        "total": total,
        "filled": filled,
        "empty": empty,
        "rate": rate,
    }


def analyze_field(
    work_item_type: str,
    field_ref: str,
    project_name: str,
    start_date: date | None = None,
    *,
    collection_name: str,
):
    if start_date is None:
        start_date = date.today() - relativedelta(months=6)

    ids = get_work_item_ids(
        project_name,
        work_item_type,
        start_date,
        collection_name=collection_name,
    )

    work_items = get_work_items(
        ids,
        collection_name=collection_name,
    )

    analysis = analyze_work_items(work_items, field_ref)

    return analysis


def find_field_references(xml_path: str, field_ref: str):
    field_name = None
    field_type = None
    control_count = 0

    tree = ET.parse(xml_path)
    root = tree.getroot()

    for i in root.iter("FIELD"):
        if i.get("refname") == field_ref:
            field_name = i.get("name")
            field_type = i.get("type")

    for i in root.iter("Control"):
        if i.get("FieldName") == field_ref:
            control_count += 1

    return {
        "field_ref": field_ref,
        "field_name": field_name,
        "field_type": field_type,
        "control_count": control_count,
    }


def analyze_field_full(
    work_item_type: str,
    field_ref: str,
    xml_path: str,
    project_name: str,
    *,
    collection_name: str,
):
    usage = analyze_field(
        work_item_type,
        field_ref,
        project_name,
        collection_name=collection_name,
    )

    xml_info = find_field_references(xml_path, field_ref)

    return {"usage": usage, "xml_info": xml_info}


def evaluate_cleanup_candidate(analysis: dict):
    rate = analysis["usage"]["rate"]

    if rate == 0:
        candidate = True
    else:
        candidate = False

    return candidate


def build_field_report(analysis: dict):
    field_ref = analysis["usage"]["field_ref"]
    field_name = analysis["xml_info"]["field_name"]
    total = analysis["usage"]["total"]
    filled = analysis["usage"]["filled"]
    empty = analysis["usage"]["empty"]
    usage_rate = analysis["usage"]["rate"]
    control_count = analysis["xml_info"]["control_count"]

    candidate = evaluate_cleanup_candidate(analysis)

    return {
        "field_ref": field_ref,
        "field_name": field_name,
        "total": total,
        "filled": filled,
        "empty": empty,
        "usage_rate": usage_rate,
        "control_count": control_count,
        "candidate": candidate,
    }


def hide_field_from_ui(xml_path: str, field_ref: str, output_path: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    field_exists = False
    removed_count = 0

    for field in root.iter("FIELD"):
        if field.get("refname") == field_ref:
            field_exists = True
            break
    if not field_exists:
        return {"success": False, "message": "Field does not exist in XML"}

    for parent in root.iter():
        for child in list(parent):
            if child.tag == "Control" and child.get("FieldName") == field_ref:
                parent.remove(child)
                removed_count += 1

    if removed_count == 0:
        return {
            "success": True,
            "field_ref": field_ref,
            "status": "ALREADY_HIDDEN",
            "removed_controls": 0,
            "output_path": None,
        }

    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    return {
        "success": True,
        "field_ref": field_ref,
        "removed_controls": removed_count,
        "output_path": output_path,
    }


def validate_xml(xml_path: str):
    try:
        ET.parse(xml_path)

        return {"valid": True}

    except Exception as e:
        return {"valid": False, "error": str(e)}


def build_change_preview(
    before_analysis: dict,
    after_analysis: dict,
    validation_result: dict,
    azure_validation: bool,
):
    before_controls = before_analysis["xml_info"]["control_count"]
    after_controls = after_analysis["control_count"]

    field_preserved = after_analysis["field_name"] is not None
    xml_valid = validation_result["valid"]

    ready_to_apply = (
        before_controls > after_controls
        and field_preserved
        and xml_valid
        and azure_validation
    )

    return {
        "operation": "HIDE_FROM_UI",
        "field_ref": before_analysis["usage"]["field_ref"],
        "field_name": before_analysis["xml_info"]["field_name"],
        "before_controls": before_controls,
        "after_controls": after_controls,
        "field_preserved": field_preserved,
        "xml_validation": xml_valid,
        "azure_validation": azure_validation,
        "ready_to_apply": ready_to_apply,
    }


def can_apply_change(preview: dict, confirmed: bool):
    technical_ready = preview["ready_to_apply"]

    apply_allowed = technical_ready and confirmed

    return {
        "technical_ready": technical_ready,
        "confirmed": confirmed,
        "apply_allowed": apply_allowed,
    }


def prepare_apply(confirmation_result: dict, preview_xml_path: str):
    apply_allowed = confirmation_result["apply_allowed"]
    if apply_allowed == False:
        return {"success": False, "message": "Apply is not allowed"}
    else:
        return {
            "success": True,
            "status": "READY_FOR_IMPORT",
            "xml_path": preview_xml_path,
        }


def build_import_command(
    prepare_result: dict, collection_url: str, project: str, windows_path: str
):
    result = prepare_result["success"]
    if result == False:
        return {"error": "is not true"}
    else:
        command = f"witadmin importwitd /collection:{collection_url} /p:{project} /f:{windows_path}"
        return {"success": True, "command": command}


def build_export_command(
    witadmin: str,
    collection_url: str,
    project: str,
    work_item_type: str,
    output_path: str,
):
    if (
        not witadmin
        or not collection_url
        or not project
        or not work_item_type
        or not output_path
    ):
        return {"success": False, "error": "Missing required parameter"}
    args = [
        "exportwitd",
        f"/collection:{collection_url}",
        f"/p:{project}",
        f"/n:{work_item_type}",
        f"/f:{output_path}",
    ]
    return {"success": True, "program": witadmin, "args": args}


def execute_command(program: str, args: list, session: winrm.Session):
    try:
        result = session.run_cmd(f'"{program}"', args)

        return {
            "success": result.status_code == 0,
            "status_code": result.status_code,
            "stdout": result.std_out.decode(errors="replace").strip(),
            "stderr": result.std_err.decode(errors="replace").strip(),
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
            "error_type": "REMOTE_EXECUTION_ERROR",
        }


witadmin_path = (
    r"C:\Program Files\Microsoft Visual Studio\18\TeamExplorer"
    r"\Common7\IDE\CommonExtensions\Microsoft"
    r"\TeamFoundation\Team Explorer\witadmin.exe"
)


def verify(verification_result: dict):
    field_name = verification_result["field_name"]
    control_count = verification_result["control_count"]
    if field_name != None and control_count == 0:
        return {"verified": True}
    else:
        return {"verified": False}


def check_remote_file(session: winrm.Session, remote_path: str):
    script = f'Test-Path "{remote_path}"'
    result = session.run_ps(script)
    return result


def read_remote_xml(session: winrm.Session, remote_path: str):

    script = rf"""
    $bytes = [System.IO.File]::ReadAllBytes("{remote_path}")
    [Convert]::ToBase64String($bytes)"""
    result = session.run_ps(script)
    if result.status_code != 0:
        raise RuntimeError("Uzak sunucudaki XML okunamadı")
    xml_bytes = base64.b64decode(result.std_out.strip(), validate=True)
    return xml_bytes


def is_xml_response_valid(response):
    if response.status_code != 0:
        return False

    if not response.std_out.strip():
        return False

    return True


def escape_wiql_value(value: str) -> str:
    result = value.replace("'", "''")
    return result


def list_xml_fields(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    fields = []
    work_item_type = root.find("{*}WORKITEMTYPE")

    if work_item_type is None:
        raise ValueError("WORKITEMTYPE bölümü bulunamadı")
    fields_section = work_item_type.find("{*}FIELDS")

    if fields_section is None:
        raise ValueError("FIELDS bölümü bulunamadı")
    for field in fields_section.findall("{*}FIELD"):
        name = field.get("name")
        refname = field.get("refname")
        field_type = field.get("type")
        if name is None or refname is None or field_type is None:
            raise ValueError(f"Eksik FIELD bilgisi: {field.attrib}")
        field_info = {"name": name, "refname": refname, "field_type": field_type}
        fields.append(field_info)
    return fields


def ensure_remote_directory(session: winrm.Session, directory: str):
    script = r"""
    $path = "C:\Temp"

    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    """

    result = session.run_ps(script)

    if result.status_code != 0:
        raise RuntimeError("Windows geçici klasörü oluşturulamadı")


def get_project_xml(
    session: winrm.Session, collection_name: str, project_name: str, work_item_type: str
):
    collection_url = get_collection_url(collection_name, for_witadmin=True)
    remote_xml_path = rf"C:\Temp\wit-{uuid4().hex}.xml"
    ensure_remote_directory(session, remote_xml_path)
    witadmin_exe = find_witadmin_path(session)

    export_result = build_export_command(
        witadmin_exe, collection_url, project_name, work_item_type, remote_xml_path
    )
    if not export_result["success"]:
        raise RuntimeError("Export komutu hazırlanamadı")

    try:
        execute_result = execute_command(
            export_result["program"], export_result["args"], session
        )
        if not execute_result["success"]:
            raise RuntimeError(
                f"XML export başarısız: {execute_result.get('stderr') or execute_result.get('error')}"
            )
        xml_bytes = read_remote_xml(session, remote_xml_path)
        return xml_bytes

    finally:
        try:
            cleanup_result = session.run_cmd(
                "cmd.exe", ["/c", "del", "/q", remote_xml_path]
            )
            if cleanup_result.status_code != 0:
                logger.warning("Geçici XML dosyası temizlenemedi")
        except Exception:
            logger.warning("Geçici XML temizleme işlemi başarısız")


def create_winrm_session():
    windows_ip = os.getenv("WINRM_HOST")
    username = os.getenv("WINRM_USERNAME")
    password = os.getenv("WINRM_PASSWORD")
    if not all([windows_ip, username, password]):
        raise RuntimeError("WinRM bağlantı bilgileri eksik")
    session = winrm.Session(
        f"http://{windows_ip}:5985/wsman",
        auth=(username, password),
        transport="ntlm",
        message_encryption="always",
    )
    return session


def get_collections():
    # 1. Bağlantı bilgilerini al
    windows_ip = os.getenv("WINRM_HOST")
    username = os.getenv("WINRM_USERNAME")
    password = os.getenv("WINRM_PASSWORD")
    server_url = os.getenv("AZURE_DEVOPS_SERVER_URL")

    if not all([windows_ip, username, password, server_url]):
        raise RuntimeError("Azure DevOps veya WinRM bağlantı bilgileri eksik")

    session = winrm.Session(
        f"http://{windows_ip}:5985/wsman",
        auth=(username, password),
        transport="ntlm",
        message_encryption="always",
    )

    powershell_script = r"""
$ErrorActionPreference = "Stop"

$dllPath = "C:\Program Files\Azure DevOps Server 2022\Application Tier\Web Services\bin\Microsoft.TeamFoundation.Client.dll"

$serverUrl = __SERVER_URL__

Add-Type -Path $dllPath

$server = [Microsoft.TeamFoundation.Client.TfsConfigurationServerFactory]::GetConfigurationServer([Uri]$serverUrl)

$server.EnsureAuthenticated()

$types = [System.Guid[]]@(
    [Microsoft.TeamFoundation.Framework.Common.CatalogResourceTypes]::ProjectCollection
)

$collections = $server.CatalogNode.QueryChildren(
    $types,
    $false,
    [Microsoft.TeamFoundation.Framework.Common.CatalogQueryOptions]::None
)

$names = @(
    $collections | ForEach-Object {
        $_.Resource.DisplayName
    }
)

ConvertTo-Json -InputObject $names -Compress
"""

    server_url_ps = "'" + server_url.replace("'", "''") + "'"
    powershell_script = powershell_script.replace("__SERVER_URL__", server_url_ps)

    result = session.run_ps(powershell_script)

    if result.status_code != 0:
        error_message = result.std_err.decode("utf-8", errors="replace")
        raise RuntimeError(error_message)

    output = result.std_out.decode("utf-8-sig", errors="replace").strip()

    if not output:
        raise RuntimeError("Collection sorgusu boş çıktı döndürdü")

    return json.loads(output)


def get_project(collection_name: str):
    token = os.getenv("AZURE_DEVOPS_PAT")
    url = f"{server_url.rstrip('/')}/{collection_name}/_apis/projects?api-version=7.0"

    session = requests.Session()
    session.trust_env = False

    response = session.get(url, auth=("", token), timeout=15)
    print("Collection:", collection_name)
    print("PAT mevcut mu:", bool(token))
    from dotenv import dotenv_values

    env_pat = dotenv_values(".env").get("AZURE_DEVOPS_PAT")

    print("Çalışan PAT .env ile aynı mı?", token == env_pat)
    print("HTTP Status:", response.status_code)
    response.raise_for_status()
    return response.json()


def get_work_item_types(collection_name: str, project_name: str):
    token = os.getenv("AZURE_DEVOPS_PAT")

    if not token or not server_url:
        raise RuntimeError("Azure DevOps bağlantı bilgileri eksik")

    url = f"{server_url.rstrip('/')}/{collection_name}/{project_name}/_apis/wit/workitemtypes?api-version=7.0"

    response = requests.get(
        url=url, auth=("", token), timeout=60, proxies={"http": "", "https": ""}
    )

    response.raise_for_status()
    return response.json()


def preview_hide_field(
    session: winrm.Session,
    collection_name: str,
    project_name: str,
    work_item_type: str,
    field_ref: str,
):
    xml_bytes = get_project_xml(session, collection_name, project_name, work_item_type)
    if not xml_bytes:
        raise RuntimeError("Azure DevOps'tan boş XML döndü")

    with tempfile.TemporaryDirectory() as temp_dir:

        original_path = Path(temp_dir) / "original.xml"
        preview_path = Path(temp_dir) / "preview.xml"

        with open(original_path, "wb") as f:
            f.write(xml_bytes)

        hide_result = hide_field_from_ui(
            str(original_path), field_ref, str(preview_path)
        )
        print("HIDE RESULT:", hide_result)
        print("PREVIEW PATH:", preview_path)
        print("PREVIEW EXISTS:", preview_path.exists())

        if hide_result.get("status") == "ALREADY_HIDDEN":
            return {
                "success": True,
                "status": "ALREADY_HIDDEN",
                "field_ref": field_ref,
                "removed_controls": 0,
                "message": "Bu alan zaten gizli. Herhangi bir değişiklik yapılmadı.",
            }

        if not hide_result["success"]:
            return hide_result

        if not preview_path.exists():
            raise RuntimeError("Preview XML oluşturulamadı")

        validation_result = validate_xml(str(preview_path))

        if not validation_result["valid"]:
            raise RuntimeError("Preview XML geçersiz")

        with open(preview_path, "r", encoding="utf-8") as f:
            preview_xml = f.read()

        return {
            "success": True,
            "field_ref": field_ref,
            "removed_controls": hide_result["removed_controls"],
            "preview_xml": preview_xml,
            "message": "Preview oluşturuldu. Azure DevOps'a uygulanmadı.",
        }


def get_field_visibility(xml_path: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    visible_fields = set()

    for element in root.iter():
        if element.tag.split("}")[-1] == "Control":
            field_name = element.get("FieldName")

            if field_name:
                visible_fields.add(field_name)

    field_statuses = []
    processed_fields = set()

    for element in root.iter():
        if element.tag.split("}")[-1] == "FIELD":
            field_ref = element.get("refname")

            if not field_ref or field_ref in processed_fields:
                continue

            processed_fields.add(field_ref)

            if field_ref in visible_fields:
                status = "VISIBLE"
            else:
                status = "ALREADY_HIDDEN"

            field_statuses.append({"field_ref": field_ref, "status": status})

    return field_statuses


def local_tag(element):
    return element.tag.split("}")[-1]


def find_fields_element(root):
    for element in root.iter():
        if local_tag(element) == "FIELDS":
            return element
    return None


def add_field_to_form(root, field_ref: str, field_name: str):
    def tag_name(element):
        return element.tag.split("}")[-1]

    form = next(
        (e for e in root.iter() if tag_name(e) == "FORM"),
        None,
    )
    if form is None:
        raise ValueError("XML içinde FORM bulunamadı.")

    added_controls = 0
    existing_controls = 0
    supported_layouts = 0

    for layout_name in ("Layout", "WebLayout"):
        layout = next(
            (e for e in form if tag_name(e) == layout_name),
            None,
        )
        if layout is None:
            continue

        supported_layouts += 1

        if any(
            tag_name(e) == "Control" and e.get("FieldName") == field_ref
            for e in layout.iter()
        ):
            existing_controls += 1
            continue

        groups = [e for e in layout.iter() if tag_name(e) == "Group"]

        def group_is_safe(group):
            controls = [e for e in group.iter() if tag_name(e) == "Control"]

            # Özel kontrol barındıran grupları kullanma.
            return all(c.get("Type") == "FieldControl" for c in controls)

        safe_groups = [group for group in groups if group_is_safe(group)]

        # Önce Planning, ardından diğer normal alan grupları.
        safe_groups.sort(
            key=lambda group: (
                group.get("Label") != "Planning",
                group.get("Label") != "Bug Details",
            )
        )

        target = None

        for group in safe_groups:
            if layout_name == "Layout":
                target = next(
                    (e for e in group.iter() if tag_name(e) == "Column"),
                    None,
                )
            else:
                target = group

            if target is not None:
                break

        if target is None:
            raise ValueError(f"{layout_name} içinde güvenli Group bulunamadı.")

        namespace = target.tag.rsplit("}", 1)[0] + "}" if "}" in target.tag else ""

        attributes = {
            "FieldName": field_ref,
            "Type": "FieldControl",
            "Label": field_name,
        }

        if layout_name == "Layout":
            attributes["LabelPosition"] = "Left"

        ET.SubElement(
            target,
            f"{namespace}Control",
            attributes,
        )

        added_controls += 1

    if supported_layouts == 0:
        raise ValueError("FORM içinde Layout veya WebLayout bulunamadı.")

    if added_controls == 0 and existing_controls == 0:
        raise ValueError("Alan hiçbir layout içine eklenemedi.")

    return added_controls


def remove_field_controls(root, field_ref):
    removed_count = 0

    def local_name(element):
        return element.tag.split("}")[-1]

    for form in root.iter():
        if local_name(form) != "FORM":
            continue

        for parent in form.iter():
            for child in list(parent):
                if (
                    local_name(child) == "Control"
                    and child.get("FieldName") == field_ref
                ):
                    parent.remove(child)
                    removed_count += 1

    return removed_count


def update_field_form_visibility(root, field_ref, field_name, show_on_form):
    if show_on_form is None:
        return {
            "action": "UNCHANGED",
            "added_controls": 0,
            "removed_controls": 0,
        }

    if show_on_form is False:
        removed = remove_field_controls(root, field_ref)

        return {
            "action": "HIDDEN",
            "added_controls": 0,
            "removed_controls": removed,
        }

    # Açma işleminden önce mevcut Control'leri kontrol ediyoruz.
    def local_name(element):
        return element.tag.split("}")[-1]

    form = next(
        (element for element in root.iter() if local_name(element) == "FORM"),
        None,
    )

    if form is None:
        raise ValueError("FORM bölümü bulunamadı.")

    layouts = {}

    for layout_name in ("Layout", "WebLayout"):
        layout = next(
            (child for child in form if local_name(child) == layout_name),
            None,
        )

        if layout is None:
            raise ValueError(f"{layout_name} bulunamadı.")

        layouts[layout_name] = sum(
            1
            for element in layout.iter()
            if local_name(element) == "Control"
            and element.get("FieldName") == field_ref
        )

    if all(count == 1 for count in layouts.values()):
        return {
            "action": "ALREADY_VISIBLE",
            "added_controls": 0,
            "removed_controls": 0,
        }

    # Kısmi veya tekrar eden Control durumu varsa
    # otomatik değiştirmek yerine duruyoruz.
    if any(count > 0 for count in layouts.values()):
        raise ValueError(f"Beklenmeyen Control dağılımı: {layouts}")

    added = add_field_to_form(root, field_ref, field_name)

    if added != 2:
        raise ValueError(f"İki Control bekleniyordu, {added} eklendi.")

    return {
        "action": "SHOWN",
        "added_controls": added,
        "removed_controls": 0,
    }


def add_field_to_xml(
    xml_path: str,
    field_name: str,
    field_ref: str,
    field_type: str,
    output_path: str,
    is_required: bool = False,
    is_read_only: bool = False,
    show_on_form: bool = True,
    help_text: str | None = None,
):
    allowed_types = {
        "String",
        "Integer",
        "Double",
        "DateTime",
        "Boolean",
        "PlainText",
        "HTML",
        "History",
        "TreePath",
        "GUID",
        "Identity",
    }

    if field_type not in allowed_types:
        raise ValueError("Desteklenmeyen alan tipi")

    if not field_name.strip() or not field_ref.strip():
        raise ValueError("Alan adı ve referans adı boş olamaz")

    if Path(xml_path).resolve() == Path(output_path).resolve():
        raise ValueError("Orijinal XML dosyasının üzerine yazılamaz")

    namespace_events = ET.iterparse(
        io.BytesIO(Path(xml_path).read_bytes()), events=("start-ns",)
    )

    for _, (prefix, uri) in namespace_events:
        if prefix in {"xml", "xmlns"}:
            continue
        ET.register_namespace(prefix or "", uri)

    tree = ET.parse(xml_path)
    root = tree.getroot()

    fields_element = find_fields_element(root)

    if fields_element is None:
        raise ValueError("XML içinde FIELDS bölümü bulunamadı")

    for field in fields_element:
        if local_tag(field) != "FIELD":
            continue

        if field.get("refname") == field_ref:
            raise ValueError("Bu referans adına sahip alan zaten var")

        if field.get("name") == field_name:
            raise ValueError("Bu isimde bir alan zaten var")

    namespace = (
        fields_element.tag.rsplit("}", 1)[0] + "}" if "}" in fields_element.tag else ""
    )
    if is_required and is_read_only:
        raise ValueError("Bir alan aynı anda Required ve Read Only olamaz.")

    new_field = ET.SubElement(
        fields_element,
        f"{namespace}FIELD",
        {"name": field_name, "refname": field_ref, "type": field_type},
    )

    if is_required:
        ET.SubElement(new_field, f"{namespace}REQUIRED")

    if is_read_only:
        ET.SubElement(new_field, f"{namespace}READONLY")

    if help_text and help_text.strip():
        help_element = ET.SubElement(new_field, f"{namespace}HELPTEXT")
        help_element.text = help_text.strip()
    if show_on_form:
        added_controls = add_field_to_form(
            root,
            field_ref,
            field_name,
        )
    else:
        added_controls = 0
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    return {
        "success": True,
        "action": "ADD_FIELD",
        "field_ref": field_ref,
        "output_path": output_path,
        "added_controls": added_controls,
    }


def get_field_settings(xml_path: str, field_ref: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    def local_name(element):
        return element.tag.split("}")[-1]

    # Yalnızca WORKITEMTYPE altındaki ana FIELDS bölümünü bul.
    work_item_type = next(
        (element for element in root.iter() if local_name(element) == "WORKITEMTYPE"),
        None,
    )

    if work_item_type is None:
        raise ValueError("WORKITEMTYPE bulunamadı.")

    fields = next(
        (child for child in work_item_type if local_name(child) == "FIELDS"),
        None,
    )

    if fields is None:
        raise ValueError("Ana FIELDS bölümü bulunamadı.")

    matching_fields = [
        child
        for child in fields
        if local_name(child) == "FIELD" and child.get("refname") == field_ref
    ]

    if len(matching_fields) != 1:
        raise ValueError("Field bulunamadı veya birden fazla tanım var.")

    field = matching_fields[0]

    rules = {local_name(child): child for child in field}

    form = next(
        (child for child in work_item_type if local_name(child) == "FORM"),
        None,
    )

    layouts = {}

    if form is not None:
        for layout_name in ("Layout", "WebLayout"):
            layout = next(
                (child for child in form if local_name(child) == layout_name),
                None,
            )

            layouts[layout_name] = layout is not None and any(
                local_name(element) == "Control"
                and element.get("FieldName") == field_ref
                for element in layout.iter()
            )

    help_element = rules.get("HELPTEXT")

    return {
        "field_ref": field_ref,
        "field_name": field.get("name"),
        "field_type": field.get("type"),
        "is_required": "REQUIRED" in rules,
        "is_read_only": "READONLY" in rules,
        "help_text": (help_element.text or "" if help_element is not None else ""),
        "show_on_form": any(layouts.values()),
        "form_locations": layouts,
    }


def update_field_rules(
    field,
    is_required=None,
    is_read_only=None,
    help_text=None,
):
    def local_name(element):
        return element.tag.split("}")[-1]

    existing_rules = {
        local_name(child): child
        for child in field
        if local_name(child) in {"REQUIRED", "READONLY"}
    }

    current_required = "REQUIRED" in existing_rules
    current_read_only = "READONLY" in existing_rules

    final_required = current_required if is_required is None else is_required
    final_read_only = current_read_only if is_read_only is None else is_read_only

    if final_required and final_read_only:
        raise ValueError("Required ve Read Only aynı anda aktif olamaz.")

    namespace = field.tag.rsplit("}", 1)[0] + "}" if "}" in field.tag else ""

    for rule_name, requested_value in (
        ("REQUIRED", is_required),
        ("READONLY", is_read_only),
    ):
        if requested_value is None:
            continue

        existing = existing_rules.get(rule_name)

        if requested_value and existing is None:
            ET.SubElement(field, f"{namespace}{rule_name}")

        elif not requested_value and existing is not None:
            field.remove(existing)
    if help_text is not None:
        help_elements = [child for child in field if local_name(child) == "HELPTEXT"]

        if len(help_elements) > 1:
            raise ValueError("Birden fazla HELPTEXT bulundu.")

        existing_help = help_elements[0] if help_elements else None

        if help_text.strip():
            if existing_help is None:
                existing_help = ET.SubElement(
                    field,
                    f"{namespace}HELPTEXT",
                )

            existing_help.text = help_text.strip()

        elif existing_help is not None:
            field.remove(existing_help)


def update_field_in_xml(
    xml_path: str,
    field_ref: str,
    new_field_name: str | None,
    output_path: str,
    is_required: bool | None = None,
    is_read_only: bool | None = None,
    show_on_form: bool | None = None,
    help_text: str | None = None,
):
    if not field_ref.strip():
        raise ValueError("Field reference name cannot be empty.")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    def local_name(element):
        return element.tag.split("}")[-1]

    work_item_type = next(
        (element for element in root.iter() if local_name(element) == "WORKITEMTYPE"),
        None,
    )

    if work_item_type is None:
        raise ValueError("WORKITEMTYPE bulunamadı.")

    fields = next(
        (child for child in work_item_type if local_name(child) == "FIELDS"),
        None,
    )

    if fields is None:
        raise ValueError("Ana FIELDS bölümü bulunamadı.")

    matching_fields = [
        child
        for child in fields
        if local_name(child) == "FIELD" and child.get("refname") == field_ref
    ]

    if not matching_fields:
        raise ValueError(f"Field '{field_ref}' was not found in XML.")

    if len(matching_fields) > 1:
        raise ValueError(f"Multiple FIELD definitions found for '{field_ref}'.")

    field = matching_fields[0]
    old_name = field.get("name")

    if new_field_name is not None and new_field_name.strip():
        new_field_name = new_field_name.strip()

        if new_field_name != old_name:
            field.set("name", new_field_name)

            for control in root.iter():
                if (
                    local_name(control) == "Control"
                    and control.get("FieldName") == field_ref
                    and control.get("Label") is not None
                ):
                    control.set("Label", new_field_name)

    update_field_rules(
        field,
        is_required=is_required,
        is_read_only=is_read_only,
        help_text=help_text,
    )

    visibility_result = update_field_form_visibility(
        root,
        field_ref,
        field.get("name"),
        show_on_form,
    )

    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return {
        "success": True,
        "field_ref": field_ref,
        "old_name": old_name,
        "new_name": field.get("name"),
        "output_path": output_path,
        "form_visibility": visibility_result,
    }


def remove_field_from_xml(xml_path: str, field_ref: str, output_path: str):
    if not field_ref or not field_ref.strip():
        raise ValueError("Field reference name boş olamaz.")

    if Path(xml_path).resolve() == Path(output_path).resolve():
        raise ValueError("Orijinal XML dosyasının üzerine yazılamaz.")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    fields_element = find_fields_element(root)

    if fields_element is None:
        raise ValueError("XML içinde FIELDS bölümü bulunamadı.")

    target_field = next(
        (
            field
            for field in fields_element
            if local_tag(field) == "FIELD" and field.get("refname") == field_ref
        ),
        None,
    )

    if target_field is None:
        raise ValueError(f"Alan bulunamadı: {field_ref}")

    # Önce diğer XML öğelerindeki bağımlılıkları kontrol et.
    # FORM kontrolleri Remove sırasında kaldırılabilir.
    dependencies = []

    for element in root.iter():
        if element is target_field:
            continue

        tag = local_tag(element)

        if tag == "Control" and element.get("FieldName") == field_ref:
            continue

        for attribute_name, attribute_value in element.attrib.items():
            if field_ref in attribute_value:
                dependencies.append(
                    {
                        "element": tag,
                        "attribute": attribute_name,
                        "value": attribute_value,
                    }
                )

        if element.text and field_ref in element.text:
            dependencies.append(
                {
                    "element": tag,
                    "location": "text",
                }
            )

    if dependencies:
        return {
            "success": False,
            "action": "REMOVE_FIELD",
            "field_ref": field_ref,
            "message": "Alan başka XML öğelerinde kullanılıyor. Silme engellendi.",
            "dependencies": dependencies,
        }

    # FORM altındaki Layout / WebLayout kontrollerini kaldır.
    removed_controls = remove_field_controls(root, field_ref)

    # FIELD tanımını kaldır.
    fields_element.remove(target_field)

    # Çıktıda referans kalmadığını kontrol et.
    remaining_references = []

    for element in root.iter():
        for attribute_name, value in element.attrib.items():
            if field_ref in value:
                remaining_references.append(
                    {
                        "element": local_tag(element),
                        "attribute": attribute_name,
                    }
                )

        if element.text and field_ref in element.text:
            remaining_references.append(
                {
                    "element": local_tag(element),
                    "location": "text",
                }
            )

    if remaining_references:
        return {
            "success": False,
            "action": "REMOVE_FIELD",
            "field_ref": field_ref,
            "message": "Silme sonrası alan referansları kaldı.",
            "dependencies": remaining_references,
        }

    tree.write(
        output_path,
        encoding="utf-8",
        xml_declaration=True,
    )

    return {
        "success": True,
        "action": "REMOVE_FIELD",
        "field_ref": field_ref,
        "removed_controls": removed_controls,
        "output_path": output_path,
        "message": "Alan ve form kontrolleri XML'den kaldırıldı.",
    }


def validate_remove_field_change(
    original_xml: bytes,
    modified_xml: bytes,
    field_ref: str,
):
    import tempfile

    if not isinstance(field_ref, str) or not field_ref.strip():
        return {"success": False, "message": "Geçersiz field_ref."}

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "original.xml"
            expected_path = Path(temp_dir) / "expected.xml"

            original_path.write_bytes(original_xml)

            result = remove_field_from_xml(
                xml_path=str(original_path),
                field_ref=field_ref,
                output_path=str(expected_path),
            )

            if result.get("success") is not True:
                return result

            expected_root = ET.fromstring(expected_path.read_bytes())
            preview_root = ET.fromstring(modified_xml)

            def canonical(element):
                return ET.canonicalize(
                    ET.tostring(element, encoding="unicode"),
                    strip_text=True,
                )

            valid = canonical(expected_root) == canonical(preview_root)

            return {
                "success": valid,
                "message": (
                    "Remove XML doğrulaması başarılı."
                    if valid
                    else "Preview XML beklenen Remove değişikliğiyle eşleşmiyor."
                ),
            }

    except (ET.ParseError, OSError, ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
        }


def get_collection_url(collection_name: str, for_witadmin: bool = False):
    if not collection_name or not collection_name.strip():
        raise ValueError("Collection adı boş olamaz")

    if for_witadmin:
        base_url = os.getenv("AZURE_DEVOPS_WITADMIN_URL")
    else:
        base_url = os.getenv("AZURE_DEVOPS_SERVER_URL")

    if not base_url:
        raise RuntimeError("Azure DevOps sunucu adresi tanımlanmamış")

    return f"{base_url.rstrip('/')}/{collection_name}"


def get_server_field_info(session, collection_name: str, field_ref: str):
    if not field_ref or not field_ref.strip():
        raise ValueError("Field reference name boş olamaz.")

    witadmin = find_witadmin_path(session)
    collection_url = get_collection_url(
        collection_name,
        for_witadmin=True,
    )

    result = execute_command(
        witadmin,
        [
            "listfields",
            f"/collection:{collection_url}",
            f"/n:{field_ref}",
        ],
        session,
    )

    if not result["success"]:
        raise RuntimeError(f"Alan bilgileri okunamadı: {result.get('stderr', '')}")

    output = result["stdout"]
    name_matches = re.findall(
        r"(?m)^[ \t\u00a0]*Name:[ \t\u00a0]*(.+?)\s*$",
        output,
    )

    use_matches = re.findall(
        r"(?m)^[ \t\u00a0]*Use:[ \t\u00a0]*(.*?)\s*$",
        output,
    )

    if len(name_matches) != 1 or not use_matches:
        raise RuntimeError(
            "listfields çıktısındaki alan adı veya kullanım bilgisi doğrulanamadı."
        )

    name = name_matches[0].strip()
    uses = [item.strip() for item in use_matches]

    if not name or any(not item for item in uses):
        raise RuntimeError("Alan adı veya kullanım bilgisi boş.")

    return {
        "field_ref": field_ref,
        "name": name,
        "uses": uses,
    }


def change_field_name(
    session,
    collection_name: str,
    field_ref: str,
    new_name: str,
):
    if not field_ref or not field_ref.strip():
        raise ValueError("Field reference name boş olamaz.")

    if not new_name or not new_name.strip():
        raise ValueError("Yeni alan adı boş olamaz.")

    # Şimdilik yalnızca test alanlarımızda izin veriyoruz.
    if not field_ref.startswith("Lab."):
        raise ValueError("Alan adı değiştirme yalnızca Lab. alanlarında destekleniyor.")

    witadmin = find_witadmin_path(session)

    collection_url = get_collection_url(
        collection_name,
        for_witadmin=True,
    )

    ps_script = f"""
$ErrorActionPreference = 'Stop'
$witadmin = '{witadmin.replace("'", "''")}'
$collection = '{collection_url.replace("'", "''")}'
$field = '{field_ref.replace("'", "''")}'
$newName = '{new_name.replace("'", "''")}'

& $witadmin changefield "/collection:$collection" "/n:$field" "/name:$newName" /noprompt

if ($LASTEXITCODE -ne 0) {{
    exit 1
}}
"""

    result = session.run_ps(ps_script)

    stdout = result.std_out.decode(errors="replace").strip()
    stderr = result.std_err.decode(errors="replace").strip()

    if result.status_code != 0 or "TF212000" in stderr:
        raise RuntimeError("Alan adı değiştirilemedi: " + (stderr or stdout))

    return {
        "success": True,
        "field_ref": field_ref,
        "new_name": new_name,
        "message": "changefield komutu başarılı.",
    }


def find_witadmin_path(session):
    script = r"""
    $ErrorActionPreference = 'Stop'

    $command = Get-Command witadmin.exe -ErrorAction SilentlyContinue

    if ($command) {
        $command.Source
        exit 0
    }

    $roots = @(
        "${env:ProgramFiles}\Microsoft Visual Studio",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio"
    )

    foreach ($root in $roots) {
        if (Test-Path -LiteralPath $root) {
            $file = Get-ChildItem -LiteralPath $root `
                -Filter witadmin.exe `
                -Recurse -File `
                -ErrorAction SilentlyContinue |
                Select-Object -First 1

            if ($file) {
                $file.FullName
                exit 0
            }
        }
    }

    throw "witadmin.exe bulunamadi."
    """

    result = session.run_ps(script)

    if result.status_code != 0:
        error = result.std_err.decode("utf-8", errors="replace")
        raise RuntimeError(f"witadmin bulunamadı: {error}")

    path = result.std_out.decode("utf-8-sig").strip()

    if not path:
        raise RuntimeError("witadmin yolu boş döndü")

    return path


def export_global_list(session, collection_name: str) -> bytes:
    if not collection_name or not collection_name.strip():
        raise ValueError("Collection adı boş olamaz")

    if not all(char.isalnum() or char in "._-" for char in collection_name):
        raise ValueError("Geçersiz collection adı")

    remote_path = rf"C:\Windows\Temp\globallists-{uuid4().hex}.xml"

    collection_url = get_collection_url(collection_name, for_witadmin=True)
    witadmin_exe = find_witadmin_path(session)

    ps_script = f"""
    $ErrorActionPreference = 'Stop'

    $witadmin = '{witadmin_exe.replace("'", "''")}'
    $file = '{remote_path}'
    $collection = '{collection_url}'

    try {{
     $output = & $witadmin exportgloballist `
        /collection:$collection `
        /f:$file 2>&1

    if ($LASTEXITCODE -ne 0) {{
        throw ($output | Out-String)
    }}

    if (-not (Test-Path -LiteralPath $file)) {{
        throw "GlobalList XML dosyasi olusturulamadi."
    }}

    $bytes = [System.IO.File]::ReadAllBytes($file)
    [Convert]::ToBase64String($bytes)
}}
    finally {{
    Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
}}
"""

    result = session.run_ps(ps_script)

    if result.status_code != 0:
        error_message = result.std_err.decode("utf-8", errors="replace")
        raise RuntimeError(f"GlobalList export başarısız: {error_message}")

    output = result.std_out.decode("utf-8", errors="replace").strip()

    if not output:
        raise RuntimeError("GlobalList export boş çıktı döndürdü")

    try:
        xml_bytes = base64.b64decode(output, validate=True)
    except Exception as exc:
        raise RuntimeError("GlobalList export çıktısı geçerli Base64 değil") from exc

    try:
        ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise RuntimeError("GlobalList export geçerli XML üretmedi") from exc

    return xml_bytes


GLOBAL_LIST_NS = (
    "http://schemas.microsoft.com/VisualStudio/" "2005/workitemtracking/globallists"
)

ET.register_namespace("gl", GLOBAL_LIST_NS)


def find_global_list(root, list_name):
    for element in root:
        if local_tag(element) == "GLOBALLIST":
            if element.get("name") == list_name:
                return element
    return None


def add_global_list_item(xml_path, list_name, item_value, output_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if local_tag(root) != "GLOBALLISTS":
        raise ValueError("Geçersiz GlobalList XML")

    if not list_name.strip() or not item_value.strip():
        raise ValueError("Liste adı ve değer boş olamaz")

    if Path(xml_path).resolve() == Path(output_path).resolve():
        raise ValueError("Orijinal XML üzerine yazılamaz")

    global_list = find_global_list(root, list_name)

    if global_list is None:
        global_list = ET.SubElement(root, "GLOBALLIST", {"name": list_name})

    for item in global_list:
        if item.get("value") == item_value:
            raise ValueError("Bu değer zaten listede var")

    ET.SubElement(global_list, "LISTITEM", {"value": item_value})

    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    return {
        "success": True,
        "action": "ADD_GLOBAL_LIST_ITEM",
        "list_name": list_name,
        "item_value": item_value,
    }


def update_global_list_item(xml_path, list_name, old_value, new_value, output_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if Path(xml_path).resolve() == Path(output_path).resolve():
        raise ValueError("Orijinal XML üzerine yazılamaz")

    if not new_value.strip():
        raise ValueError("Yeni değer boş olamaz")

    global_list = find_global_list(root, list_name)

    if global_list is None:
        raise ValueError("GlobalList bulunamadı")

    target_item = None

    for item in global_list:
        if item.get("value") == new_value and old_value != new_value:
            raise ValueError("Yeni değer zaten mevcut")

        if item.get("value") == old_value:
            target_item = item

    if target_item is None:
        raise ValueError("Güncellenecek değer bulunamadı")

    target_item.set("value", new_value)

    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    return {
        "success": True,
        "action": "UPDATE_GLOBAL_LIST_ITEM",
        "old_value": old_value,
        "new_value": new_value,
    }


def remove_global_list_item(xml_path, list_name, item_value, output_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if Path(xml_path).resolve() == Path(output_path).resolve():
        raise ValueError("Orijinal XML üzerine yazılamaz")

    global_list = find_global_list(root, list_name)

    if global_list is None:
        raise ValueError("GlobalList bulunamadı")

    target_item = None

    for item in global_list:
        if item.get("value") == item_value:
            target_item = item
            break

    if target_item is None:
        raise ValueError("Silinecek değer bulunamadı")

    if len(global_list) == 1:
        raise ValueError(
            "GlobalList içindeki son değer silinemez. "
            "Azure DevOps en az bir LISTITEM gerektiriyor."
        )

    global_list.remove(target_item)

    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return {
        "success": True,
        "action": "REMOVE_GLOBAL_LIST_ITEM",
        "list_name": list_name,
        "item_value": item_value,
        "output_path": output_path,
    }


def save_global_list_backup(xml_bytes: bytes, collection_name: str):
    if not xml_bytes:
        raise ValueError("Yedeklenecek XML boş olamaz")

    # Dosya adında güvenli karakterler kullan
    if not collection_name or not all(
        char.isascii() and (char.isalnum() or char in "._-") for char in collection_name
    ):
        raise ValueError("Geçersiz collection adı")

    # Sunucuya değil, backend'in çalıştığı bilgisayara kaydedilir
    backup_dir = Path("backups") / "global-lists"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_id = uuid4().hex

    backup_path = backup_dir / (f"{collection_name}-{timestamp}-{backup_id}.xml")

    # x modu: Aynı isimli dosya varsa üzerine yazma
    with backup_path.open("xb") as file:
        file.write(xml_bytes)

    return {
        "success": True,
        "backup_id": backup_id,
        "backup_path": str(backup_path),
        "collection_name": collection_name,
        "size_bytes": len(xml_bytes),
    }


def save_global_list_preview(
    original_xml: bytes, preview_xml: bytes, collection_name: str, operation: str
):
    if operation not in {"add", "update", "remove"}:
        raise ValueError("Geçersiz GlobalList işlemi")

    if not collection_name or not all(
        c.isascii() and (c.isalnum() or c in "._-") for c in collection_name
    ):
        raise ValueError("Geçersiz collection adı")

    ET.fromstring(original_xml)
    ET.fromstring(preview_xml)

    preview_id = uuid4().hex

    preview_dir = Path("previews") / "global-lists" / preview_id
    preview_dir.mkdir(parents=True, exist_ok=False)

    original_hash = hashlib.sha256(original_xml).hexdigest()

    (preview_dir / "original.xml").write_bytes(original_xml)
    (preview_dir / "preview.xml").write_bytes(preview_xml)

    metadata = {
        "preview_id": preview_id,
        "collection_name": collection_name,
        "operation": operation,
        "original_sha256": original_hash,
        "preview_sha256": hashlib.sha256(preview_xml).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (preview_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    return metadata


def import_global_list(session, collection_name: str, xml_bytes: bytes):
    """
    GlobalList XML'ini Azure DevOps Server'a import eder.
    XML, WinRM üzerinden küçük parçalar halinde aktarılır.
    """

    if not xml_bytes:
        raise ValueError("Import edilecek XML boş")

    root = ET.fromstring(xml_bytes)

    if root.tag.split("}")[-1] != "GLOBALLISTS":
        raise ValueError("Geçersiz GlobalList XML'i")

    collection_url = get_collection_url(collection_name, for_witadmin=True)
    witadmin_exe = find_witadmin_path(session)

    remote_path = rf"C:\Windows\Temp\globallists-{uuid4().hex}.xml"

    def run_checked(script, step="unknown"):
        result = session.run_ps(script)

        stdout = result.std_out.decode("utf-8-sig", errors="replace")
        stderr = result.std_err.decode("utf-8-sig", errors="replace")

        if result.status_code != 0:
            raise RuntimeError(
                f"GlobalList işlemi başarısız [{step}]: " f"{stderr or stdout}"
            )

        return stdout

    ps_path = remote_path.replace("'", "''")
    ps_url = collection_url.replace("'", "''")
    ps_exe = witadmin_exe.replace("'", "''")

    try:
        # 1. Sunucuda geçici dosya oluştur
        run_checked(f"[System.IO.File]::WriteAllBytes('{ps_path}', [byte[]]@())")

        # 2. XML'i küçük parçalar halinde aktar
        chunk_size = 512

        for offset in range(0, len(xml_bytes), chunk_size):
            chunk = xml_bytes[offset : offset + chunk_size]
            encoded = base64.b64encode(chunk).decode("ascii")

            script = f"""
            $bytes = [Convert]::FromBase64String('{encoded}')
            $stream = [System.IO.File]::Open(
                '{ps_path}',
                [System.IO.FileMode]::Append,
                [System.IO.FileAccess]::Write
            )
            try {{
                $stream.Write($bytes, 0, $bytes.Length)
            }}
            finally {{
                $stream.Dispose()
            }}
            """

            run_checked(script, step=f"XML aktarımı offset={offset}")

        # 3. Dosyanın doğru aktarıldığını kontrol et
        expected_hash = hashlib.sha256(xml_bytes).hexdigest()

        verify_script = f"""
        $hash = (Get-FileHash -LiteralPath '{ps_path}' -Algorithm SHA256).Hash
        Write-Output $hash
        """

        actual_hash = run_checked(verify_script).strip().lower()

        if actual_hash != expected_hash:
            raise RuntimeError(
                "GlobalList XML aktarımı doğrulanamadı: SHA256 uyuşmuyor."
            )

        # 4. GlobalList import
        import_script = f"""
        $ErrorActionPreference = 'Stop'

        $output = & '{ps_exe}' importgloballist `
            '/collection:{ps_url}' `
            '/f:{ps_path}' 2>&1

        if ($LASTEXITCODE -ne 0) {{
            throw "GlobalList import failed: $output"
        }}

        Write-Output "IMPORT_SUCCESS"
        """

        stdout = run_checked(import_script)

        if "IMPORT_SUCCESS" not in stdout:
            raise RuntimeError(f"GlobalList import doğrulanamadı: {stdout}")

        return {
            "success": True,
            "collection_name": collection_name,
            "message": "GlobalList import komutu başarıyla tamamlandı.",
        }

    finally:
        # 5. Geçici dosyayı temizle
        cleanup_script = f"""
        if (Test-Path -LiteralPath '{ps_path}') {{
            Remove-Item -LiteralPath '{ps_path}' -Force
        }}
        """

        try:
            run_checked(cleanup_script)
        except Exception:
            pass


def import_work_item_type(
    session,
    collection_name: str,
    project_name: str,
    xml_bytes: bytes,
    dry_run: bool = False,
):
    if not xml_bytes:
        raise ValueError("Import edilecek XML boş olamaz")

    root = ET.fromstring(xml_bytes)

    if local_tag(root) != "WITD":
        raise ValueError("Geçersiz Work Item Type XML")
    collection_url = get_collection_url(collection_name, for_witadmin=True)

    witadmin_exe = None

    if not dry_run:
        witadmin_exe = find_witadmin_path(session)

    remote_path = rf"C:\Windows\Temp\wit-{uuid4().hex}.xml"

    xml_base64 = base64.b64encode(xml_bytes).decode("ascii")
    chunk_size = 512

    chunks = [
        xml_base64[i : i + chunk_size] for i in range(0, len(xml_base64), chunk_size)
    ]

    try:
        init_script = f"""
        $ErrorActionPreference = 'Stop'
        [System.IO.File]::WriteAllBytes(
            '{remote_path}',
            [byte[]]@()
        )
        """

        init_result = session.run_ps(init_script)

        if init_result.status_code != 0:
            raise RuntimeError(init_result.std_err.decode(errors="replace"))

        # 2. XML'i küçük parçalar hâlinde gönder.
        for index, chunk in enumerate(chunks, start=1):
            upload_script = f"""
            $ErrorActionPreference = 'Stop'
            $bytes = [Convert]::FromBase64String('{chunk}')

            $stream = [System.IO.File]::Open(
                '{remote_path}',
                [System.IO.FileMode]::Append,
                [System.IO.FileAccess]::Write
            )

            try {{
                $stream.Write($bytes, 0, $bytes.Length)
            }}
            finally {{
                $stream.Dispose()
            }}
            """

            upload_result = session.run_ps(upload_script)

            if upload_result.status_code != 0:
                error = upload_result.std_err.decode(errors="replace")
                raise RuntimeError(
                    f"XML aktarımı {index}/{len(chunks)} parçasında başarısız: {error}"
                )

        # 3. Sunucudaki dosyanın bütünlüğünü doğrula.
        verify_script = f"""
        $ErrorActionPreference = 'Stop'
        $hash = (Get-FileHash -LiteralPath '{remote_path}' -Algorithm SHA256).Hash
        Write-Output $hash
        """

        verify_result = session.run_ps(verify_script)

        if verify_result.status_code != 0:
            raise RuntimeError("Sunucudaki XML dosyasının hash değeri okunamadı.")

        remote_hash = verify_result.std_out.decode(errors="replace").strip().lower()
        local_hash = hashlib.sha256(xml_bytes).hexdigest()

        if remote_hash != local_hash:
            raise RuntimeError("XML aktarımında bütünlük hatası: SHA256 uyuşmuyor.")
        if dry_run:
            return {
                "success": True,
                "message": "XML Windows'a aktarıldı ve SHA256 doğrulandı. Import yapılmadı.",
                "sha256": local_hash,
                "chunk_count": len(chunks),
            }
        # 4. XML'i Azure DevOps Server'a import et.
        result = execute_command(
            witadmin_exe,
            [
                "importwitd",
                f"/collection:{collection_url}",
                f"/p:{project_name}",
                f"/f:{remote_path}",
            ],
            session,
        )
        logger.info(
            "witadmin importwitd sonucu: status=%s stdout=%r stderr=%r",
            result.get("status_code"),
            result.get("stdout"),
            result.get("stderr"),
        )

        if not result["success"]:
            raise RuntimeError(
                "Work Item Type import başarısız: "
                f"{result.get('stderr') or result.get('error')}"
            )

        return {
            "success": True,
            "message": "Work Item Type import komutu başarılı.",
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }

    finally:
        cleanup_script = f"""
        Remove-Item -LiteralPath '{remote_path}' -Force -ErrorAction SilentlyContinue
        """

        try:
            session.run_ps(cleanup_script)
        except Exception:
            logging.getLogger(__name__).exception(
                "Geçici WIT XML dosyası temizlenemedi"
            )


def validate_field_name_update(
    original_xml: bytes,
    preview_xml: bytes,
):
    original_root = ET.fromstring(original_xml)
    preview_root = ET.fromstring(preview_xml)

    def field_names(root):
        return {
            field.get("refname"): field.get("name")
            for field in root.iter()
            if local_tag(field) == "FIELD"
        }

    original_fields = field_names(original_root)
    preview_fields = field_names(preview_root)

    if original_fields.keys() != preview_fields.keys():
        raise ValueError("Update işleminde field eklenemez veya silinemez.")

    changed_fields = [
        ref for ref in original_fields if original_fields[ref] != preview_fields[ref]
    ]

    if len(changed_fields) != 1:
        raise ValueError("Update işleminde yalnızca bir field adı değişmelidir.")

    return {
        "success": True,
        "field_ref": changed_fields[0],
        "old_name": original_fields[changed_fields[0]],
        "new_name": preview_fields[changed_fields[0]],
    }


def save_wit_preview(
    original_xml: bytes,
    preview_xml: bytes,
    collection_name: str,
    project_name: str,
    work_item_type: str,
    operation: str,
    field_ref: str,
    update_options: dict | None = None,
):
    if operation not in {"add", "remove", "update", "manual_edit"}:
        raise ValueError("Geçersiz işlem")

    if operation != "manual_edit":
        if not field_ref or not field_ref.strip():
            raise ValueError("Field reference name zorunlu")

    if not all([collection_name, project_name, work_item_type]):
        raise ValueError("Collection, project ve Work Item Type zorunlu")

    original_root = ET.fromstring(original_xml)
    preview_root = ET.fromstring(preview_xml)

    if local_tag(original_root) != "WITD":
        raise ValueError("Orijinal XML geçersiz")

    if local_tag(preview_root) != "WITD":
        raise ValueError("Preview XML geçersiz")

    if original_xml == preview_xml:
        raise ValueError("XML'de değişiklik yok")
    preview_id = uuid4().hex
    preview_dir = Path("previews") / "work-item-types" / preview_id

    if operation == "update":
        if update_options is None:
            raise ValueError("Update options are required.")

        expected_keys = {
            "field_name",
            "is_required",
            "is_read_only",
            "show_on_form",
            "help_text",
        }

        if not isinstance(update_options, dict) or set(update_options) != expected_keys:
            raise ValueError("Invalid Update options.")

        for key in ("is_required", "is_read_only", "show_on_form"):
            value = update_options[key]
            if value is not None and type(value) is not bool:
                raise ValueError(f"Invalid {key} value.")

        for key in ("field_name", "help_text"):
            value = update_options[key]
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Invalid {key} value.")

    preview_dir.mkdir(parents=True, exist_ok=False)

    (preview_dir / "original.xml").write_bytes(original_xml)
    (preview_dir / "preview.xml").write_bytes(preview_xml)

    metadata = {
        "preview_id": preview_id,
        "collection_name": collection_name,
        "project_name": project_name,
        "work_item_type": work_item_type,
        "operation": operation,
        "original_sha256": hashlib.sha256(original_xml).hexdigest(),
        "preview_sha256": hashlib.sha256(preview_xml).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "field_ref": field_ref,
    }

    if operation == "update":
        metadata["update_options"] = update_options

    (preview_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    return metadata


def save_wit_backup(
    xml_bytes: bytes,
    collection_name: str,
    project_name: str,
    work_item_type: str,
    field_name_change: dict | None = None,
):
    root = ET.fromstring(xml_bytes)

    if local_tag(root) != "WITD":
        raise ValueError("Geçersiz Work Item Type XML")

    backup_id = uuid4().hex
    backup_dir = Path("backups") / "work-item-types" / backup_id
    backup_dir.mkdir(parents=True, exist_ok=False)

    backup_path = backup_dir / "original.xml"
    backup_path.write_bytes(xml_bytes)
    saved_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    original_hash = hashlib.sha256(xml_bytes).hexdigest()

    if saved_hash != original_hash:
        raise RuntimeError("Backup doğrulaması başarısız: SHA256 uyuşmuyor.")
    metadata = {
        "backup_id": backup_id,
        "collection_name": collection_name,
        "project_name": project_name,
        "work_item_type": work_item_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "sha256": original_hash,
    }
    if field_name_change is not None:
        required_keys = {"field_ref", "old_name", "new_name"}

        if not isinstance(field_name_change, dict) or not required_keys.issubset(
            field_name_change
        ):
            raise ValueError("Alan adı değişikliği bilgileri eksik.")

        if not all(
            isinstance(field_name_change[key], str) and field_name_change[key].strip()
            for key in required_keys
        ):
            raise ValueError("Alan adı değişikliği bilgileri geçersiz.")

        metadata["field_name_change"] = {
            key: field_name_change[key] for key in ("field_ref", "old_name", "new_name")
        }

    (backup_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    return {"backup_id": backup_id, "backup_path": str(backup_path)}


def get_protected_apply_backup_ids():
    protected_ids = set()

    preview_root = Path("previews") / "work-item-types"

    if not preview_root.is_dir():
        return protected_ids

    for preview_dir in preview_root.iterdir():
        if not preview_dir.is_dir() or preview_dir.is_symlink():
            continue

        applied_path = preview_dir / "applied.json"

        if not applied_path.exists():
            continue

        try:
            applied_data = json.loads(applied_path.read_text(encoding="utf-8"))

            if not isinstance(applied_data, dict):
                raise ValueError("applied.json nesne formatında değil.")

            backup_id = applied_data.get("backup_id")
            status = applied_data.get("status")

            if not isinstance(backup_id, str) or not re.fullmatch(
                r"[0-9a-f]{32}", backup_id
            ):
                raise ValueError("Geçersiz veya eksik backup_id.")

            if status != "verified":
                protected_ids.add(backup_id)

        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Backup cleanup durduruldu. "
                f"applied.json okunamadı veya geçersiz: {applied_path}"
            ) from exc

    return protected_ids


def cleanup_old_wit_backups(
    collection_name: str,
    project_name: str,
    work_item_type: str,
    keep: int = 3,
    dry_run: bool = True,
):
    if keep < 1:
        raise ValueError("En az bir backup saklanmalı.")

    backup_root = Path("backups") / "work-item-types"

    if not backup_root.is_dir():
        return {
            "success": True,
            "dry_run": dry_run,
            "deleted": [],
            "would_delete": [],
            "kept": [],
            "protected": [],
        }

    eligible_backups = []
    protected_backups = []
    protected_apply_ids = get_protected_apply_backup_ids()
    for backup_dir in backup_root.iterdir():

        if not backup_dir.is_dir() or backup_dir.is_symlink():
            continue

        metadata_path = backup_dir / "metadata.json"
        original_path = backup_dir / "original.xml"

        if not metadata_path.is_file() or not original_path.is_file():
            continue

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

            if not isinstance(metadata, dict):
                continue

            if (
                metadata.get("collection_name") != collection_name
                or metadata.get("project_name") != project_name
                or metadata.get("work_item_type") != work_item_type
            ):
                continue

            if metadata.get("backup_id") != backup_dir.name:
                continue
            if backup_dir.name in protected_apply_ids:
                protected_backups.append(backup_dir.name)
                continue
            original_bytes = original_path.read_bytes()

            if hashlib.sha256(original_bytes).hexdigest() != metadata.get("sha256"):
                continue

            created_at = metadata.get("created_at")

            if not isinstance(created_at, str):
                protected_backups.append(backup_dir.name)
                continue

            created_time = datetime.fromisoformat(created_at)

            if created_time.tzinfo is None:
                protected_backups.append(backup_dir.name)
                continue

            created_time = created_time.astimezone(timezone.utc)

            if metadata.get("status") != "verified":
                protected_backups.append(backup_dir.name)
                continue

            eligible_backups.append((created_time, backup_dir))

        except (OSError, ValueError, TypeError):
            continue

    eligible_backups.sort(
        key=lambda item: (item[0], item[1].name),
        reverse=True,
    )

    deleted = []
    would_delete = []

    for _, backup_dir in eligible_backups[keep:]:
        if dry_run:
            would_delete.append(backup_dir.name)
        else:
            shutil.rmtree(backup_dir)
            deleted.append(backup_dir.name)

    return {
        "success": True,
        "dry_run": dry_run,
        "deleted": deleted,
        "would_delete": would_delete,
        "kept": [backup_dir.name for _, backup_dir in eligible_backups[:keep]],
        "protected": protected_backups,
    }
