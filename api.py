from fastapi import FastAPI
from pydantic import BaseModel, Field , ConfigDict
from devops_backend import analyze_field
import requests
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

@app.post("/analyses")
def build_analysis(request: AnalysisRequest):
    try:
        result = analyze_field(
            request.work_item_type,
            request.field_ref,
            request.project_name
        )
        return result

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Azure DevOps request timed out."
        )
