from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from ..database.database import supabase
from ..utils.dependencies import get_current_admin_user
from ..schemas.users import UserResponse
from ..schemas.incident_types import IncidentTypeCreate, IncidentTypeUpdate, IncidentTypeResponse

router = APIRouter()

@router.get("/", 
            response_model=List[IncidentTypeResponse],
            summary="Lister tous les types d'incidents")
def get_all_incident_types(current_admin: UserResponse = Depends(get_current_admin_user)):
    """Récupère la liste complète des types d'incidents."""
    try:
        response = supabase.table("typesincident").select("*").order("nom_type").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/", 
             response_model=IncidentTypeResponse, 
             status_code=status.HTTP_201_CREATED,
             summary="Créer un nouveau type d'incident")
def create_incident_type(type_data: IncidentTypeCreate, current_admin: UserResponse = Depends(get_current_admin_user)):
    """Ajoute un nouveau type d'incident à la base de données."""
    try:
        response = supabase.table("typesincident").insert(type_data.model_dump()).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La création a échoué.")
        return response.data[0]
    except Exception as e:
        # Gère le cas où le nom du type existe déjà (contrainte UNIQUE)
        if "duplicate key value" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Le type d'incident '{type_data.nom_type}' existe déjà.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/{type_id}", 
            response_model=IncidentTypeResponse,
            summary="Mettre à jour un type d'incident")
def update_incident_type(type_id: int, type_update: IncidentTypeUpdate, current_admin: UserResponse = Depends(get_current_admin_user)):
    """Met à jour les informations d'un type d'incident existant."""
    update_data = type_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune donnée à mettre à jour.")
    try:
        response = supabase.table("typesincident").update(update_data).eq("id", type_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Type d'incident ID {type_id} non trouvé.")
        return response.data[0]
    except Exception as e:
        if "duplicate key value" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce nom de type d'incident est déjà utilisé.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{type_id}", 
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Supprimer un type d'incident")
def delete_incident_type(type_id: int, current_admin: UserResponse = Depends(get_current_admin_user)):
    """Supprime un type d'incident s'il n'est lié à aucun incident."""
    try:
        response = supabase.table("typesincident").delete().eq("id", type_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Type d'incident ID {type_id} non trouvé.")
    except Exception as e:
        # Gère l'erreur de contrainte de clé étrangère
        if "foreign key constraint" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, 
                detail="Impossible de supprimer ce type car il est déjà utilisé par un ou plusieurs incidents."
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
