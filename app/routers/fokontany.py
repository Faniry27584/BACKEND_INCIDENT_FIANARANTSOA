from fastapi import APIRouter, HTTPException, status
from typing import List
from ..database.database import supabase

# Création d'un router spécifique pour les fokontany
router = APIRouter()

# Définition d'un modèle simple pour la réponse
from pydantic import BaseModel

class FokontanyResponse(BaseModel):
    id: int
    nom_fokontany: str  # Corrigé pour correspondre au schéma SQL

@router.get("/", 
            response_model=List[FokontanyResponse], 
            summary="Récupérer la liste de tous les fokontany",
            description="Retourne un tableau de tous les fokontany avec leur ID et leur nom.")
def get_all_fokontany():
    """
    Endpoint pour lister tous les fokontany depuis la base de données Supabase.
    Cette route est publique et utilisée par le formulaire d'inscription.
    """
    # 1. Récupérer les données de la table fokontany
    try:
        response = supabase.table("fokontany").select("id, nom_fokontany").execute()
        
        # 2. Vérifier si la réponse contient des données
        if not response.data:
            return [] # Retourner une liste vide si la table est vide

        # 3. Retourner les données récupérées
        return response.data

    except Exception as e:
        # 4. Gérer les erreurs de connexion à la base de données ou autres problèmes
        print(f"Error fetching fokontany: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur est survenue lors de la récupération des fokontany."
        )