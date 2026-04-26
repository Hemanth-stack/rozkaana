from pydantic import BaseModel
from typing import Optional, List

class MenuResponse(BaseModel):
    id: str
    owner_id: str
    owner_type: str
    menu_date: str
    breakfast: Optional[dict]
    morning_snack: Optional[dict]
    lunch: Optional[dict]
    evening_snack: Optional[dict]
    dinner: Optional[dict]
    total_calories: int
    total_protein_g: float
    pdf_url: Optional[str]

class HistoryResponse(BaseModel):
    menus: List[MenuResponse]

class RegenerateResponse(BaseModel):
    task_id: str

class TaskStatusResponse(BaseModel):
    status: str
    menu: Optional[MenuResponse]

class OverrideCuisineRequest(BaseModel):
    cuisine: str

class PDFURLResponse(BaseModel):
    pdf_url: str