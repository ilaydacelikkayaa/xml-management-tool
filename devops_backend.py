import requests
import os
import xml.etree.ElementTree as ET
import shutil
import subprocess
from dotenv import load_dotenv
import winrm
import getpass
import base64
windows_ip = "192.168.64.2"
username = r"WIN-9B0E3EPO4LV\Administrator"
wiql_url = "http://win-9b0e3epo4lv/XMLLabCollection/_apis/wit/wiql?api-version=7.0"

load_dotenv()
token = os.getenv("AZURE_DEVOPS_PAT")

#A

def get_work_item_ids(work_item_type: str):
    wiql_body = {
        "query": f"Select [System.Id] From WorkItems WHERE [System.WorkItemType] = '{work_item_type}'"
    }

    request = requests.post(
        auth=("", token),
        url=wiql_url,
        json=wiql_body
    )

    result = request.json()

    ids = []

    for i in result["workItems"]:
        ids.append(i["id"])

    return ids


def get_work_items(ids: list):
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
        url=second_url
    )

    result = request.json()

    return result["value"]



def analyze_work_items(work_items: list, field_ref: str):
    filled = 0

    for i in work_items:
        field_value = i["fields"].get(field_ref)

        if field_value is not None:
            filled += 1

    total = len(work_items)
    empty = total - filled
    rate = (filled / total) * 100

    return {
        "field_ref": field_ref,
        "total": total,
        "filled": filled,
        "empty": empty,
        "rate": rate
    }


def analyze_field(work_item_type: str, field_ref: str):
    ids = get_work_item_ids(work_item_type)

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


def analyze_field_full(work_item_type: str, field_ref: str, xml_path: str):
    usage = analyze_field(work_item_type, field_ref)

    xml_info = find_field_references(
        xml_path,
        field_ref
    )

    return {
        "usage": usage,
        "xml_info": xml_info
    }

#B

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

#C
def create_backup(xml_path: str, backup_path: str):
    try:
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



''' Temporary: witadmin validation was performed manually on Windows VM
azure_validation = True

preview = build_change_preview(
    analysis_result,
    verify_result,
    validation_result,
    azure_validation
)

print(preview)
'''

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
    return result

def is_xml_response_valid(response):
    if response.status_code != 0:
        return False

    if not response.std_out.strip():
        return False

    return True



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
    response = read_remote_xml(
        session,
        remote_xml_path
    )

    print("Status:", response.status_code)
    print("Hata:", response.std_err.decode())
    print("Gelen veri uzunluğu:", len(response.std_out))

    if is_xml_response_valid(response):
        try:
            xml_bytes = base64.b64decode(
                response.std_out.strip(),
                validate=True
            )
        except Exception as e:
            print("Base64 çözme hatası:", e)
            return
    else:
        print("XML could not be read.")
        return

    #  XML'i Mac'e kaydet
    with open(local_xml_path, "wb") as e:
        e.write(xml_bytes)

    #  Alan analizi
    analysis_result = analyze_field_full(
        work_item_type,
        field_ref,
        local_xml_path
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
    main()
