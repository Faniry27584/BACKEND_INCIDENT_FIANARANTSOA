from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class HistoryLogItem(BaseModel):
    """
    Représente une seule entrée dans le journal d'historique,
    enrichie avec des informations contextuelles.
    """
    id: int
    date_changement: datetime = Field(..., description="Date et heure de l'action")
    
    # Le titre de l'incident concerné
    incident_titre: str = Field(..., alias="incident_title") 

    # Le nom complet de l'utilisateur qui a fait l'action
    modifie_par_nom: str = Field(..., alias="modified_by_name")

    # La transition de statut
    ancien_statut: Optional[str] = Field(None, alias="old_status")
    nouveau_statut: str = Field(..., alias="new_status")

    class Config:
        from_attributes = True
        # alias_generator est utilisé pour que Pydantic puisse mapper
        # les noms de champs de la BDD vers nos noms de champs Python.
        populate_by_name = True
