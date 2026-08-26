from pydantic import BaseModel
from typing import List

class AnalysisResponse(BaseModel):
    score: float
    matched_role: str
    alternative_roles: List[dict]
    improvements: List[dict]
    extracted_entities: dict

class HealthResponse(BaseModel):
    status: str
    version: str

class RoleResponse(BaseModel):
    roles: List[str]