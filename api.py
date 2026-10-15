from fastapi import FastAPI,Request
from pydantic import BaseModel, Field , ConfigDict
import requests
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from datetime import date
from devops_backend import get_project_xml, list_xml_fields,create_winrm_session,analyze_field,get_collections,get_project,get_work_item_types,preview_hide_field
from fastapi import HTTPException
app= FastAPI()


@app.get("/health")
def get_health():
    return{
        "status": "ok"
    }

class AnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str= Field(min_length=1)
    work_item_type: str = Field(min_length=1)
    field_ref: str = Field(min_length=1)
    start_date: date | None = None

@app.get("/xml-fields")
def get_xml_fields(collection_name:str,project_name:str,work_item_type:str):
    create_session=create_winrm_session()
    try:
        xml_bytes = get_project_xml(
        create_session,
        collection_name,
        project_name,
        work_item_type
    )
        result = list_xml_fields(xml_bytes)
        return result
    
    except RuntimeError as error:
     if "TF201077" in str(error):
        raise HTTPException(
            status_code=404,
            detail="Belirtilen Work Item Type bulunamadı."
        ) from error
        
     
@app.get("/collections")
def take_collections():
    try: 
      collection = get_collections(
        )
      return collection
    except RuntimeError as error:
            raise HTTPException(
                status_code=500,
                detail="Belirtilen Collections bulunamadı."
            ) from error
import requests

@app.get("/projects")
def take_projects(collection_name: str):
    try:
        projects = get_project(collection_name)
        return projects

    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail="Azure DevOps Server'dan Project listesi alınamadı."
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail="Project listesi alınırken bir hata oluştu."
        ) from error
    
@app.get("/work_item_type")
def take_work_item_type(collection_name:str,project_name:str):
    try:
        wit_type=get_work_item_types(collection_name,project_name)
        return wit_type
    except requests.exceptions.HTTPError as error:
     if error.response is not None and error.response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Belirtilen proje bulunamadı."
        ) from error

     raise HTTPException(
        status_code=502,
        detail="Azure DevOps Server isteği başarısız oldu."
    ) from error
    except requests.exceptions.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail="Work item type belirlenemedi"
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail="Azure DevOps bağlantı yapılandırması eksik."
        ) from error
    
@app.post("/preview-hide-field")
def preview_hide_field_endpoint(
    collection_name: str,
    project_name: str,
    work_item_type: str,
    field_ref: str
):
    try:
        session = create_winrm_session()

        result = preview_hide_field(
            session=session,
            collection_name=collection_name,
            project_name=project_name,
            work_item_type=work_item_type,
            field_ref=field_ref
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.exception_handler(requests.exceptions.Timeout)
async def timeout_handler(request:Request,exc:requests.exceptions.Timeout):
    return JSONResponse(
        status_code=504,
        content={"detail": "Azure DevOps request timed out."}
    )
@app.exception_handler(requests.exceptions.HTTPError)
async def http_handler(request:Request,exc:requests.exceptions.HTTPError):
    return JSONResponse(
            status_code=502,
            content="Bad Gateway"
        )

@app.post("/analyses")
def build_analysis(request: AnalysisRequest):
        print("API'YE GELEN TARİH:", request.start_date, flush=True)
        result = analyze_field(
            request.work_item_type,
            request.field_ref,
            request.project_name,
            request.start_date
        )
        return result

