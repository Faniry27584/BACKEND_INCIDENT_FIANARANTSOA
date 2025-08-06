# Fichier complet : backend/app/schemas/incidents.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID

# --- Nouveaux Schémas de support pour le rapport ---
class PosteSecuriteInfo(BaseModel):
    nom_poste: str
    class Config:
        from_attributes = True

class ReportAuthorResponse(BaseModel):
    nom: str
    prenom: str
    postes_securite: Optional[PosteSecuriteInfo] = None
    class Config:
        from_attributes = True

class ReportDetailResponse(BaseModel):
    contenu: str
    date_rapport: datetime
    redige_par: ReportAuthorResponse
    class Config:
        from_attributes = True

# --- Schémas existants ---
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
    signale_par_id: UUID
    fokontany_id: int
    type_id: int
    assigne_a_id: Optional[UUID] = None
    date_assignation: Optional[datetime] = None
    date_resolution: Optional[datetime] = None
    fokontany: Optional[FokontanyResponse] = None
    typesincident: Optional[IncidentTypeResponse] = None
    class Config:
        from_attributes = True
        json_encoders = {UUID: str}

class SignaleParResponse(BaseModel):
    prenom: str
    nom: str

class AssigneAResponse(BaseModel):
    prenom: str
    nom: str

class IncidentDetailResponse(IncidentResponse):
    can_edit_delete: bool = False
    signale_par: SignaleParResponse
    assigne_a: Optional[AssigneAResponse] = None
    piecesjointes: List[PieceJointeResponse] = []
    # MISE À JOUR : Utilisation du nouveau schéma détaillé pour les rapports
    rapports_intervention: List[ReportDetailResponse] = []