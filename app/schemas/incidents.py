# CHEMIN : backend/app/schemas/incidents.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID

# --- Schémas de support ---

class IncidentTypeResponse(BaseModel):
    id: int
    nom_type: str
    categorie: str
    class Config:
        from_attributes = True

class FokontanyResponse(BaseModel):
    id: int
    nom_fokontany: str
    class Config:
        from_attributes = True

class PieceJointeResponse(BaseModel):
    id: int
    url_fichier: str
    type_fichier: str
    class Config:
        from_attributes = True

# --- Schémas d'incident ---

class IncidentCreate(BaseModel):
    titre: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10)
    latitude: float
    longitude: float
    adresse_approximative: Optional[str] = None
    type_id: int
    fokontany_id: int
    pieces_jointes_urls: Optional[List[str]] = []

class IncidentUpdate(BaseModel):
    titre: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=10)
    adresse_approximative: Optional[str] = None
    type_id: Optional[int] = None

class IncidentResponse(BaseModel):
    id: int
    titre: str
    description: str
    date_signalement: datetime
    latitude: float
    longitude: float
    adresse_approximative: Optional[str] = None
    statut: str
    signale_par_id: UUID  # <-- MODIFIÉ
    fokontany_id: int
    type_id: int
    assigne_a_id: Optional[UUID] = None  # <-- MODIFIÉ
    date_assignation: Optional[datetime] = None
    date_resolution: Optional[datetime] = None
    fokontany: Optional[FokontanyResponse] = None
    typesincident: Optional[IncidentTypeResponse] = None

    class Config:
        from_attributes = True
        json_encoders = {UUID: str}  # Assure la sérialisation correcte

class IncidentDetailResponse(IncidentResponse):
    can_edit_delete: bool = False
    fokontany: Optional[FokontanyResponse] = None
    typesincident: Optional[IncidentTypeResponse] = None
    piecesjointes: List[PieceJointeResponse] = []