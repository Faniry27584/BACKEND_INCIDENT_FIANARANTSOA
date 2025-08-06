from fastapi import APIRouter, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from ..database.database import supabase

router = APIRouter()

# CORRECTION : Le schéma de réponse correspond maintenant à la nouvelle structure de la base de données
class FokontanyResponse(BaseModel):
    id: int
    nom_fokontany: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius: Optional[float] = None

@router.get("/", 
            response_model=List[FokontanyResponse], 
            summary="Récupérer la liste de tous les fokontany")
def get_all_fokontany():
    """
    Endpoint pour lister tous les fokontany.
    """
    try:
        # CORRECTION : La requête sélectionne les nouvelles colonnes
        response = supabase.table("fokontany").select("id, nom_fokontany, latitude, longitude, radius").execute()
        if not response.data:
            return []
        return response.data
    except Exception as e:
        print(f"Error fetching fokontany: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur est survenue lors de la récupération des fokontany."
        )

@router.get("/{fokontany_id}",
            response_model=FokontanyResponse,
            summary="Récupérer les détails d'un Fokontany spécifique")
def get_fokontany_by_id(fokontany_id: int):
    """
    Retourne les détails complets d'un Fokontany, y compris ses coordonnées centrales et son rayon.
    """
    try:
        response = supabase.table("fokontany").select("*").eq("id", fokontany_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fokontany non trouvé.")
        return response.data
    except Exception as e:
        print(f"Error fetching fokontany by ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du Fokontany."
        )
