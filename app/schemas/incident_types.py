from pydantic import BaseModel, Field
from typing import Optional

class IncidentTypeBase(BaseModel):
    """Schéma de base pour un type d'incident."""
    nom_type: str = Field(..., min_length=3, description="Le nom du type d'incident (ex: Vol à l'arraché)")
    categorie: str = Field(..., description="La catégorie principale (ex: SECURITE, INFRASTRUCTURE)")
    description: Optional[str] = Field(None, description="Description optionnelle du type d'incident")

class IncidentTypeCreate(IncidentTypeBase):
    """Schéma utilisé pour la création d'un nouveau type d'incident."""
    pass

class IncidentTypeUpdate(BaseModel):
    """Schéma pour la mise à jour, tous les champs sont optionnels."""
    nom_type: Optional[str] = Field(None, min_length=3)
    categorie: Optional[str] = None
    description: Optional[str] = None

class IncidentTypeResponse(IncidentTypeBase):
    """Schéma de réponse complet, incluant l'ID."""
    id: int

    class Config:
        from_attributes = True
