from fastapi import FastAPI,Request
from pydantic import BaseModel, Field , ConfigDict
import requests
from fastapi.responses import JSONResponse
from datetime import date
from devops_backend import get_project_xml, list_xml_fields,create_winrm_session,analyze_field
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
    xml_bytes = get_project_xml(
        create_session,
        collection_name,
        project_name,
        work_item_type
    )

    result = list_xml_fields(xml_bytes)
    return result

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
    