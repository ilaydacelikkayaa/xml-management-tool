import requests
import os
import xml.etree.ElementTree as ET
import shutil
from dotenv import load_dotenv
import winrm
import getpass
import base64
import logging
import time
from dateutil.relativedelta import relativedelta
from datetime import date
from uuid import uuid4
import json
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

windows_ip = "192.168.64.2"
username = r"WIN-9B0E3EPO4LV\Administrator"
wiql_url = "http://win-9b0e3epo4lv/XMLLabCollection/_apis/wit/wiql?api-version=7.0"


load_dotenv()
server_url = os.getenv("AZURE_DEVOPS_SERVER_URL")
token = os.getenv("AZURE_DEVOPS_PAT")


#A

def get_work_item_ids(project_name: str, work_item_type: str,start_date: date | None = None):

    safe_project_name = escape_wiql_value(project_name)
    safe_work_item_type = escape_wiql_value(work_item_type)

    wiql_body = {
        "query": (
            "Select [System.Id] From WorkItems "
            f"WHERE [System.WorkItemType] = '{safe_work_item_type}' "
            f"AND [System.TeamProject] = '{safe_project_name}' "
            f" AND [System.CreatedDate] >= '{start_date}'"
        )
    }
    logger.info("WIQL query: %s", wiql_body["query"])

    start = time.perf_counter()

    try:
        request = requests.post(
            auth=("", token),
            url=wiql_url,
            json=wiql_body,
            timeout=15
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

def get_work_items(ids: list):
    
    if not ids:
        return []
    
    id_strings = []
    for i in ids:
        id_strings.append(str(i))

    ids_csv = ",".join(id_strings)

    second_url = (
        f"http://win-9b0e3epo4lv/XMLLabCollection/"
        f"_apis/wit/workitems?ids={ids_csv}&api-version=7.0"
    )

    request = requests.get(
        auth=("", token),
        url=second_url,
        timeout=15
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
    if total==0:
       return {
    "field_ref": field_ref,
    "total": 0,
    "filled": 0,
    "empty": 0,
    "rate": 0
}
    empty = total - filled
    rate = (filled / total) * 100

    return {
        "field_ref": field_ref,
        "total": total,
        "filled": filled,
        "empty": empty,
        "rate": rate
    }

def analyze_field(work_item_type: str, field_ref: str,project_name:str,start_date: date | None = None
):
    
    if start_date is None:
        start_date = date.today() - relativedelta(months=6)

    ids = get_work_item_ids(project_name,work_item_type,start_date)

    work_items = get_work_items(ids)

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
        "control_count": control_count
    }

def analyze_field_full(work_item_type: str, field_ref: str, xml_path: str,project_name:str):
    usage = analyze_field(work_item_type, field_ref,project_name)

    xml_info = find_field_references(
        xml_path,
        field_ref
    )

    return {
        "usage": usage,
        "xml_info": xml_info
    }

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
        "candidate": candidate
    }

def create_backup(xml_path: str, backup_path: str):
    try:
        if os.path.exists(backup_path):
            return {
                "success": False,
                "message": "Backup file already exists"
            }
        shutil.copy2(xml_path, backup_path)

        return {
            "success": True,
            "backup_path": backup_path
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
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
            return{
                "success": False,
                "message": "Field does not exist in XML"
            }
    
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
        "output_path":None
        }

    tree.write(
        output_path,
        encoding="utf-8",
        xml_declaration=True
    )

    return {
        "success": True,
        "field_ref": field_ref,
        "removed_controls": removed_count,
        "output_path": output_path
    }

def validate_xml(xml_path: str):
    try:
        ET.parse(xml_path)

        return {
            "valid": True
        }

    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }

def build_change_preview(
    before_analysis: dict,
    after_analysis: dict,
    validation_result: dict,
    azure_validation:bool
):
    before_controls = before_analysis["xml_info"]["control_count"]
    after_controls = after_analysis["control_count"]

    field_preserved = after_analysis["field_name"] is not None
    xml_valid=validation_result["valid"]

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
        "ready_to_apply": ready_to_apply
    }


def can_apply_change(preview: dict, confirmed: bool):
    technical_ready = preview["ready_to_apply"]

    apply_allowed = (technical_ready and confirmed)

    return {
        "technical_ready": technical_ready,
        "confirmed": confirmed,
        "apply_allowed": apply_allowed
    }


def prepare_apply(confirmation_result:dict,preview_xml_path:str):
      apply_allowed = confirmation_result["apply_allowed"]
      if apply_allowed == False :
          return {
              "success": False,
              "message": "Apply is not allowed"
          }
      else:
          return{
               "success": True,
               "status": "READY_FOR_IMPORT",
               "xml_path": preview_xml_path
          }

def build_import_command(prepare_result:dict,collection_url:str,project:str,windows_path:str):
    result=prepare_result["success"]
    if result == False:
         return{
             "error": "is not true"
         }
    else:
        command = f"witadmin importwitd /collection:{collection_url} /p:{project} /f:{windows_path}"
        return{
            "success": True,
            "command": command
        }

def build_export_command(witadmin:str,collection_url: str, project: str, work_item_type: str, output_path: str):
    if not witadmin or not collection_url or not project or not work_item_type or not output_path:
         return {
            "success": False,
            "error": "Missing required parameter"
          }
    args = [
        "exportwitd",
        f"/collection:{collection_url}",
        f"/p:{project}",
        f"/n:{work_item_type}",
        f"/f:{output_path}"
    ]
    return{
    "success": True,
    "program": witadmin,
    "args":args
    }
def execute_command(program:str,args:list,session:winrm.Session):
    try:
        result=session.run_cmd(f'"{program}"',args)

        return{
            "success": result.status_code == 0,
            "status_code": result.status_code,
            "stdout": result.std_out.decode(errors="replace").strip(),
            "stderr": result.std_err.decode(errors="replace").strip()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
            "error_type": "REMOTE_EXECUTION_ERROR"
        }

witadmin_path = (
    r"C:\Program Files\Microsoft Visual Studio\18\TeamExplorer"
    r"\Common7\IDE\CommonExtensions\Microsoft"
    r"\TeamFoundation\Team Explorer\witadmin.exe"
)


def verify(verification_result: dict):
    field_name = verification_result["field_name"]
    control_count = verification_result["control_count"]
    if field_name != None and control_count==0:
        return{
        "verified":True
        }
    else:
       return {
    "verified": False
     }
    
def check_remote_file(session: winrm.Session, remote_path: str):
    script=f'Test-Path "{remote_path}"'
    result = session.run_ps(script)
    return result


def read_remote_xml(session: winrm.Session, remote_path: str):
    
    script=rf'''
    $bytes = [System.IO.File]::ReadAllBytes("{remote_path}")
    [Convert]::ToBase64String($bytes)'''
    result=session.run_ps(script)
    if result.status_code !=0 :
        raise RuntimeError("Uzak sunucudaki XML okunamadı")
    xml_bytes = base64.b64decode(result.std_out.strip(), validate=True)
    return xml_bytes

def is_xml_response_valid(response):
    if response.status_code != 0:
        return False

    if not response.std_out.strip():
        return False

    return True

def escape_wiql_value(value:str)->str:
    result=value.replace("'","''")
    return result

def list_xml_fields(xml_bytes:bytes):
    root = ET.fromstring(xml_bytes)
    fields=[]
    work_item_type = root.find("{*}WORKITEMTYPE")

    if work_item_type is None:
      raise ValueError("WORKITEMTYPE bölümü bulunamadı") 
    fields_section = work_item_type.find("{*}FIELDS")

    if fields_section is None:
      raise ValueError("FIELDS bölümü bulunamadı")
    for field in fields_section.findall("{*}FIELD"):
      name=field.get("name")
      refname=field.get("refname")
      field_type=field.get("type")
      if name is None or refname is None or field_type is None:
       raise ValueError(f"Eksik FIELD bilgisi: {field.attrib}")
      field_info={
        "name":name,
        "refname":refname,
        "field_type":field_type
    }
      fields.append(field_info)
    return fields

def ensure_remote_directory(session: winrm.Session, directory: str):
    script = r'''
    $path = "C:\Temp"

    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    '''

    result = session.run_ps(script)

    if result.status_code != 0:
        raise RuntimeError("Windows geçici klasörü oluşturulamadı")
    
def get_project_xml(
    session: winrm.Session,
    collection_name: str,
    project_name: str,
    work_item_type: str
):
    collection_url = f"{server_url.rstrip('/')}/{collection_name}"
    remote_xml_path = rf"C:\Temp\wit-{uuid4().hex}.xml"
    ensure_remote_directory(session,remote_xml_path)
    export_result = build_export_command(
        witadmin_path,
        collection_url,
        project_name,
        work_item_type,
        remote_xml_path
    )
    if not export_result["success"]:
      raise RuntimeError("Export komutu hazırlanamadı")

    try:
      execute_result = execute_command(
      export_result["program"],
      export_result["args"],
      session
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
        "cmd.exe",
        ["/c", "del", "/q", remote_xml_path]
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
        message_encryption="always"
    )
        return session

import os
import json
import winrm


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
        message_encryption="always"
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
    powershell_script = powershell_script.replace(
        "__SERVER_URL__",
        server_url_ps
    )

    result = session.run_ps(powershell_script)

    if result.status_code != 0:
        error_message = result.std_err.decode(
            "utf-8",
            errors="replace"
        )
        raise RuntimeError(error_message)

    output = result.std_out.decode(
        "utf-8-sig",
        errors="replace"
    ).strip()

    if not output:
        raise RuntimeError("Collection sorgusu boş çıktı döndürdü")

    return json.loads(output)

def get_project(collection_name:str):
        token = os.getenv("AZURE_DEVOPS_PAT")
        url = f"{server_url.rstrip('/')}/{collection_name}/_apis/projects?api-version=7.0"
        response=requests.get(
            url=url,
            auth=("", token),
            timeout=15
        )
        response.raise_for_status()
        return response.json()

def get_work_item_types(collection_name: str, project_name: str):
    token=os.getenv("AZURE_DEVOPS_PAT")
    if not token or not server_url:
     raise RuntimeError("Azure DevOps bağlantı bilgileri eksik")
    url = f"{server_url.rstrip('/')}/{collection_name}/{project_name}/_apis/wit/workitemtypes?api-version=7.0"
    response=requests.get(
        url=url,
        auth=("", token),
        timeout=15
    )

    response.raise_for_status()
    return response.json()

def preview_hide_field(
    session: winrm.Session,
    collection_name: str,
    project_name: str,
    work_item_type: str,
    field_ref: str
):
    xml_bytes = get_project_xml(
        session,
        collection_name,
        project_name,
        work_item_type
    )
    if not xml_bytes:
        raise RuntimeError("Azure DevOps'tan boş XML döndü")

    with tempfile.TemporaryDirectory() as temp_dir:

        original_path = Path(temp_dir) / "original.xml"
        backup_path = Path(temp_dir) / "backup.xml"
        preview_path = Path(temp_dir) / "preview.xml"

        with open(original_path, "wb") as f:
            f.write(xml_bytes)

        backup_result = create_backup(
            str(original_path),
            str(backup_path)
        )

        if not backup_result["success"]:
            raise RuntimeError("Backup oluşturulamadı")

        hide_result = hide_field_from_ui(
            str(original_path),
            field_ref,
            str(preview_path)
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
        "message": "Bu alan zaten gizli. Herhangi bir değişiklik yapılmadı."
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
            "message": "Preview oluşturuldu. Azure DevOps'a uygulanmadı."
        }
    
def main():
    project_name = "XMLManagementLab"
    work_item_type = "Issue"
    field_ref = "Lab.Environment"
    collection_url = "http://win-9b0e3epo4lv/XMLLabCollection"

    # Dosya yolları
    remote_xml_path = rf"C:\{work_item_type}-current.xml"
    local_xml_path = f"{work_item_type}-current.xml"
    backup_xml_path = f"{work_item_type}-backup-python.xml"
    preview_xml_path = f"{work_item_type}-preview.xml"

    # Windows Server bağlantısı
    password = getpass.getpass("Windows şifresi: ")

    session = winrm.Session(
        f"http://{windows_ip}:5985/wsman",
        auth=(username, password),
        transport="ntlm",
        message_encryption="always"
    )

    #  XML export
    export_result = build_export_command(
        witadmin_path,
        collection_url,
        project_name,
        work_item_type,
        remote_xml_path
    )

    if export_result["success"]:
        execute_result = execute_command(
            export_result["program"],
            export_result["args"],
            session
        )
    else:
        print("Export failed, transaction canceled")
        return

    if not execute_result["success"]:
        print("Export failed, transaction canceled")
        return

    print(execute_result)

    # Remote dosya kontrolü
    check_result = check_remote_file(
        session,
        remote_xml_path
    )

    print("Status:", check_result.status_code)
    print("Dosya var mı:", check_result.std_out.decode().strip())

    if (
        check_result.status_code != 0
        or check_result.std_out.decode().strip() != "True"
    ):
        print("The file is in an uncontrollable state.")
        return

    #  Windows'taki XML'i oku
    xml_bytes = read_remote_xml(session, remote_xml_path)

    with open(local_xml_path, "wb") as f:
      f.write(xml_bytes)

    #  Alan analizi
    analysis_result = analyze_field_full(
        work_item_type,
        field_ref,
        local_xml_path,
        project_name
    )
    print(analysis_result)

    cleanup_result = evaluate_cleanup_candidate(
        analysis_result
    )
    print(cleanup_result)

    field_report = build_field_report(
        analysis_result
    )
    print(field_report)

    #  Backup oluştur
    create_result = create_backup(
        local_xml_path,
        backup_xml_path
    )
    print(create_result)

    if not create_result["success"]:
        print("Backup başarısız! XML değişikliği durduruldu.")
        return

    #  Alanı UI'dan gizle
    hide_result = hide_field_from_ui(
        local_xml_path,
        field_ref,
        preview_xml_path
    )

    if hide_result.get("status") == "ALREADY_HIDDEN":
        print("This field is already hidden.")
        return

    print(hide_result)

    if not hide_result["success"]:
        print("Alan gizlenemedi. İşlem durduruldu.")
        return

    #  Değişikliği kontrol et
    verify_result = find_field_references(
        preview_xml_path,
        field_ref
    )
    print(verify_result)

    #  XML doğrulama
    validation_result = validate_xml(
        preview_xml_path
    )
    print(validation_result)

    #  Değişiklik önizlemesi
    preview = build_change_preview(
        analysis_result,
        verify_result,
        validation_result,
        azure_validation=False
    )

    print("Preview:", preview)
    print("Sunucuya import yapılmadı.")


if __name__ == "__main__":
    with open("Issue-current.xml", "rb") as f:
        xml_bytes = f.read()

    result = list_xml_fields(xml_bytes)
    print("Toplam alan:", len(result))
    print("İlk alan:", result[0])