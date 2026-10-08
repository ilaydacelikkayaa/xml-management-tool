import requests
import os
import xml.etree.ElementTree as ET
import shutil
import subprocess
from dotenv import load_dotenv


wiql_url = "http://win-9b0e3epo4lv/XMLLabCollection/_apis/wit/wiql?api-version=7.0"

load_dotenv()
token = os.getenv("AZURE_DEVOPS_PAT")



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

    removed_count = 0

    for parent in root.iter():
        for child in list(parent):
            if child.tag == "Control" and child.get("FieldName") == field_ref:
                parent.remove(child)
                removed_count += 1

    if removed_count == 0:
        return {
            "success": False,
            "field_ref": field_ref,
            "message": "No matching UI Control found."
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



analysis_result = analyze_field_full(
    "Issue",
    "Lab.OldSystemCode",
    "/Users/ilayda/Desktop/Issue-after.xml"
)

print(analysis_result)


cleanup_result = evaluate_cleanup_candidate(analysis_result)
print(cleanup_result)


field_report = build_field_report(analysis_result)
print(field_report)


create_result = create_backup(
    "/Users/ilayda/Desktop/Issue-after.xml",
    "/Users/ilayda/Desktop/Issue-backup-python.xml"
)

print(create_result)


hide_result = hide_field_from_ui(
    "/Users/ilayda/Desktop/Issue-after.xml",
    "Lab.OldSystemCode",
    "/Users/ilayda/Desktop/Issue-preview.xml"
)

print(hide_result)


verify_result = find_field_references(
    "/Users/ilayda/Desktop/Issue-preview.xml",
    "Lab.OldSystemCode"
)

print(verify_result)


validation_result = validate_xml(
    "/Users/ilayda/Desktop/Issue-preview.xml"
)
print(validation_result)

# Temporary: witadmin validation was performed manually on Windows VM
azure_validation = True

preview = build_change_preview(
    analysis_result,
    verify_result,
    validation_result,
    azure_validation
)

print(preview)

def can_apply_change(preview: dict, confirmed: bool):
    technical_ready = preview["ready_to_apply"]

    apply_allowed = (technical_ready and confirmed)

    return {
        "technical_ready": technical_ready,
        "confirmed": confirmed,
        "apply_allowed": apply_allowed
    }

test1=can_apply_change(preview=preview,confirmed=False)
test2=can_apply_change(preview=preview,confirmed=True)
print(test1)
print(test2)

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
prepare_apply(test1, "/Users/ilayda/Desktop/Issue-preview.xml")
prepare_result = prepare_apply(
    test2,
    "/Users/ilayda/Desktop/Issue-preview.xml"
)
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
import_result = build_import_command(
    prepare_result,
    "http://win-9b0e3epo4lv/XMLLabCollection",
    "XMLManagementLab",
    r"C:\Issue-preview.xml"
)

print(import_result)


def execute_command(command: str):
    try:
        result = subprocess.run(
            [command],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return {
                "success": True,
                "stdout": result.stdout.strip(),
                "returncode": result.returncode
            }
        else:
            return {
                "success": False,
                "stderr": result.stderr.strip(),
                "returncode": result.returncode
            }

    except FileNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "COMMAND_NOT_FOUND"
        }
    
if import_result["success"] == True:
    execute_result=execute_command(import_result["command"])
else:
    execute_result = import_result
print(execute_result)

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