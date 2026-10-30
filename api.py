from fastapi import FastAPI, Request
from pydantic import BaseModel, Field, ConfigDict
import requests
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from datetime import date
from pathlib import Path
import logging
import difflib
import tempfile
import xml.etree.ElementTree as ET
import hashlib
import json
import re
import threading
import os
import tempfile
from collections import Counter
import shutil
from datetime import datetime, timezone
from devops_backend import (
    get_project_xml,
    list_xml_fields,
    create_winrm_session,
    analyze_field,
    get_collections,
    get_project,
    get_work_item_types,
    preview_hide_field,
    get_field_visibility,
    add_field_to_xml,
    remove_field_from_xml,
    export_global_list,
    add_global_list_item,
    update_global_list_item,
    remove_global_list_item,
    save_global_list_preview,
    save_global_list_backup,
    import_global_list,
    save_wit_preview,
    save_wit_backup,
    import_work_item_type,
    update_field_in_xml,
    get_server_field_info,
    change_field_name,
    validate_remove_field_change,
    cleanup_old_wit_backups,
)
from github_service import (
    pull_xml_from_github,
    push_xml_to_github,
    get_xml_history,
    get_xml_commit_diff,
    list_github_xml_files,
)

logger = logging.getLogger(__name__)
app = FastAPI()

from dotenv import load_dotenv

load_dotenv()
GITHUB_BACKUP_BRANCH = os.getenv("GITHUB_BACKUP_BRANCH")


def get_github_backup_branch():
    if not GITHUB_BACKUP_BRANCH:
        raise ValueError("GITHUB_BACKUP_BRANCH is not configured.")

    return GITHUB_BACKUP_BRANCH


@app.get("/health")
def get_health():
    return {"status": "ok"}


class AddFieldRequest(BaseModel):
    collection_name: str
    project_name: str
    work_item_type: str
    field_name: str
    field_ref: str
    field_type: str
    is_required: bool = False
    is_read_only: bool = False
    show_on_form: bool = True
    help_text: str | None = None


class RemoveFieldRequest(BaseModel):
    collection_name: str
    project_name: str
    work_item_type: str
    field_ref: str


class WorkItemDryRunRequest(BaseModel):
    preview_id: str


class UpdateFieldRequest(BaseModel):
    collection_name: str
    project_name: str
    work_item_type: str
    field_ref: str
    field_name: str | None = None
    is_required: bool | None = None
    is_read_only: bool | None = None
    show_on_form: bool | None = None
    help_text: str | None = None


class MultiProjectFieldRequest(BaseModel):
    collection_name: str
    project_names: list[str] = Field(min_length=1)
    work_item_type: str

    operation: str
    field_name: str | None = None
    field_ref: str
    field_type: str | None = None
    is_required: bool | None = None
    is_read_only: bool | None = None
    show_on_form: bool | None = None
    help_text: str | None = None


class MultiProjectApplyRequest(BaseModel):
    preview_ids: list[str] = Field(min_length=1)
    confirm: bool = False


class AnalysisRequest(BaseModel):
    collection_name: str
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(min_length=1)
    work_item_type: str = Field(min_length=1)
    field_ref: str = Field(min_length=1)
    start_date: date | None = None


class GlobalListAddRequest(BaseModel):
    collection_name: str
    list_name: str
    item_value: str


class GlobalListUpdateRequest(BaseModel):
    collection_name: str
    list_name: str
    old_value: str
    new_value: str


class GlobalListRemoveRequest(BaseModel):
    collection_name: str
    list_name: str
    item_value: str


class ManualXmlEditRequest(BaseModel):
    modified_xml: str = Field(min_length=1)


class WorkItemApplyRequest(BaseModel):
    preview_id: str
    confirm: bool = False


class GitHubPullRequest(BaseModel):
    file_path: str
    branch: str


class GithubPushRequest(BaseModel):
    file_path: str
    branch: str
    xml_content: str
    sha: str | None = None


class GithubWitBackupRequest(BaseModel):
    collection_name: str
    project_name: str
    work_item_type: str
    branch: str


@app.post("/preview-add-field")
def preview_add_field(request: AddFieldRequest):
    try:
        session = create_winrm_session()

        xml_bytes = get_project_xml(
            session,
            request.collection_name,
            request.project_name,
            request.work_item_type,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            current_path = Path(temp_dir) / "current.xml"
            preview_path = Path(temp_dir) / "preview.xml"

            current_path.write_bytes(xml_bytes)

            result = add_field_to_xml(
                xml_path=str(current_path),
                field_name=request.field_name,
                field_ref=request.field_ref,
                field_type=request.field_type,
                output_path=str(preview_path),
                is_required=request.is_required,
                is_read_only=request.is_read_only,
                show_on_form=request.show_on_form,
                help_text=request.help_text,
            )

            preview_xml = preview_path.read_bytes()

            saved_preview = save_wit_preview(
                original_xml=xml_bytes,
                preview_xml=preview_xml,
                collection_name=request.collection_name,
                project_name=request.project_name,
                work_item_type=request.work_item_type,
                operation="add",
                field_ref=request.field_ref,
            )

            root = ET.fromstring(preview_xml)

            return {
                "success": True,
                "action": "ADD_FIELD",
                "field_ref": request.field_ref,
                "result": result,
                "preview_xml": ET.tostring(root, encoding="unicode"),
                "preview_id": saved_preview["preview_id"],
                "original_sha256": saved_preview["original_sha256"],
            }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception:
        logger.exception("Alan ekleme önizlemesi başarısız")
        raise HTTPException(
            status_code=500, detail="Alan ekleme önizlemesi oluşturulamadı"
        )


@app.post("/preview-update-field")
def preview_update_field(request: UpdateFieldRequest):
    try:
        session = create_winrm_session()

        xml_bytes = get_project_xml(
            session,
            request.collection_name,
            request.project_name,
            request.work_item_type,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            current_path = Path(temp_dir) / "current.xml"
            preview_path = Path(temp_dir) / "preview.xml"

            current_path.write_bytes(xml_bytes)

            result = update_field_in_xml(
                xml_path=str(current_path),
                field_ref=request.field_ref,
                new_field_name=request.field_name,
                output_path=str(preview_path),
                is_required=request.is_required,
                is_read_only=request.is_read_only,
                show_on_form=request.show_on_form,
                help_text=request.help_text,
            )

            preview_xml = preview_path.read_bytes()
            validation = validate_update_field_change(
                original_xml=xml_bytes,
                modified_xml=preview_xml,
                field_ref=request.field_ref,
                field_name=request.field_name,
                is_required=request.is_required,
                is_read_only=request.is_read_only,
                show_on_form=request.show_on_form,
                help_text=request.help_text,
            )

            saved_preview = save_wit_preview(
                original_xml=xml_bytes,
                preview_xml=preview_xml,
                collection_name=request.collection_name,
                project_name=request.project_name,
                work_item_type=request.work_item_type,
                operation="update",
                field_ref=request.field_ref,
                update_options={
                    "field_name": request.field_name,
                    "is_required": request.is_required,
                    "is_read_only": request.is_read_only,
                    "show_on_form": request.show_on_form,
                    "help_text": request.help_text,
                },
            )

            root = ET.fromstring(preview_xml)

            return {
                "success": True,
                "action": "UPDATE_FIELD",
                "field_ref": request.field_ref,
                "result": result,
                "preview_xml": ET.tostring(root, encoding="unicode"),
                "preview_id": saved_preview["preview_id"],
                "original_sha256": saved_preview["original_sha256"],
                "validation": validation,
            }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception:
        logger.exception("Alan güncelleme önizlemesi başarısız")
        raise HTTPException(
            status_code=500, detail="Alan güncelleme önizlemesi oluşturulamadı"
        )


@app.post("/preview-remove-field")
def preview_remove_field(request: RemoveFieldRequest):
    try:
        session = create_winrm_session()

        xml_bytes = get_project_xml(
            session,
            request.collection_name,
            request.project_name,
            request.work_item_type,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            current_path = Path(temp_dir) / "current.xml"
            preview_path = Path(temp_dir) / "preview.xml"

            current_path.write_bytes(xml_bytes)

            result = remove_field_from_xml(
                xml_path=str(current_path),
                field_ref=request.field_ref,
                output_path=str(preview_path),
            )

            stderr = (result.get("stderr") or "").strip()

            if not result["success"] or re.search(r"\bTF\d{5}\s*:", stderr):
                return result

            preview_xml = preview_path.read_bytes()
            saved_preview = save_wit_preview(
                original_xml=xml_bytes,
                preview_xml=preview_xml,
                collection_name=request.collection_name,
                project_name=request.project_name,
                work_item_type=request.work_item_type,
                operation="remove",
                field_ref=request.field_ref,
            )
            root = ET.fromstring(preview_xml)

            return {
                "success": True,
                "action": "REMOVE_FIELD",
                "field_ref": request.field_ref,
                "result": result,
                "preview_xml": ET.tostring(root, encoding="unicode"),
                "preview_id": saved_preview["preview_id"],
                "original_sha256": saved_preview["original_sha256"],
            }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception:
        logger.exception("Alan silme önizlemesi başarısız")
        raise HTTPException(
            status_code=500, detail="Alan silme önizlemesi oluşturulamadı"
        )


@app.get("/xml-fields")
def get_xml_fields(collection_name: str, project_name: str, work_item_type: str):
    create_session = create_winrm_session()
    try:
        xml_bytes = get_project_xml(
            create_session, collection_name, project_name, work_item_type
        )
        result = list_xml_fields(xml_bytes)
        return result

    except RuntimeError as error:
        if "TF201077" in str(error):
            raise HTTPException(
                status_code=404, detail="Belirtilen Work Item Type bulunamadı."
            ) from error
        logger.exception("XML Fields yüklenirken hata oluştu")
        raise HTTPException(
            status_code=500,
            detail="XML Fields alınamadı. Backend loglarını kontrol edin.",
        ) from error


@app.get("/global-lists")
def get_global_lists(collection_name: str):

    try:
        session = create_winrm_session()

        xml_bytes = export_global_list(session, collection_name)
        root = ET.fromstring(xml_bytes)

        if root.tag.split("}")[-1] != "GLOBALLISTS":
            raise HTTPException(status_code=400, detail="Geçersiz GlobalList XML'i.")

        global_lists = []

        for global_list in root.iter("GLOBALLIST"):
            list_name = global_list.get("name")

            values = [item.get("value") for item in global_list.iter("LISTITEM")]

            global_lists.append({"name": list_name, "values": values})

        xml_text = ET.tostring(root, encoding="unicode")

        return {
            "success": True,
            "collection": collection_name,
            "xml": xml_text,
            "global_lists": global_lists,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("GlobalList export başarısız")
        raise HTTPException(status_code=500, detail="GlobalList verileri alınamadı.")


@app.get("/collections")
def take_collections():
    try:
        collection = get_collections()
        return collection
    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Belirtilen Collections bulunamadı."
        ) from error


@app.get("/projects")
def take_projects(collection_name: str):
    print("FastAPI PAT tanımlı mı?", bool(os.getenv("AZURE_DEVOPS_PAT")))
    try:
        projects = get_project(collection_name)
        return projects

    except requests.exceptions.RequestException as error:
        logger.exception("Project listesi alınırken Azure DevOps bağlantı hatası")
        raise HTTPException(
            status_code=502, detail="Azure DevOps Server'dan Project listesi alınamadı."
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Project listesi alınırken bir hata oluştu."
        ) from error


@app.get("/work_item_type")
def take_work_item_type(collection_name: str, project_name: str):
    try:
        wit_type = get_work_item_types(collection_name, project_name)
        return wit_type
    except requests.exceptions.HTTPError as error:
        if error.response is not None and error.response.status_code == 404:
            raise HTTPException(
                status_code=404, detail="Belirtilen proje bulunamadı."
            ) from error

        raise HTTPException(
            status_code=502, detail="Azure DevOps Server isteği başarısız oldu."
        ) from error
    except requests.exceptions.RequestException as error:
        logger.exception("Work Item Type listesi alınırken hata oluştu")
        raise HTTPException(
            status_code=502, detail="Work item type belirlenemedi"
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=500, detail="Azure DevOps bağlantı yapılandırması eksik."
        ) from error


def write_json_atomic(path: Path, data: dict):
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

            json.dump(data, temp_file)

            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, path)

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def update_wit_backup_status(backup_id: str, status: str):
    if status not in {"verified", "needs_investigation"}:
        raise ValueError("Geçersiz backup durumu.")

    if not re.fullmatch(r"[0-9a-f]{32}", backup_id):
        raise ValueError("Geçersiz backup ID.")

    backup_dir = Path("backups") / "work-item-types" / backup_id
    metadata_path = backup_dir / "metadata.json"

    if not metadata_path.is_file():
        raise FileNotFoundError("Backup metadata bulunamadı.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if not isinstance(metadata, dict):
        raise ValueError("Backup metadata geçersiz.")

    if metadata.get("backup_id") != backup_id:
        raise ValueError("Backup ID uyuşmuyor.")

    if metadata.get("status") != "pending":
        raise ValueError("Backup beklenen durumda değil.")

    metadata["status"] = status
    write_json_atomic(metadata_path, metadata)

    return {
        "success": True,
        "backup_id": backup_id,
        "status": status,
    }


@app.post("/preview-hide-field")
def preview_hide_field_endpoint(
    collection_name: str, project_name: str, work_item_type: str, field_ref: str
):
    try:
        session = create_winrm_session()

        result = preview_hide_field(
            session=session,
            collection_name=collection_name,
            project_name=project_name,
            work_item_type=work_item_type,
            field_ref=field_ref,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/visibility")
def is_visible(collection_name: str, project_name: str, work_item_type: str):
    try:
        session = create_winrm_session()

        xml_bytes = get_project_xml(
            session, collection_name, project_name, work_item_type
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            xml_path = Path(temp_dir) / "current.xml"
            xml_path.write_bytes(xml_bytes)

            result = get_field_visibility(str(xml_path))

        return {"success": True, "fields": result}

    except Exception:
        logger.exception("Field visibility sorgusu başarısız")
        raise HTTPException(status_code=500, detail="Alan görünürlüğü alınamadı")


@app.exception_handler(requests.exceptions.Timeout)
async def timeout_handler(request: Request, exc: requests.exceptions.Timeout):
    return JSONResponse(
        status_code=504, content={"detail": "Azure DevOps request timed out."}
    )


@app.exception_handler(requests.exceptions.HTTPError)
async def http_handler(request: Request, exc: requests.exceptions.HTTPError):
    return JSONResponse(status_code=502, content="Bad Gateway")


@app.post("/analyses")
def build_analysis(request: AnalysisRequest):
    print("API'YE GELEN TARİH:", request.start_date, flush=True)

    result = analyze_field(
        request.work_item_type,
        request.field_ref,
        request.project_name,
        request.start_date,
        collection_name=request.collection_name,
    )

    return result


def create_global_list_preview(collection_name, operation, **kwargs):

    session = create_winrm_session()

    xml_bytes = export_global_list(session, collection_name)

    with tempfile.TemporaryDirectory() as temp_dir:

        original_path = Path(temp_dir) / "original.xml"
        preview_path = Path(temp_dir) / "preview.xml"

        original_path.write_bytes(xml_bytes)

        if operation == "add":
            result = add_global_list_item(
                str(original_path),
                kwargs["list_name"],
                kwargs["item_value"],
                str(preview_path),
            )

        elif operation == "update":
            result = update_global_list_item(
                str(original_path),
                kwargs["list_name"],
                kwargs["old_value"],
                kwargs["new_value"],
                str(preview_path),
            )

        elif operation == "remove":
            result = remove_global_list_item(
                str(original_path),
                kwargs["list_name"],
                kwargs["item_value"],
                str(preview_path),
            )

        else:
            raise ValueError("Geçersiz işlem")

        if not result.get("success"):
            raise ValueError(result.get("message", "İşlem başarısız"))

        preview_bytes = preview_path.read_bytes()

        ET.fromstring(preview_bytes)
        saved_preview = save_global_list_preview(
            original_xml=xml_bytes,
            preview_xml=preview_bytes,
            collection_name=collection_name,
            operation=operation,
        )

        return {
            **result,
            "collection_name": collection_name,
            "preview_xml": preview_bytes.decode("utf-8-sig"),
            "message": "Önizleme oluşturuldu. Sunucuya uygulanmadı.",
            "preview_id": saved_preview["preview_id"],
            "original_sha256": saved_preview["original_sha256"],
        }


@app.post("/global-lists/preview-add")
def preview_add_global_list(request: GlobalListAddRequest):

    try:
        return create_global_list_preview(
            request.collection_name,
            "add",
            list_name=request.list_name,
            item_value=request.item_value,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/global-lists/preview-update")
def preview_update_global_list(request: GlobalListUpdateRequest):

    try:
        return create_global_list_preview(
            request.collection_name,
            "update",
            list_name=request.list_name,
            old_value=request.old_value,
            new_value=request.new_value,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/global-lists/preview-remove")
def preview_remove_global_list(request: GlobalListRemoveRequest):

    try:
        return create_global_list_preview(
            request.collection_name,
            "remove",
            list_name=request.list_name,
            item_value=request.item_value,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


global_list_apply_lock = threading.Lock()


class GlobalListApplyRequest(BaseModel):
    preview_id: str
    confirm: bool = False


@app.post("/global-lists/apply")
def apply_global_list(request: GlobalListApplyRequest):

    if not request.confirm:
        raise HTTPException(status_code=400, detail="Import için açık onay gerekli.")

    if not re.fullmatch(r"[0-9a-f]{32}", request.preview_id):
        raise HTTPException(status_code=400, detail="Geçersiz preview_id.")

    preview_dir = Path("previews") / "global-lists" / request.preview_id

    if not preview_dir.is_dir():
        raise HTTPException(status_code=404, detail="Preview bulunamadı.")

    with global_list_apply_lock:

        metadata_path = preview_dir / "metadata.json"
        original_path = preview_dir / "original.xml"
        modified_path = preview_dir / "preview.xml"

        if not all(
            path.is_file() for path in (metadata_path, original_path, modified_path)
        ):
            raise HTTPException(status_code=400, detail="Preview dosyaları eksik.")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        if metadata.get("preview_id") != request.preview_id:
            raise HTTPException(status_code=400, detail="Preview kimliği uyuşmuyor.")

        collection_name = metadata["collection_name"]

        # Collection seçimi dinamik olarak yapılır.
        # Import işlemi öncesinde collection adı doğrulanır.
        if not collection_name or not collection_name.strip():
            raise HTTPException(
                status_code=400,
                detail="Geçerli bir collection seçilmelidir.",
            )

        original_xml = original_path.read_bytes()
        modified_xml = modified_path.read_bytes()

        original_hash = hashlib.sha256(original_xml).hexdigest()

        modified_hash = hashlib.sha256(modified_xml).hexdigest()

        if original_hash != metadata.get(
            "original_sha256"
        ) or modified_hash != metadata.get("preview_sha256"):
            raise HTTPException(status_code=409, detail="Preview dosyaları değişmiş.")

        # XML biçimini doğrula
        original_root = ET.fromstring(original_xml)
        modified_root = ET.fromstring(modified_xml)

        for root in (original_root, modified_root):
            if root.tag.split("}")[-1] != "GLOBALLISTS":
                raise HTTPException(
                    status_code=400, detail="Geçersiz GlobalList XML'i."
                )

        if original_xml == modified_xml:
            raise HTTPException(status_code=400, detail="Uygulanacak değişiklik yok.")

        session = create_winrm_session()

        # Sunucunun mevcut durumunu tekrar oku
        current_xml = export_global_list(session, collection_name)

        current_hash = hashlib.sha256(current_xml).hexdigest()

        if current_hash != original_hash:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Sunucudaki GlobalList değişmiş. " "Yeni preview oluşturmalısın."
                ),
            )

        # Import öncesi kalıcı backup
        backup = save_global_list_backup(current_xml, collection_name)

        # Bu satır gerçek sunucu değişikliğini gerçekleştirir
        import_global_list(session, collection_name, modified_xml)

        # Import sonrası doğrulama
        # Import sonrası doğrulama
        verified_xml = export_global_list(session, collection_name)

        def global_list_snapshot(xml_bytes):
            root = ET.fromstring(xml_bytes)

            def local_name(element):
                return element.tag.split("}")[-1]

            if local_name(root) != "GLOBALLISTS":
                raise ValueError("Geçersiz GlobalList XML kökü.")

            result = {}

            for global_list in root:
                if local_name(global_list) != "GLOBALLIST":
                    raise ValueError("Beklenmeyen GlobalList elemanı.")

                name = global_list.get("name")

                if not name or name in result:
                    raise ValueError("Eksik veya tekrarlanan GlobalList adı.")

                values = []

                for item in global_list:
                    if local_name(item) != "LISTITEM":
                        raise ValueError("Beklenmeyen liste elemanı.")

                    value = item.get("value")

                    if value is None or value in values:
                        raise ValueError("Eksik veya tekrarlanan LISTITEM.")

                    values.append(value)

                result[name] = set(values)

            return result

        try:
            expected = global_list_snapshot(modified_xml)
            actual = global_list_snapshot(verified_xml)
        except (ET.ParseError, ValueError) as exc:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Import sonrası GlobalList XML doğrulanamadı: {exc}. "
                    f"Backup: {backup['backup_path']}"
                ),
            )

        if actual != expected:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Import tamamlandı ancak GlobalList içerikleri "
                    "önizlemeyle eşleşmedi. "
                    f"Backup: {backup['backup_path']}"
                ),
            )

        return {
            "success": True,
            "collection_name": collection_name,
            "preview_id": request.preview_id,
            "backup_id": backup["backup_id"],
            "backup_path": backup["backup_path"],
            "message": "GlobalList sunucuya uygulandı ve doğrulandı.",
        }


wit_apply_lock = threading.Lock()


def validate_add_field_change(original_xml: bytes, modified_xml: bytes):
    import copy
    from collections import Counter

    original_root = ET.fromstring(original_xml)
    modified_root = ET.fromstring(modified_xml)

    def local_name(element):
        return element.tag.split("}")[-1]

    def normalize(element):
        return (
            element.tag,
            tuple(sorted(element.attrib.items())),
            (element.text or "").strip(),
            tuple(normalize(child) for child in element),
        )

    # 1. FIELD elemanlarını bul
    original_fields = [
        element for element in original_root.iter() if local_name(element) == "FIELD"
    ]

    modified_fields = [
        element for element in modified_root.iter() if local_name(element) == "FIELD"
    ]

    original_refs = [field.get("refname") for field in original_fields]
    modified_refs = [field.get("refname") for field in modified_fields]

    # 2. Eklenen ve silinen FIELD sayılarını karşılaştır
    original_counts = Counter(original_refs)
    modified_counts = Counter(modified_refs)

    added_counts = modified_counts - original_counts
    removed_counts = original_counts - modified_counts

    if removed_counts:
        raise ValueError("Add işleminde mevcut FIELD elemanı silinemez.")

    if sum(added_counts.values()) != 1:
        raise ValueError("Add işleminde tam olarak bir FIELD eklenmelidir.")

    added_ref = next(iter(added_counts))

    if not added_ref:
        raise ValueError("Yeni field refname değeri boş.")

    modified_field = next(
        field for field in modified_fields if field.get("refname") == added_ref
    )
    # Yeni field'ın temel özelliklerini doğrula
    field_name = modified_field.get("name")
    field_type = modified_field.get("type")

    if not added_ref.startswith("Lab."):
        raise ValueError(
            "Test ortamında yalnızca Lab. ile başlayan field'lar eklenebilir."
        )

    if not re.fullmatch(r"Lab\.[A-Za-z][A-Za-z0-9_]*", added_ref):
        raise ValueError("Geçersiz field reference name.")

    if not field_name or not field_name.strip():
        raise ValueError("Field name boş olamaz.")

    if field_type != "String":
        raise ValueError(
            "İlk gerçek Apply testinde yalnızca String field destekleniyor."
        )

    if len(modified_field.attrib) != 3:
        raise ValueError("Yeni FIELD beklenmeyen XML özellikleri içeriyor.")

    allowed_rules = {"REQUIRED", "READONLY", "HELPTEXT"}
    rules = [local_name(child) for child in modified_field]

    if len(rules) != len(set(rules)):
        raise ValueError("Aynı FIELD kuralı birden fazla eklenemez.")

    if set(rules) - allowed_rules:
        raise ValueError("Yeni FIELD desteklenmeyen kurallar içeriyor.")

    if "REQUIRED" in rules and "READONLY" in rules:
        raise ValueError("Required ve Read Only birlikte kullanılamaz.")

    for child in modified_field:
        if child.attrib or list(child):
            raise ValueError("FIELD kuralında beklenmeyen XML yapısı var.")

        if local_name(child) == "HELPTEXT":
            if not (child.text or "").strip():
                raise ValueError("Help Text boş olamaz.")
        elif (child.text or "").strip():
            raise ValueError("Required veya Read Only içinde metin olamaz.")

    # 3. Yeni FIELD yalnızca FIELDS altında olmalı
    field_locations = []

    for parent in modified_root.iter():
        for child in parent:
            if local_name(child) == "FIELD" and child.get("refname") == added_ref:
                field_locations.append(local_name(parent))

    if field_locations != ["FIELDS"]:
        raise ValueError("Yeni FIELD yalnızca FIELDS bölümüne eklenebilir.")

    new_controls = [
        element
        for element in modified_root.iter()
        if local_name(element) == "Control" and element.get("FieldName") == added_ref
    ]

    # İlk Apply testinde en fazla bir Control destekliyoruz.
    if len(new_controls) not in {0, 2}:
        raise ValueError(
            "Yeni field için ya hiç Control olmamalı "
            "ya da Layout ve WebLayout içinde birer Control bulunmalı."
        )
    if len(new_controls) == 2:
        locations = []

        for control in new_controls:
            for layout_name in ("Layout", "WebLayout"):
                for layout in modified_root.iter():
                    if local_name(layout) == layout_name and control in layout.iter():
                        locations.append(layout_name)

        if sorted(locations) != ["Layout", "WebLayout"]:
            raise ValueError(
                "Control elemanları Layout ve WebLayout içinde birer tane olmalı."
            )

    for control in new_controls:
        # Control mutlaka FORM altında bulunmalı.
        inside_form = any(
            local_name(element) == "FORM" and control in element.iter()
            for element in modified_root.iter()
        )

        if not inside_form:
            raise ValueError("Yeni Control, FORM dışında bulunuyor.")

        if control.get("Type") != "FieldControl":
            raise ValueError("Yalnızca FieldControl türü destekleniyor.")

        if control.get("FieldName") != added_ref:
            raise ValueError("Control FieldName ile yeni field uyuşmuyor.")

        allowed_attributes = {"FieldName", "Type", "Label", "LabelPosition"}

        if set(control.attrib) - allowed_attributes:
            raise ValueError("Control beklenmeyen XML özellikleri içeriyor.")

        if list(control):
            raise ValueError("Yeni Control altında ek XML elemanına izin verilmiyor.")
    original_controls = [
        element
        for element in original_root.iter()
        if local_name(element) == "Control" and element.get("FieldName") == added_ref
    ]

    if original_controls:
        raise ValueError("Yeni field'a ait Control orijinal XML'de zaten bulunuyor.")
    comparison_root = copy.deepcopy(modified_root)

    for parent in comparison_root.iter():
        for child in list(parent):
            if local_name(child) == "FIELD" and child.get("refname") == added_ref:
                parent.remove(child)

    for parent in comparison_root.iter():
        for child in list(parent):
            if local_name(child) == "Control" and child.get("FieldName") == added_ref:
                parent.remove(child)

    if normalize(original_root) != normalize(comparison_root):

        original_text = ET.tostring(original_root, encoding="unicode").splitlines()

        comparison_text = ET.tostring(comparison_root, encoding="unicode").splitlines()

        diff = difflib.unified_diff(
            original_text,
            comparison_text,
            fromfile="original",
            tofile="modified_without_new_field",
            lineterm="",
        )

        print(
            "ADD VALIDATION DIFF:\n" + "\n".join(list(diff)[:60]),
            flush=True,
        )

        raise ValueError("Yeni field dışında XML'de başka değişiklik tespit edildi.")

    return {
        "success": True,
        "added_field_ref": added_ref,
        "added_field_name": modified_field.get("name"),
    }


def validate_update_rules(original_field, modified_field):
    allowed_rules = {"REQUIRED", "READONLY", "HELPTEXT"}

    def other_children(field):
        return [
            ET.tostring(child, encoding="unicode")
            for child in field
            if child.tag.split("}")[-1] not in allowed_rules
        ]

    if other_children(original_field) != other_children(modified_field):
        raise ValueError("Update sırasında izin verilmeyen FIELD kuralları değişmiş.")

    for field in (original_field, modified_field):
        required = field.find("REQUIRED") is not None
        readonly = field.find("READONLY") is not None

        if required and readonly:
            raise ValueError("FIELD aynı anda Required ve ReadOnly olamaz.")


def validate_update_field_change(
    original_xml: bytes,
    modified_xml: bytes,
    field_ref: str,
    field_name: str | None = None,
    is_required: bool | None = None,
    is_read_only: bool | None = None,
    show_on_form: bool | None = None,
    help_text: str | None = None,
):
    import copy
    from collections import Counter

    def local_name(element):
        return element.tag.split("}")[-1]

    def main_fields(root):
        sections = [child for child in root if local_name(child) == "FIELDS"]

        if len(sections) != 1:
            raise ValueError("Ana FIELDS bölümü tekil bulunamadı.")

        fields = [child for child in sections[0] if local_name(child) == "FIELD"]

        refs = [field.get("refname") for field in fields]

        if any(not ref for ref in refs):
            raise ValueError("Refname olmayan FIELD bulundu.")

        if len(refs) != len(set(refs)):
            raise ValueError("Tekrarlanan FIELD refname bulundu.")

        return fields

    def find_target(fields):
        matches = [field for field in fields if field.get("refname") == field_ref]

        if len(matches) != 1:
            raise ValueError("Hedef FIELD tekil bulunamadı.")

        return matches[0]

    def normalize(element):
        return (
            local_name(element),
            tuple(sorted(element.attrib.items())),
            (element.text or "").strip(),
            tuple(normalize(child) for child in element),
        )

    def check_rules(original_field, modified_field):
        allowed = {"REQUIRED", "READONLY", "HELPTEXT"}

        for field in (original_field, modified_field):
            rules = [child for child in field if local_name(child) in allowed]

            names = [local_name(rule) for rule in rules]

            if len(names) != len(set(names)):
                raise ValueError("Tekrarlanan FIELD kuralı bulundu.")

            if "REQUIRED" in names and "READONLY" in names:
                raise ValueError("Required ve ReadOnly birlikte kullanılamaz.")

            for rule in rules:
                if rule.attrib or len(rule):
                    raise ValueError("FIELD kuralında beklenmeyen yapı bulundu.")

                if (
                    local_name(rule) in {"REQUIRED", "READONLY"}
                    and (rule.text or "").strip()
                ):
                    raise ValueError("Required/ReadOnly içinde metin olamaz.")

        def other_rules(field):
            return [
                normalize(child) for child in field if local_name(child) not in allowed
            ]

        if other_rules(original_field) != other_rules(modified_field):
            raise ValueError("İzin verilmeyen FIELD kuralları değiştirilmiş.")

    def controls_by_location(root):
        result = {}

        form_sections = [child for child in root if local_name(child) == "FORM"]

        if len(form_sections) != 1:
            raise ValueError("FORM bölümü tekil bulunamadı.")

        form = form_sections[0]

        for layout_name in ("Layout", "WebLayout"):
            layouts = [child for child in form if local_name(child) == layout_name]

            if len(layouts) > 1:
                raise ValueError(f"Birden fazla {layout_name} bulundu.")

            controls = []

            for layout in layouts:
                for element in layout.iter():
                    if (
                        local_name(element) == "Control"
                        and element.get("FieldName") == field_ref
                    ):
                        controls.append(element)

            if len(controls) > 1:
                raise ValueError(f"{layout_name} içinde tekrarlanan Control.")

            result[layout_name] = controls

        return result

    def remove_target_controls(root):
        form = next(
            (child for child in root if local_name(child) == "FORM"),
            None,
        )

        if form is None:
            return

        for parent in form.iter():
            for child in list(parent):
                if (
                    local_name(child) == "Control"
                    and child.get("FieldName") == field_ref
                ):
                    parent.remove(child)

    def remove_target_field(root):
        fields_section = next(child for child in root if local_name(child) == "FIELDS")

        for child in list(fields_section):
            if local_name(child) == "FIELD" and child.get("refname") == field_ref:
                fields_section.remove(child)

    if not field_ref.startswith("Lab."):
        raise ValueError("Yalnızca Lab.* FIELD güncellenebilir.")

    original_root = ET.fromstring(original_xml)
    modified_root = ET.fromstring(modified_xml)

    def get_work_item_type(root):
        if local_name(root) != "WITD":
            raise ValueError("XML kökü WITD olmalıdır.")

        matches = [child for child in root if local_name(child) == "WORKITEMTYPE"]

        if len(matches) != 1:
            raise ValueError("WORKITEMTYPE tekil bulunamadı.")

        return matches[0]

    original_wit = get_work_item_type(original_root)
    modified_wit = get_work_item_type(modified_root)

    original_list = main_fields(original_wit)
    modified_list = main_fields(modified_wit)

    original_controls = controls_by_location(original_wit)
    modified_controls = controls_by_location(modified_wit)

    original_refs = [field.get("refname") for field in original_list]
    modified_refs = [field.get("refname") for field in modified_list]

    if Counter(original_refs) != Counter(modified_refs):
        raise ValueError("Update sırasında FIELD eklenemez/silinemez.")

    original_field = find_target(original_list)
    modified_field = find_target(modified_list)

    if original_field.get("type") != "String":
        raise ValueError("Yalnızca String FIELD güncellenebilir.")

    for attribute in set(original_field.attrib) | set(modified_field.attrib):
        if attribute == "name":
            continue

        if original_field.get(attribute) != modified_field.get(attribute):
            raise ValueError(f"FIELD attribute değiştirilemez: {attribute}")

    new_name = modified_field.get("name")

    if not new_name or not new_name.strip():
        raise ValueError("FIELD adı boş olamaz.")

    check_rules(original_field, modified_field)

    def has_rule(field, rule_name):
        return any(local_name(child) == rule_name for child in field)

    for rule_name, requested_value in (
        ("REQUIRED", is_required),
        ("READONLY", is_read_only),
    ):
        before = has_rule(original_field, rule_name)
        after = has_rule(modified_field, rule_name)

        expected = before if requested_value is None else requested_value

        if after != expected:
            raise ValueError(
                f"{rule_name} beklenen değerle eşleşmiyor. "
                f"Beklenen: {expected}, Gerçekleşen: {after}"
            )

    old_field_name = original_field.get("name")
    new_field_name = modified_field.get("name")

    expected_name = (
        field_name.strip()
        if field_name is not None and field_name.strip()
        else old_field_name
    )

    if new_field_name != expected_name:
        raise ValueError(
            f"FIELD name beklenen değerle eşleşmiyor. "
            f"Beklenen: {expected_name}, Gerçekleşen: {new_field_name}"
        )

    def get_help_text(field):
        for child in field:
            if local_name(child) == "HELPTEXT":
                return (child.text or "").strip()
        return None

    old_help_text = get_help_text(original_field)
    new_help_text = get_help_text(modified_field)

    expected_help_text = (
        old_help_text if help_text is None else (help_text.strip() or None)
    )

    if new_help_text != expected_help_text:
        raise ValueError("HELPTEXT beklenen değerle eşleşmiyor.")
    old_name = original_field.get("name")

    for layout_name in ("Layout", "WebLayout"):
        before = original_controls[layout_name]
        after = modified_controls[layout_name]

        if show_on_form is None:
            if len(before) != len(after):
                raise ValueError(
                    f"{layout_name}: Control sayısı beklenmedik şekilde değişti."
                )

        elif show_on_form is False:
            if after:
                raise ValueError(
                    f"{layout_name}: Alan gizlenmek istendi ama Control hâlâ mevcut."
                )

        elif show_on_form is True:
            if before and not after:
                raise ValueError(
                    f"{layout_name}: Mevcut Control beklenmedik şekilde silindi."
                )

        for control in before + after:
            if local_name(control) != "Control":
                raise ValueError("Geçersiz Control.")

            if len(control):
                raise ValueError("Control altında beklenmeyen element bulundu.")

        if before and after:
            old_attrs = dict(before[0].attrib)
            new_attrs = dict(after[0].attrib)

            if new_name != old_name and old_attrs.get("Label") is not None:
                old_attrs["Label"] = new_name

            if old_attrs != new_attrs:
                raise ValueError(
                    f"{layout_name} Control özellikleri beklenmedik değişti."
                )

        elif after and not before:
            attrs = after[0].attrib

            if attrs.get("FieldName") != field_ref:
                raise ValueError("Control FieldName hatalı.")

            if attrs.get("Type") != "FieldControl":
                raise ValueError("Control Type hatalı.")

            if attrs.get("Label") != new_name:
                raise ValueError("Yeni Control Label hatalı.")

    original_copy = copy.deepcopy(original_root)
    modified_copy = copy.deepcopy(modified_root)

    original_wit_copy = get_work_item_type(original_copy)
    modified_wit_copy = get_work_item_type(modified_copy)

    remove_target_field(original_wit_copy)
    remove_target_field(modified_wit_copy)

    remove_target_controls(original_wit_copy)
    remove_target_controls(modified_wit_copy)

    if normalize(original_copy) != normalize(modified_copy):
        raise ValueError("Update sırasında XML'in başka bölümleri değiştirilmiş.")

    return {
        "success": True,
        "field_ref": field_ref,
        "old_name": old_name,
        "new_name": new_name,
        "is_required": modified_field.find("REQUIRED") is not None,
        "is_read_only": modified_field.find("READONLY") is not None,
        "help_text": (modified_field.findtext("HELPTEXT")),
        "show_on_form": any(modified_controls.values()),
        "message": "Update XML temel güvenlik doğrulamasını geçti.",
    }


@app.post("/work-item-types/apply")
def apply_work_item_type(request: WorkItemApplyRequest):

    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Import için açık onay gerekli.",
        )

    if not re.fullmatch(r"[0-9a-f]{32}", request.preview_id):
        raise HTTPException(
            status_code=400,
            detail="Geçersiz preview_id.",
        )

    preview_dir = Path("previews") / "work-item-types" / request.preview_id

    if not preview_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Preview bulunamadı.",
        )

    with wit_apply_lock:

        metadata_path = preview_dir / "metadata.json"
        original_path = preview_dir / "original.xml"
        modified_path = preview_dir / "preview.xml"
        applied_path = preview_dir / "applied.json"

        if applied_path.exists():
            raise HTTPException(
                status_code=409,
                detail="Bu preview daha önce uygulanmış veya import başlatılmış.",
            )

        if not all(
            path.is_file() for path in (metadata_path, original_path, modified_path)
        ):
            raise HTTPException(
                status_code=400,
                detail="Preview dosyaları eksik.",
            )

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            original_xml = original_path.read_bytes()
            modified_xml = modified_path.read_bytes()

        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Preview okunamadı: {exc}",
            )

        if not isinstance(metadata, dict):
            raise HTTPException(
                status_code=400,
                detail="Preview metadata geçersiz.",
            )

        if metadata.get("preview_id") != request.preview_id:
            raise HTTPException(
                status_code=400,
                detail="Preview kimliği uyuşmuyor.",
            )

        collection_name = metadata.get("collection_name")
        project_name = metadata.get("project_name")
        work_item_type = metadata.get("work_item_type")

        target_valid = all(
            isinstance(value, str) and bool(value.strip())
            for value in (
                collection_name,
                project_name,
                work_item_type,
            )
        )

        if not target_valid:
            raise HTTPException(
                status_code=400,
                detail=("Collection, Project veya Work Item Type " "bilgisi geçersiz."),
            )

        operation = metadata.get("operation")
        if operation not in ("add", "update", "remove", "manual_edit"):
            raise HTTPException(
                status_code=403,
                detail="Gerçek Apply yalnızca Add, Update, Remove ve doğrulanmış Manual Edit işlemlerini destekliyor.",
            )

        original_hash = hashlib.sha256(original_xml).hexdigest()
        modified_hash = hashlib.sha256(modified_xml).hexdigest()

        if original_hash != metadata.get(
            "original_sha256"
        ) or modified_hash != metadata.get("preview_sha256"):
            raise HTTPException(
                status_code=409,
                detail="Preview dosyalarının içeriği değişmiş.",
            )

        try:
            original_root = ET.fromstring(original_xml)
            modified_root = ET.fromstring(modified_xml)

        except ET.ParseError:
            raise HTTPException(
                status_code=400,
                detail="XML biçimi geçersiz.",
            )

        if (
            original_root.tag.split("}")[-1] != "WITD"
            or modified_root.tag.split("}")[-1] != "WITD"
        ):
            raise HTTPException(
                status_code=400,
                detail="Geçersiz Work Item Type XML.",
            )

        for root in (original_root, modified_root):
            wit_node = next(
                (
                    element
                    for element in root.iter()
                    if element.tag.split("}")[-1] == "WORKITEMTYPE"
                ),
                None,
            )

            if wit_node is None or wit_node.get("name") != work_item_type:
                raise HTTPException(
                    status_code=400,
                    detail="XML içindeki Work Item Type uyuşmuyor.",
                )

        if original_xml == modified_xml:
            raise HTTPException(
                status_code=400,
                detail="Uygulanacak değişiklik yok.",
            )

        # Operasyona özel XML güvenlik doğrulaması
        try:
            if operation == "add":
                field_change = validate_add_field_change(
                    original_xml,
                    modified_xml,
                )

                if field_change["added_field_ref"] != metadata.get("field_ref"):
                    raise ValueError(
                        "Preview'daki field ile metadata'daki " "field uyuşmuyor."
                    )

            elif operation == "update":
                options = metadata.get("update_options")

                expected_keys = {
                    "field_name",
                    "is_required",
                    "is_read_only",
                    "show_on_form",
                    "help_text",
                }

                if not isinstance(options, dict) or set(options) != expected_keys:
                    raise ValueError("Update seçenekleri eksik veya geçersiz.")

                for key in (
                    "is_required",
                    "is_read_only",
                    "show_on_form",
                ):
                    if options[key] is not None and type(options[key]) is not bool:
                        raise ValueError(f"Geçersiz {key} değeri.")

                for key in ("field_name", "help_text"):
                    if options[key] is not None and not isinstance(options[key], str):
                        raise ValueError(f"Geçersiz {key} değeri.")

                field_change = validate_update_field_change(
                    original_xml=original_xml,
                    modified_xml=modified_xml,
                    field_ref=metadata["field_ref"],
                    field_name=options["field_name"],
                    is_required=options["is_required"],
                    is_read_only=options["is_read_only"],
                    show_on_form=options["show_on_form"],
                    help_text=options["help_text"],
                )

                if field_change.get("success") is not True:
                    raise ValueError("Update XML doğrulaması başarısız.")

            elif operation == "remove":
                field_change = validate_remove_field_change(
                    original_xml=original_xml,
                    modified_xml=modified_xml,
                    field_ref=metadata["field_ref"],
                )

                if field_change.get("success") is not True:
                    raise ValueError(
                        field_change.get(
                            "message", "Remove XML güvenlik doğrulaması başarısız."
                        )
                    )
            elif operation == "manual_edit":
                field_change = validate_manual_xml_change(
                    original_xml=original_xml,
                    modified_xml=modified_xml,
                )

                if (
                    field_change.get("success") is not True
                    or field_change.get("operation") != "add"
                    or not isinstance(field_change.get("field_ref"), str)
                    or not field_change["field_ref"].strip()
                ):
                    raise ValueError(
                        field_change.get(
                            "message",
                            "Manual XML Add güvenlik doğrulaması başarısız.",
                        )
                    )

                logger.info(
                    "MANUAL APPLY VALIDATION | preview=%s | field=%s",
                    request.preview_id,
                    field_change["field_ref"],
                )
            else:
                raise ValueError("Desteklenmeyen işlem.")

        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Field değişikliği doğrulanamadı: {exc}",
            )
        # Update işleminde alan adı değişikliğini tespit et
        name_change = None

        if operation == "update":
            try:
                name_change = detect_field_name_change(
                    original_xml,
                    modified_xml,
                    metadata["field_ref"],
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Alan adı değişikliği doğrulanamadı: {exc}",
                )
        if name_change is not None and name_change["changed"]:
            logger.info(
                "Alan adı değişikliği tespit edildi: %s -> %s (refname: %s)",
                name_change["old_name"],
                name_change["new_name"],
                name_change["field_ref"],
            )
        # Sunucunun Preview sonrasında değişmediğini kontrol et
        session = create_winrm_session()

        current_xml = get_project_xml(
            session,
            collection_name,
            project_name,
            work_item_type,
        )

        if name_change is not None and name_change["changed"]:

            server_field = get_server_field_info(
                session,
                collection_name,
                name_change["field_ref"],
            )

            if server_field["name"] != name_change["old_name"]:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Alan adı Preview oluşturulduktan sonra değişmiş. "
                        f"Beklenen: {name_change['old_name']}, "
                        f"Sunucudaki: {server_field['name']}. "
                        "Yeni Preview oluşturmalısın."
                    ),
                )

            # changefield collection düzeyindedir: beklenmeyen kullanımlarda dur.
            expected_use = f"{project_name} ({work_item_type})"
            actual_uses = server_field["uses"]

            if actual_uses != [expected_use]:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Alan adı değişikliği durduruldu: kullanım kapsamı "
                        "beklenen tek Work Item Type ile eşleşmiyor. "
                        f"Beklenen: {expected_use}. "
                        f"Sunucudaki kullanımlar: {actual_uses}"
                    ),
                )

        if hashlib.sha256(current_xml).hexdigest() != original_hash:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Sunucudaki XML preview sonrasında değişmiş. "
                    "Yeni preview oluşturmalısın."
                ),
            )
        # Import öncesi yedek oluştur
        backup = save_wit_backup(
            current_xml,
            collection_name,
            project_name,
            work_item_type,
            field_name_change=(
                name_change
                if name_change is not None and name_change["changed"]
                else None
            ),
        )

        write_json_atomic(
            applied_path,
            {
                "status": "import_started",
                "backup_id": backup["backup_id"],
            },
        )

        try:
            import_xml = modified_xml

            if name_change is not None and name_change["changed"]:
                import_root = ET.fromstring(modified_xml)

                matching_fields = [
                    field
                    for field in import_root.iter()
                    if field.tag.split("}")[-1] == "FIELD"
                    and field.get("refname") == name_change["field_ref"]
                ]

                if len(matching_fields) != 1:
                    raise RuntimeError("Import XML içinde hedef FIELD doğrulanamadı.")

                matching_fields[0].set("name", name_change["old_name"])

                import_xml = ET.tostring(import_root, encoding="utf-8")

            import_work_item_type(
                session,
                collection_name,
                project_name,
                import_xml,
            )
            if name_change is not None and name_change["changed"]:
                field_after_import = get_server_field_info(
                    session,
                    collection_name,
                    name_change["field_ref"],
                )

                if field_after_import["name"] not in (
                    name_change["old_name"],
                    name_change["new_name"],
                ):
                    raise RuntimeError(
                        "Import sonrasında alan adı beklenmeyen bir değere değişmiş. "
                        "Manuel inceleme gerekiyor."
                    )

                if field_after_import["uses"] != [f"{project_name} ({work_item_type})"]:
                    raise RuntimeError(
                        "Import sonrasında alanın kullanım kapsamı değişmiş. "
                        "Manuel inceleme gerekiyor."
                    )
                if field_after_import["name"] == name_change["old_name"]:
                    write_json_atomic(
                        applied_path,
                        {
                            "status": "field_name_change_started",
                            "backup_id": backup["backup_id"],
                            "operation": operation,
                            "field_ref": name_change["field_ref"],
                            "old_name": name_change["old_name"],
                            "new_name": name_change["new_name"],
                        },
                    )

                    change_field_name(
                        session,
                        collection_name,
                        name_change["field_ref"],
                        name_change["new_name"],
                    )

                # changefield sonrasında sunucudan tekrar doğrula.
                field_after_change = get_server_field_info(
                    session,
                    collection_name,
                    name_change["field_ref"],
                )

                if field_after_change["name"] != name_change["new_name"]:
                    raise RuntimeError(
                        "changefield sonrasında alan adı doğrulanamadı. "
                        "Manuel inceleme gerekiyor."
                    )

                if field_after_change["uses"] != [f"{project_name} ({work_item_type})"]:
                    raise RuntimeError(
                        "changefield sonrasında alanın kullanım kapsamı değişmiş. "
                        "Manuel inceleme gerekiyor."
                    )

            verified_xml = get_project_xml(
                session,
                collection_name,
                project_name,
                work_item_type,
            )

            verified_root = ET.fromstring(verified_xml)

            if operation == "manual_edit":
                verification_field_ref = field_change["field_ref"]
            else:
                verification_field_ref = metadata.get("field_ref")

            if verification_field_ref and operation in ("add", "update", "manual_edit"):
                xml_matches = normalize_wit_xml_after_import(
                    verified_root, verification_field_ref
                ) == normalize_wit_xml_after_import(
                    modified_root, verification_field_ref
                )
            else:
                xml_matches = normalize_wit_xml(verified_root) == normalize_wit_xml(
                    modified_root
                )

            if not xml_matches:
                raise RuntimeError("Import sonrası XML preview ile eşleşmedi.")

        except Exception as exc:
            logger.exception("Work Item Type import/doğrulama başarısız")

            try:
                update_wit_backup_status(
                    backup_id=backup["backup_id"],
                    status="needs_investigation",
                )
            except Exception:
                logger.exception(
                    "Backup investigation durumu kaydedilemedi: %s",
                    backup["backup_id"],
                )

            try:
                write_json_atomic(
                    applied_path,
                    {
                        "status": "needs_investigation",
                        "backup_id": backup["backup_id"],
                        "operation": operation,
                        "field_ref": metadata.get("field_ref"),
                        "field_name_change": name_change,
                        "error": str(exc),
                    },
                )

            except OSError:
                logger.exception("Import durum dosyası güncellenemedi")

            raise HTTPException(
                status_code=500,
                detail=(
                    "Import veya doğrulama başarısız. "
                    "Sunucu durumunu kontrol et. "
                    f"Backup: {backup['backup_path']}. "
                    f"Hata: {exc}"
                ),
            )

        try:
            write_json_atomic(
                applied_path,
                {
                    "status": "verified",
                    "backup_id": backup["backup_id"],
                },
            )

        except OSError as exc:
            logger.exception("Import doğrulandı fakat verified durumu kaydedilemedi")

            raise HTTPException(
                status_code=500,
                detail=(
                    "XML import edildi ve sunucuda doğrulandı, "
                    "ancak verified durumu kaydedilemedi. "
                    "Aynı importu tekrar deneme. "
                    "Sunucu ve applied.json durumunu kontrol et. "
                    f"Backup: {backup['backup_path']}. "
                    f"Hata: {exc}"
                ),
            )

        try:
            update_wit_backup_status(
                backup_id=backup["backup_id"],
                status="verified",
            )
        except Exception:
            logger.exception(
                "Import doğrulandı fakat backup metadata "
                "verified olarak güncellenemedi. Backup: %s",
                backup["backup_id"],
            )
        else:
            try:
                cleanup_result = cleanup_old_wit_backups(
                    collection_name=collection_name,
                    project_name=project_name,
                    work_item_type=work_item_type,
                    keep=3,
                    dry_run=True,
                )

                logger.info(
                    "BACKUP CLEANUP DRY RUN | project=%s | wit=%s | result=%s",
                    project_name,
                    work_item_type,
                    cleanup_result,
                )

            except Exception:
                logger.exception(
                    "Backup cleanup başarısız. "
                    "Doğrulanmış import sonucu etkilenmedi."
                )

        return {
            "success": True,
            "preview_id": request.preview_id,
            "collection_name": collection_name,
            "project_name": project_name,
            "work_item_type": work_item_type,
            "backup_id": backup["backup_id"],
            "backup_path": backup["backup_path"],
            "message": ("Work Item Type import edildi ve doğrulandı."),
        }


def detect_field_name_change(original_xml, modified_xml, field_ref):
    original_root = ET.fromstring(original_xml)
    modified_root = ET.fromstring(modified_xml)

    def find_field(root):
        matches = [
            element
            for element in root.iter()
            if element.tag.split("}")[-1] == "FIELD"
            and element.get("refname") == field_ref
        ]

        if len(matches) != 1:
            raise ValueError(f"Alan tam olarak bir kez bulunmalı: {field_ref}")

        return matches[0]

    original_field = find_field(original_root)
    modified_field = find_field(modified_root)

    old_name = original_field.get("name")
    new_name = modified_field.get("name")

    if not old_name or not new_name:
        raise ValueError("Alan adı boş olamaz.")

    return {
        "changed": old_name != new_name,
        "field_ref": field_ref,
        "old_name": old_name,
        "new_name": new_name,
    }


def normalize_wit_xml(element):
    tag = element.tag.split("}")[-1]

    children = [normalize_wit_xml(child) for child in element]

    if tag == "FIELD":
        positions = [
            i
            for i, child in enumerate(element)
            if child.tag.split("}")[-1] in {"DEFAULT", "ALLOWEDVALUES"}
        ]

        reordered = sorted((children[i] for i in positions), key=repr)

        for i, normalized_child in zip(positions, reordered):
            children[i] = normalized_child
    if tag == "STATES":
        children = sorted(children, key=lambda child: dict(child[1]).get("value", ""))
    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        (element.text or "").strip(),
        tuple(children),
    )


def normalize_wit_xml_after_import(
    element,
    field_ref,
    in_web_layout=False,
):
    tag = element.tag.split("}")[-1]

    in_web_layout = in_web_layout or tag == "WebLayout"

    attributes = dict(element.attrib)

    if (
        in_web_layout
        and tag == "Control"
        and attributes.get("FieldName") == field_ref
        and attributes.get("Type") == "FieldControl"
        and attributes.get("LabelPosition", "Left") == "Left"
    ):
        attributes["LabelPosition"] = "Left"

    children = [
        normalize_wit_xml_after_import(
            child,
            field_ref,
            in_web_layout,
        )
        for child in element
    ]

    if tag == "FIELD":
        positions = [
            i
            for i, child in enumerate(element)
            if child.tag.split("}")[-1] in {"DEFAULT", "ALLOWEDVALUES"}
        ]

        reordered = sorted(
            (children[i] for i in positions),
            key=repr,
        )

        for i, normalized_child in zip(positions, reordered):
            children[i] = normalized_child

    if tag == "STATES":
        children = sorted(
            children,
            key=lambda child: dict(child[1]).get("value", ""),
        )

    return (
        element.tag,
        tuple(sorted(attributes.items())),
        (element.text or "").strip(),
        tuple(children),
    )


@app.get("/previews/{preview_id}/diff")
def get_preview_diff(preview_id: str):

    if not re.fullmatch(r"[0-9a-f]{32}", preview_id):
        raise HTTPException(status_code=400, detail="Geçersiz preview ID.")

    preview_dir = Path("previews") / "work-item-types" / preview_id

    metadata_path = preview_dir / "metadata.json"
    original_path = preview_dir / "original.xml"
    modified_path = preview_dir / "preview.xml"

    if not all(
        path.is_file() for path in [metadata_path, original_path, modified_path]
    ):
        raise HTTPException(status_code=404, detail="Preview dosyaları bulunamadı.")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        original_bytes = original_path.read_bytes()
        modified_bytes = modified_path.read_bytes()

        if metadata.get("preview_id") != preview_id:
            raise HTTPException(status_code=409, detail="Preview bilgileri eşleşmiyor.")

        if hashlib.sha256(original_bytes).hexdigest() != metadata.get(
            "original_sha256"
        ) or hashlib.sha256(modified_bytes).hexdigest() != metadata.get(
            "preview_sha256"
        ):
            raise HTTPException(
                status_code=409, detail="XML dosyalarının bütünlüğü doğrulanamadı."
            )

        def normalize_xml(xml_bytes):
            root = ET.fromstring(xml_bytes)

            ET.indent(root, space="  ")

            return ET.tostring(root, encoding="unicode").splitlines()

        original = normalize_xml(original_bytes)
        modified = normalize_xml(modified_bytes)

        matcher = difflib.SequenceMatcher(None, original, modified, autojunk=False)

        changes = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            changes.append(
                {
                    "type": tag,
                    "original_start": i1 + 1,
                    "modified_start": j1 + 1,
                    "original_lines": original[i1:i2],
                    "modified_lines": modified[j1:j2],
                }
            )

        return {
            "preview_id": preview_id,
            "project_name": metadata.get("project_name"),
            "original_lines": len(original),
            "modified_lines": len(modified),
            "original_xml": original_bytes.decode("utf-8-sig"),
            "modified_xml": modified_bytes.decode("utf-8-sig"),
            "changes": changes,
        }

    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="XML UTF-8 olarak okunamadı.")
    except (OSError, ValueError):
        raise HTTPException(
            status_code=500, detail="XML karşılaştırması oluşturulamadı."
        )


@app.post("/previews/{preview_id}/manual-edit")
def save_manual_xml_edit(preview_id: str, request: ManualXmlEditRequest):

    if not re.fullmatch(r"[0-9a-f]{32}", preview_id):
        raise HTTPException(status_code=400, detail="Geçersiz preview ID.")

    preview_dir = Path("previews") / "work-item-types" / preview_id

    metadata_path = preview_dir / "metadata.json"
    original_path = preview_dir / "original.xml"
    modified_path = preview_dir / "preview.xml"

    if not all(
        path.is_file() for path in (metadata_path, original_path, modified_path)
    ):
        raise HTTPException(
            status_code=404,
            detail="Kaynak Preview dosyaları bulunamadı.",
        )

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        original_xml = original_path.read_bytes()
        previous_xml = modified_path.read_bytes()
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Preview okunamadı: {exc}",
        )

    if not isinstance(metadata, dict) or metadata.get("preview_id") != preview_id:
        raise HTTPException(
            status_code=409,
            detail="Preview metadata uyuşmuyor.",
        )

    if hashlib.sha256(original_xml).hexdigest() != metadata.get(
        "original_sha256"
    ) or hashlib.sha256(previous_xml).hexdigest() != metadata.get("preview_sha256"):
        raise HTTPException(
            status_code=409,
            detail="Kaynak Preview bütünlüğü doğrulanamadı.",
        )

    try:
        edited_xml = request.modified_xml.encode("utf-8")
        edited_root = ET.fromstring(edited_xml)
        original_root = ET.fromstring(original_xml)
    except (UnicodeError, ET.ParseError):
        raise HTTPException(
            status_code=422,
            detail="Düzenlenen XML biçimi geçersiz.",
        )

    if (
        edited_root.tag.split("}")[-1] != "WITD"
        or original_root.tag.split("}")[-1] != "WITD"
    ):
        raise HTTPException(
            status_code=422,
            detail="XML kök elementi WITD olmalıdır.",
        )

    expected_wit = metadata.get("work_item_type")

    def get_wit_name(root):
        return next(
            (
                element.get("name")
                for element in root.iter()
                if element.tag.split("}")[-1] == "WORKITEMTYPE"
            ),
            None,
        )

    if (
        not isinstance(expected_wit, str)
        or get_wit_name(original_root) != expected_wit
        or get_wit_name(edited_root) != expected_wit
    ):
        raise HTTPException(
            status_code=422,
            detail="Work Item Type adı değiştirilemez.",
        )

    if original_xml == edited_xml:
        raise HTTPException(
            status_code=422,
            detail="XML üzerinde değişiklik bulunamadı.",
        )
    try:
        changes = detect_xml_changes(original_xml, edited_xml)

        logger.info("MANUAL EDIT CHANGES: %s", changes)

        logger.info(
            "MANUAL EDIT matches existing preview: %s",
            edited_xml == previous_xml,
        )

        logger.info(
            "MANUAL EDIT normalized match: %s",
            normalize_wit_xml(ET.fromstring(edited_xml))
            == normalize_wit_xml(ET.fromstring(previous_xml)),
        )
        validation = validate_manual_xml_change(
            original_xml,
            edited_xml,
        )
    except (ValueError, ET.ParseError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Manual XML doğrulaması başarısız: {exc}",
        )

    if validation.get("success") is not True:
        raise HTTPException(
            status_code=422,
            detail=validation.get(
                "message",
                "Manual XML değişikliği desteklenmiyor.",
            ),
        )

    try:
        new_preview = save_wit_preview(
            original_xml=original_xml,
            preview_xml=edited_xml,
            collection_name=metadata["collection_name"],
            project_name=metadata["project_name"],
            work_item_type=expected_wit,
            operation="manual_edit",
            field_ref="",
        )
    except (ValueError, KeyError, ET.ParseError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Manuel XML Preview oluşturulamadı: {exc}",
        )

    return {
        "success": True,
        "preview_id": new_preview["preview_id"],
        "operation": "manual_edit",
        "message": "XML doğrulandı ve yeni Preview oluşturuldu. Import yapılmadı.",
    }


def detect_xml_changes(original_xml: bytes, modified_xml: bytes):
    original_root = ET.fromstring(original_xml)
    modified_root = ET.fromstring(modified_xml)

    def extract_fields(root):
        fields = {}

        fields_node = root.find("./WORKITEMTYPE/FIELDS")
        if fields_node is None:
            raise ValueError("FIELDS bölümü bulunamadı.")

        for field in fields_node.findall("FIELD"):
            refname = field.get("refname")

            if not refname:
                raise ValueError("refname olmayan FIELD bulundu.")

            if refname in fields:
                raise ValueError(f"Tekrarlanan FIELD: {refname}")

            fields[refname] = normalize_wit_xml(field)

        return fields

    original_fields = extract_fields(original_root)
    modified_fields = extract_fields(modified_root)

    original_refs = set(original_fields)
    modified_refs = set(modified_fields)

    added_fields = sorted(modified_refs - original_refs)
    removed_fields = sorted(original_refs - modified_refs)

    updated_fields = sorted(
        ref
        for ref in original_refs & modified_refs
        if original_fields[ref] != modified_fields[ref]
    )

    def section_changed(section):
        original_section = original_root.find(f"./WORKITEMTYPE/{section}")
        modified_section = modified_root.find(f"./WORKITEMTYPE/{section}")

        if original_section is None and modified_section is None:
            return False

        if original_section is None or modified_section is None:
            return True

        return normalize_wit_xml(original_section) != normalize_wit_xml(
            modified_section
        )

    def without_managed_sections(root):
        import copy

        cloned_root = copy.deepcopy(root)
        wit = cloned_root.find("WORKITEMTYPE")

        if wit is None:
            raise ValueError("WORKITEMTYPE bölümü bulunamadı.")

        for child in list(wit):
            if child.tag.split("}")[-1] in {"FIELDS", "FORM", "WORKFLOW"}:
                wit.remove(child)

        return normalize_wit_xml(cloned_root)

    other_changes = without_managed_sections(original_root) != without_managed_sections(
        modified_root
    )

    return {
        "added_fields": added_fields,
        "removed_fields": removed_fields,
        "updated_fields": updated_fields,
        "form_changed": section_changed("FORM"),
        "workflow_changed": section_changed("WORKFLOW"),
        "other_changes": other_changes,
    }


def validate_manual_xml_change(original_xml: bytes, modified_xml: bytes):
    changes = detect_xml_changes(original_xml, modified_xml)

    # İlk aşamada yalnızca tek FIELD ekleme işlemini destekliyoruz.
    is_single_add = (
        len(changes["added_fields"]) == 1
        and not changes["removed_fields"]
        and not changes["updated_fields"]
        and not changes["workflow_changed"]
        and not changes["other_changes"]
    )

    if not is_single_add:
        return {
            "success": False,
            "operation": "unsupported",
            "changes": changes,
            "message": (
                "XML değişiklikleri tespit edildi ancak bu değişiklik "
                "kombinasyonu henüz güvenli Apply için desteklenmiyor."
            ),
        }

    try:
        validation = validate_add_field_change(
            original_xml,
            modified_xml,
        )
    except (ValueError, ET.ParseError) as exc:
        return {
            "success": False,
            "operation": "add",
            "changes": changes,
            "message": str(exc),
        }

    if validation.get("success") is not True:
        return {
            "success": False,
            "operation": "add",
            "changes": changes,
            "message": "Add doğrulaması başarısız.",
        }

    if validation.get("added_field_ref") != changes["added_fields"][0]:
        return {
            "success": False,
            "operation": "add",
            "changes": changes,
            "message": "Eklenen field referansı doğrulanamadı.",
        }

    return {
        "success": True,
        "operation": "add",
        "changes": changes,
        "field_ref": validation["added_field_ref"],
        "message": "Manual XML Add doğrulaması başarılı.",
    }


@app.post("/multi-projects/preview-field")
def preview_multi_project_fields(request: MultiProjectFieldRequest):

    if request.operation not in {"add", "remove", "update"}:
        raise HTTPException(
            status_code=400,
            detail="Operation yalnızca add, remove veya update olabilir.",
        )

    if request.operation == "add" and (
        not request.field_name or not request.field_type
    ):
        raise HTTPException(
            status_code=400,
            detail="Alan eklemek için field_name ve field_type gerekli.",
        )

    if len(request.project_names) != len(set(request.project_names)):
        raise HTTPException(
            status_code=400, detail="Aynı proje birden fazla seçilemez."
        )

    results = []

    for project_name in request.project_names:
        try:
            if request.operation == "add":
                field_request = AddFieldRequest(
                    collection_name=request.collection_name,
                    project_name=project_name,
                    work_item_type=request.work_item_type,
                    field_name=request.field_name,
                    field_ref=request.field_ref,
                    field_type=request.field_type,
                    is_required=request.is_required,
                    is_read_only=request.is_read_only,
                    show_on_form=request.show_on_form,
                    help_text=request.help_text,
                )

                result = preview_add_field(field_request)
            elif request.operation == "update":
                field_request = UpdateFieldRequest(
                    collection_name=request.collection_name,
                    project_name=project_name,
                    work_item_type=request.work_item_type,
                    field_ref=request.field_ref,
                    field_name=request.field_name,
                    is_required=request.is_required,
                    is_read_only=request.is_read_only,
                    show_on_form=request.show_on_form,
                    help_text=request.help_text,
                )

                result = preview_update_field(field_request)

            else:
                field_request = RemoveFieldRequest(
                    collection_name=request.collection_name,
                    project_name=project_name,
                    work_item_type=request.work_item_type,
                    field_ref=request.field_ref,
                )

                result = preview_remove_field(field_request)

            results.append(
                {
                    "project_name": project_name,
                    "success": result.get("success", False),
                    "preview_id": result.get("preview_id"),
                    "message": result.get("message", "Önizleme işlemi tamamlandı."),
                }
            )

        except HTTPException as error:
            results.append(
                {
                    "project_name": project_name,
                    "success": False,
                    "message": error.detail,
                }
            )

        except Exception:
            logger.exception("Project önizlemesi başarısız: %s", project_name)
            results.append(
                {
                    "project_name": project_name,
                    "success": False,
                    "message": "Bu proje için önizleme oluşturulamadı.",
                }
            )

    return {
        "operation": request.operation,
        "collection_name": request.collection_name,
        "total_projects": len(request.project_names),
        "results": results,
    }


@app.post("/multi-projects/check-apply")
def check_multi_project_apply(request: MultiProjectApplyRequest):
    print("CHECK APPLY PREVIEW IDS:", request.preview_ids, flush=True)
    if not request.preview_ids:
        raise HTTPException(
            status_code=400, detail="Kontrol edilecek preview bulunamadı."
        )
    if not request.confirm:
        raise HTTPException(status_code=400, detail="İşlem için açık onay gerekli.")

    if len(request.preview_ids) != len(set(request.preview_ids)):
        raise HTTPException(
            status_code=400, detail="Aynı preview birden fazla seçilemez."
        )

    results = []

    for preview_id in request.preview_ids:

        if not re.fullmatch(r"[0-9a-f]{32}", preview_id):
            results.append(
                {
                    "preview_id": preview_id,
                    "ready": False,
                    "message": "Geçersiz preview ID.",
                }
            )
            continue

        preview_dir = Path("previews") / "work-item-types" / preview_id
        metadata_path = preview_dir / "metadata.json"
        original_path = preview_dir / "original.xml"
        modified_path = preview_dir / "preview.xml"
        applied_path = preview_dir / "applied.json"

        if applied_path.exists():
            results.append(
                {
                    "preview_id": preview_id,
                    "ready": False,
                    "message": "Bu preview daha önce uygulanmış veya import başlatılmış.",
                }
            )
            continue

        if not all(
            path.is_file() for path in (metadata_path, original_path, modified_path)
        ):
            results.append(
                {
                    "preview_id": preview_id,
                    "ready": False,
                    "message": "Preview dosyaları eksik.",
                }
            )
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            original_xml = original_path.read_bytes()
            modified_xml = modified_path.read_bytes()

            original_hash = hashlib.sha256(original_xml).hexdigest()
            modified_hash = hashlib.sha256(modified_xml).hexdigest()

            hashes_valid = original_hash == metadata.get(
                "original_sha256"
            ) and modified_hash == metadata.get("preview_sha256")
            server_xml_valid = False
            if hashes_valid:
                try:
                    session = create_winrm_session()

                    current_xml = get_project_xml(
                        session,
                        metadata["collection_name"],
                        metadata["project_name"],
                        metadata["work_item_type"],
                    )

                    current_hash = hashlib.sha256(current_xml).hexdigest()

                    server_xml_valid = current_hash == original_hash

                except RuntimeError:
                    logger.exception("Sunucu XML kontrolü başarısız")
                    server_xml_valid = False

            preview_target_valid = all(
                isinstance(metadata.get(key), str) and bool(metadata[key].strip())
                for key in ("collection_name", "project_name", "work_item_type")
            )

            update_validation_valid = False
            remove_validation_valid = False
            manual_validation_valid = False

            if metadata.get("operation") == "manual_edit" and hashes_valid:
                try:
                    validation = validate_manual_xml_change(
                        original_xml=original_xml,
                        modified_xml=modified_xml,
                    )

                    manual_validation_valid = (
                        validation.get("success") is True
                        and validation.get("operation") == "add"
                        and isinstance(validation.get("field_ref"), str)
                        and bool(validation["field_ref"].strip())
                    )

                    logger.info(
                        "MANUAL CHECK VALIDATION | preview=%s | result=%s",
                        preview_id,
                        validation,
                    )

                except (ValueError, ET.ParseError, TypeError, KeyError):
                    logger.exception("Manual XML Check güvenlik doğrulaması başarısız")
            if metadata.get("operation") == "remove" and hashes_valid:
                try:
                    validation = validate_remove_field_change(
                        original_xml=original_xml,
                        modified_xml=modified_xml,
                        field_ref=metadata["field_ref"],
                    )

                    remove_validation_valid = validation.get("success") is True

                    logger.info(
                        "REMOVE VALIDATION | preview=%s | result=%s",
                        preview_id,
                        validation,
                    )

                except (ValueError, KeyError, TypeError):
                    logger.exception("Remove XML güvenlik doğrulaması başarısız")

            if metadata.get("operation") == "update" and hashes_valid:
                options = metadata.get("update_options")

                if (
                    isinstance(options, dict)
                    and set(options)
                    == {
                        "field_name",
                        "is_required",
                        "is_read_only",
                        "show_on_form",
                        "help_text",
                    }
                    and all(
                        options[key] is None or type(options[key]) is bool
                        for key in ("is_required", "is_read_only", "show_on_form")
                    )
                    and all(
                        options[key] is None or isinstance(options[key], str)
                        for key in ("field_name", "help_text")
                    )
                ):
                    try:
                        validation = validate_update_field_change(
                            original_xml=original_xml,
                            modified_xml=modified_xml,
                            field_ref=metadata["field_ref"],
                            field_name=options["field_name"],
                            is_required=options["is_required"],
                            is_read_only=options["is_read_only"],
                            show_on_form=options["show_on_form"],
                            help_text=options["help_text"],
                        )

                        update_validation_valid = validation.get("success") is True

                    except (ValueError, KeyError, TypeError):
                        logger.exception("Update XML güvenlik doğrulaması başarısız")

            operation = metadata.get("operation")

            allowed = (
                hashes_valid
                and server_xml_valid
                and metadata.get("preview_id") == preview_id
                and preview_target_valid
                and (
                    operation == "add"
                    or (operation == "update" and update_validation_valid)
                    or (operation == "remove" and remove_validation_valid)
                    or (operation == "manual_edit" and manual_validation_valid)
                )
            )
            operation = metadata.get("operation")
            if allowed and operation == "update":
                readiness_message = "Update işlemi için ön kontroller başarılı."

            elif allowed and operation == "add":
                readiness_message = "Add işlemi için ön kontroller başarılı."

            elif allowed and operation == "remove":
                readiness_message = "Remove işlemi için ön kontroller başarılı."
            elif allowed and operation == "manual_edit":
                readiness_message = "Manual XML Add işlemi için ön kontroller başarılı."

            elif operation == "manual_edit":
                readiness_message = "Manual XML güvenlik doğrulaması başarısız."
            elif operation == "remove":
                readiness_message = "Remove güvenlik doğrulaması başarısız."
            elif operation == "update":
                readiness_message = "Update güvenlik doğrulaması başarısız."

            else:
                readiness_message = (
                    "Preview bilgileri veya sunucudaki güncel XML doğrulanamadı."
                )
            results.append(
                {
                    "preview_id": preview_id,
                    "project_name": metadata.get("project_name"),
                    "ready": allowed,
                    "message": readiness_message,
                }
            )

        except (OSError, ValueError, KeyError):
            logger.exception("Preview ön kontrolü başarısız")

            results.append(
                {
                    "preview_id": preview_id,
                    "ready": False,
                    "message": "Preview dosyaları okunamadı veya doğrulanamadı.",
                }
            )

    return {
        "success": all(item["ready"] for item in results),
        "results": results,
        "message": "Yalnızca ön kontrol yapıldı. Import gerçekleştirilmedi.",
    }


@app.post("/multi-projects/apply")
def apply_multi_project_fields(request: MultiProjectApplyRequest):

    if not request.confirm:
        raise HTTPException(
            status_code=400, detail="Gerçek import için açık onay gerekli."
        )

    if len(request.preview_ids) != len(set(request.preview_ids)):
        raise HTTPException(
            status_code=400, detail="Aynı preview birden fazla seçilemez."
        )

    if not request.preview_ids:
        raise HTTPException(
            status_code=400, detail="Import için en az bir preview seçilmelidir."
        )
    # Import öncesi bütün projeleri kontrol et.
    preflight = check_multi_project_apply(request)

    if not preflight["success"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "En az bir proje Ready değil. "
                    "Hiçbir projeye import başlatılmadı."
                ),
                "results": preflight["results"],
            },
        )

    results = []

    for preview_id in request.preview_ids:

        try:
            result = apply_work_item_type(
                WorkItemApplyRequest(preview_id=preview_id, confirm=True)
            )

            results.append(
                {
                    "preview_id": preview_id,
                    "project_name": result["project_name"],
                    "success": True,
                    "backup_id": result["backup_id"],
                    "message": result["message"],
                }
            )

        except HTTPException as error:
            project_name = next(
                (
                    item.get("project_name")
                    for item in preflight["results"]
                    if item.get("preview_id") == preview_id
                ),
                None,
            )

            results.append(
                {
                    "preview_id": preview_id,
                    "project_name": project_name,
                    "success": False,
                    "message": error.detail,
                }
            )
        except Exception:
            logger.exception("Çoklu Apply başarısız: %s", preview_id)

            results.append(
                {
                    "preview_id": preview_id,
                    "success": False,
                    "message": "Beklenmeyen bir hata oluştu.",
                }
            )

    successful = sum(1 for item in results if item["success"])

    return {
        "success": successful == len(request.preview_ids),
        "total_projects": len(request.preview_ids),
        "successful": successful,
        "failed": len(request.preview_ids) - successful,
        "results": results,
    }


@app.get("/global-lists/previews/{preview_id}/diff")
def get_global_list_diff(preview_id: str):

    if not re.fullmatch(r"[0-9a-f]{32}", preview_id):
        raise HTTPException(status_code=400, detail="Invalid preview ID.")

    preview_dir = Path("previews") / "global-lists" / preview_id

    original_path = preview_dir / "original.xml"
    modified_path = preview_dir / "preview.xml"

    if not preview_dir.is_dir():
        raise HTTPException(status_code=404, detail="Preview not found.")

    if not original_path.is_file() or not modified_path.is_file():
        raise HTTPException(status_code=404, detail="Preview XML files not found.")

    try:
        original_xml = original_path.read_text(encoding="utf-8")
        modified_xml = modified_path.read_text(encoding="utf-8")

        def normalize_xml_for_diff(xml_text):
            root = ET.fromstring(xml_text)

            ET.indent(root, space="  ")

            return ET.tostring(
                root, encoding="unicode", xml_declaration=False
            ).splitlines()

        original_lines = normalize_xml_for_diff(original_xml)
        modified_lines = normalize_xml_for_diff(modified_xml)

        matcher = difflib.SequenceMatcher(
            None, original_lines, modified_lines, autojunk=False
        )

        changes = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():

            changes.append(
                {
                    "type": tag,
                    "original_lines": original_lines[i1:i2],
                    "modified_lines": modified_lines[j1:j2],
                }
            )

        return {"success": True, "preview_id": preview_id, "changes": changes}

    except OSError:
        logger.exception("GlobalList diff dosyaları okunamadı")

        raise HTTPException(
            status_code=500, detail="XML comparison could not be loaded."
        )


@app.post("/work-item-types/dry-run")
def dry_run_work_item_type(request: WorkItemDryRunRequest):
    preview_id = request.preview_id

    if not re.fullmatch(r"[0-9a-f]{32}", preview_id):
        raise HTTPException(status_code=400, detail="Geçersiz preview ID.")

    preview_dir = Path("previews") / "work-item-types" / preview_id

    metadata_path = preview_dir / "metadata.json"
    original_path = preview_dir / "original.xml"
    preview_path = preview_dir / "preview.xml"
    applied_path = preview_dir / "applied.json"

    if applied_path.exists():
        raise HTTPException(
            status_code=409, detail="Bu preview için import daha önce başlatılmış."
        )

    if not all(path.is_file() for path in (metadata_path, original_path, preview_path)):
        raise HTTPException(status_code=404, detail="Preview dosyaları eksik.")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    original_xml = original_path.read_bytes()
    preview_xml = preview_path.read_bytes()

    if metadata.get("preview_id") != preview_id:
        raise HTTPException(status_code=409, detail="Preview ID uyuşmuyor.")

    if not all(
        isinstance(metadata.get(key), str) and metadata[key].strip()
        for key in ("collection_name", "project_name", "work_item_type")
    ) or metadata.get("operation") not in {"add", "remove"}:
        raise HTTPException(
            status_code=403,
            detail="Dry Run için geçerli Collection, Project ve WIT bilgileri gerekli.",
        )

    if hashlib.sha256(original_xml).hexdigest() != metadata.get(
        "original_sha256"
    ) or hashlib.sha256(preview_xml).hexdigest() != metadata.get("preview_sha256"):
        raise HTTPException(
            status_code=409, detail="Preview dosyalarının SHA-256 değerleri uyuşmuyor."
        )

    preflight = check_multi_project_apply(
        MultiProjectApplyRequest(
            preview_ids=[preview_id],
            confirm=True,
        )
    )

    if not preflight["success"] or len(preflight["results"]) != 1:
        raise HTTPException(status_code=409, detail="Preflight Check başarısız.")

    session = create_winrm_session()

    result = import_work_item_type(
        session=session,
        collection_name=metadata["collection_name"],
        project_name=metadata["project_name"],
        xml_bytes=preview_xml,
        dry_run=True,
    )

    session = create_winrm_session()

    result = import_work_item_type(
        session=session,
        collection_name=metadata["collection_name"],
        project_name=metadata["project_name"],
        xml_bytes=preview_xml,
        dry_run=True,
    )

    return {
        "success": result["success"],
        "preview_id": preview_id,
        "message": result["message"],
        "import_performed": False,
    }


@app.get("/work-item-types/previews/{preview_id}/summary")
def get_wit_preview_summary(preview_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", preview_id):
        raise HTTPException(status_code=400, detail="Geçersiz preview ID.")

    folder = Path("previews") / "work-item-types" / preview_id

    metadata_path = folder / "metadata.json"
    original_path = folder / "original.xml"
    preview_path = folder / "preview.xml"

    if not all(path.is_file() for path in (metadata_path, original_path, preview_path)):
        raise HTTPException(status_code=404, detail="Preview dosyaları bulunamadı.")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        original_xml = original_path.read_bytes()
        preview_xml = preview_path.read_bytes()

        if metadata.get("preview_id") != preview_id:
            raise ValueError("Preview ID uyuşmuyor.")

        if hashlib.sha256(original_xml).hexdigest() != metadata.get(
            "original_sha256"
        ) or hashlib.sha256(preview_xml).hexdigest() != metadata.get("preview_sha256"):
            raise ValueError("Preview dosyalarının hash değeri uyuşmuyor.")

        operation = metadata.get("operation")
        field_ref = metadata.get("field_ref")

        if operation == "add":
            field_change = validate_add_field_change(
                original_xml,
                preview_xml,
            )

            summary_field_ref = field_change["added_field_ref"]
            summary_field_name = field_change["added_field_name"]

        elif operation == "update":
            update_options = metadata.get("update_options")

            if not isinstance(update_options, dict):
                raise ValueError("Update seçenekleri bulunamadı.")

            expected_keys = {
                "field_name",
                "is_required",
                "is_read_only",
                "show_on_form",
                "help_text",
            }

            if set(update_options) != expected_keys:
                raise ValueError("Update seçenekleri eksik veya geçersiz.")

            for key in ("is_required", "is_read_only", "show_on_form"):
                value = update_options[key]
                if value is not None and type(value) is not bool:
                    raise ValueError(f"{key} geçersiz.")

            for key in ("field_name", "help_text"):
                value = update_options[key]
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"{key} geçersiz.")

            field_change = validate_update_field_change(
                original_xml=original_xml,
                modified_xml=preview_xml,
                field_ref=field_ref,
                **update_options,
            )

            summary_field_ref = field_change["field_ref"]
            summary_field_name = field_change["new_name"]

        elif operation == "remove":
            if not isinstance(field_ref, str) or not field_ref.strip():
                raise ValueError("Remove için geçerli field_ref gerekli.")

            field_change = validate_remove_field_change(
                original_xml=original_xml,
                modified_xml=preview_xml,
                field_ref=field_ref,
            )

            if field_change.get("success") is not True:
                raise ValueError(
                    field_change.get("message", "Remove XML doğrulaması başarısız.")
                )

            summary_field_ref = field_ref

            original_root = ET.fromstring(original_xml)

            original_field = next(
                (
                    element
                    for element in original_root.iter()
                    if element.tag.split("}")[-1] == "FIELD"
                    and element.get("refname") == field_ref
                ),
                None,
            )

            if original_field is None:
                raise ValueError("Silinecek alan orijinal XML'de bulunamadı.")

            summary_field_name = original_field.get("name") or field_ref
        elif operation == "manual_edit":
            field_change = validate_manual_xml_change(
                original_xml=original_xml,
                modified_xml=preview_xml,
            )

            if (
                field_change.get("success") is not True
                or field_change.get("operation") != "add"
            ):
                raise ValueError(
                    "Manual XML yalnızca doğrulanmış Add işlemini destekliyor."
                )

            summary_field_ref = field_change.get("field_ref")

            if not isinstance(summary_field_ref, str) or not summary_field_ref.strip():
                raise ValueError("Manual XML field_ref doğrulanamadı.")

            modified_root = ET.fromstring(preview_xml)

            added_field = next(
                (
                    element
                    for element in modified_root.iter()
                    if element.tag.split("}")[-1] == "FIELD"
                    and element.get("refname") == summary_field_ref
                ),
                None,
            )

            if added_field is None:
                raise ValueError("Eklenen field XML içinde bulunamadı.")

            summary_field_name = added_field.get("name") or summary_field_ref
        else:
            raise ValueError("Desteklenmeyen işlem.")

        if operation != "manual_edit" and summary_field_ref != field_ref:
            raise ValueError("Metadata ve XML field bilgileri uyuşmuyor.")

    except (OSError, ValueError, ET.ParseError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=f"Preview doğrulanamadı: {exc}")

    return {
        "success": True,
        "preview_id": preview_id,
        "collection_name": metadata["collection_name"],
        "project_name": metadata["project_name"],
        "work_item_type": metadata["work_item_type"],
        "operation": metadata["operation"],
        "field_ref": summary_field_ref,
        "field_name": summary_field_name,
        "import_performed": False,
    }


@app.post("/github/pull-xml")
def github_pull(request: GitHubPullRequest):
    result = pull_xml_from_github(request.file_path, request.branch)
    return result


@app.put("/github/push-xml")
def github_push(request: GithubPushRequest):
    try:
        result = push_xml_to_github(
            request.file_path, request.branch, request.xml_content, request.sha
        )
        return result

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    except requests.exceptions.HTTPError as error:
        status = error.response.status_code if error.response is not None else 502

        raise HTTPException(
            status_code=status, detail="GitHub güncelleme işlemini reddetti."
        ) from error


@app.post("/github/backup-wit")
def github_backup_wit(request: GithubWitBackupRequest):
    try:
        # 1. Azure DevOps Server bağlantısı
        session = create_winrm_session()

        # 2. Güncel Work Item Type XML'ini export et
        xml_bytes = get_project_xml(
            session,
            request.collection_name,
            request.project_name,
            request.work_item_type,
        )

        xml_content = xml_bytes.decode("utf-8-sig")

        # 3. Her XML için sabit GitHub dosya yolu
        for name in (
            request.collection_name,
            request.project_name,
            request.work_item_type,
        ):
            if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", ".."):
                raise ValueError("Geçersiz XML yolu bileşeni.")

        file_path = (
            f"xml-definitions/"
            f"{request.collection_name}/"
            f"{request.project_name}/"
            f"{request.work_item_type}.xml"
        )

        # 4. GitHub'a yedekle
        result = push_xml_to_github(
            file_path=file_path,
            branch=request.branch,
            xml_content=xml_content,
            sha=None,
        )

        return {
            **result,
            "collection_name": request.collection_name,
            "project_name": request.project_name,
            "work_item_type": request.work_item_type,
            "file_path": file_path,
            "branch": request.branch,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except requests.exceptions.HTTPError as error:
        status = error.response.status_code if error.response is not None else 502
        raise HTTPException(
            status_code=status,
            detail="GitHub backup işlemi başarısız.",
        ) from error

    except (RuntimeError, UnicodeError, requests.exceptions.RequestException):
        logger.exception("GitHub WIT backup başarısız")
        raise HTTPException(
            status_code=502,
            detail="XML export veya GitHub bağlantısı başarısız.",
        )


@app.get("/github/xml-history")
def github_xml_history(file_path: str, branch: str):
    try:
        return get_xml_history(file_path, branch)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except requests.exceptions.HTTPError as error:
        status = error.response.status_code if error.response is not None else 502
        raise HTTPException(
            status_code=status,
            detail="GitHub XML history alınamadı.",
        ) from error

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail="GitHub bağlantısı başarısız.",
        ) from error


@app.get("/github/xml-commit-diff")
def github_xml_commit_diff(file_path: str, commit_sha: str):
    try:
        return get_xml_commit_diff(file_path, commit_sha)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except requests.exceptions.HTTPError as error:
        status = error.response.status_code if error.response is not None else 502
        raise HTTPException(
            status_code=status,
            detail="GitHub commit değişiklikleri alınamadı.",
        ) from error

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail="GitHub bağlantısı başarısız.",
        ) from error


@app.get("/github/xml-files")
def github_xml_files(branch: str):
    try:
        return list_github_xml_files(branch)

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub API request failed: {error}",
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


def ensure_github_wit_baseline(
    collection_name: str,
    project_name: str,
    work_item_type: str,
    current_xml: bytes,
):
    branch = get_github_backup_branch()

    for name in (collection_name, project_name, work_item_type):
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", ".."):
            raise ValueError("Geçersiz XML yolu bileşeni.")

    file_path = (
        f"xml-definitions/{collection_name}/" f"{project_name}/{work_item_type}.xml"
    )

    xml_content = current_xml.decode("utf-8-sig")

    try:
        existing = pull_xml_from_github(file_path, branch)

    except requests.exceptions.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise

        # Dosya yoksa mevcut sunucu XML'ini ilk sürüm olarak kaydet.
        result = push_xml_to_github(
            file_path=file_path,
            branch=branch,
            xml_content=xml_content,
        )

        return {
            "file_path": file_path,
            "branch": branch,
            "baseline_created": result["changed"],
            "sha": result["sha"],
        }

    if existing["xml_content"] != xml_content:
        raise ValueError(
            "GitHub'daki XML ile Azure DevOps'taki mevcut XML farklı. "
            "Otomatik Apply öncesinde sürümler uzlaştırılmalı."
        )

    return {
        "file_path": file_path,
        "branch": branch,
        "baseline_created": False,
        "sha": existing["sha"],
    }


