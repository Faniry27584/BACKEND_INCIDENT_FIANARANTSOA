from fastapi import APIRouter, HTTPException, status
from typing import List
from pydantic import BaseModel
from ..database.database import supabase

router = APIRouter()

class PosteSecuriteResponse(BaseModel):
    id: int
    nom_poste: str

@router.get("/", 
            response_model=List[PosteSecuriteResponse], 
            summary="Récupérer la liste des postes de sécurité")
def get_all_postes():
    """Endpoint pour lister tous les postes de sécurité disponibles."""
    try:
        response = supabase.table("postes_securite").select("id, nom_poste").execute()
        return response.data
    except Exception as e:
        print(f"Error fetching postes de securite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur est survenue lors de la récupération des postes."
        )
