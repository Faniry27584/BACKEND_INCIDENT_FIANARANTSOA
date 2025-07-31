from pydantic import BaseModel, Field
from datetime import datetime

# Schéma pour la création d'un rapport d'intervention
class ReportCreate(BaseModel):
    contenu: str = Field(..., min_length=20, description="Description détaillée de l'intervention et des résultats.")

# Schéma pour la mise à jour du statut d'un incident
class StatusUpdate(BaseModel):
    nouveau_statut: str = Field(..., description="Le nouveau statut de l'incident (ex: EN_COURS, RESOLU)")

# --- NOUVEAU SCHÉMA POUR LA RÉPONSE DE L'API ---

class IncidentInfoForReport(BaseModel):
    """Sous-modèle pour les informations de l'incident lié au rapport."""
    id: int
    titre: str

class ReportResponse(BaseModel):
    """Définit la structure d'un rapport retourné par l'API."""
    id: int
    contenu: str
    date_rapport: datetime
    incident: IncidentInfoForReport

    class Config:
        from_attributes = True
