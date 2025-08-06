# CHEMIN : backend/app/routers/authority.py
# Fichier complet et re-corrigé

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
from ..database.database import supabase
from ..utils.dependencies import role_checker
from ..schemas.incidents import IncidentResponse
from ..schemas.users import UserResponse
from ..utils.email_sender import send_assignment_to_security
from uuid import UUID
from datetime import datetime

router = APIRouter()
get_current_authority_user = role_checker("AUTORITE_LOCALE")

def log_status_change(incident_id: int, old_status: str, new_status: str, user_id: UUID):
    """Enregistre un changement de statut dans la table historiquestatuts."""
    try:
        supabase.table("historiquestatuts").insert({
            "incident_id": incident_id,
            "ancien_statut": old_status,
            "nouveau_statut": new_status,
            "modifie_par_id": str(user_id)
        }).execute()
    except Exception as e:
        print(f"ERROR logging status change for incident {incident_id}: {e}")

@router.get("/incidents/pending",
            response_model=List[IncidentResponse],
            summary="Lister les incidents en attente de validation")
def get_pending_incidents(current_user: UserResponse = Depends(get_current_authority_user)):
    try:
        query = "*, fokontany:fokontany_id(*), typesincident:type_id(*)"
        response = supabase.table("incidents").select(query).in_("statut", ["NOUVEAU", "URGENT"]).order("date_signalement", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# NOUVELLE ROUTE : Pour que l'Autorité Locale voie tous les incidents
@router.get("/incidents/all",
            response_model=List[IncidentResponse],
            summary="Lister tous les incidents du système pour l'Autorité Locale")
def get_all_incidents(current_user: UserResponse = Depends(get_current_authority_user)):
    """Permet à une autorité locale de voir tous les incidents de la base de données."""
    try:
        response = supabase.table("incidents").select(
            "*, fokontany:fokontany_id(*), typesincident:type_id(*)"
        ).order("date_signalement", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incidents/{incident_id}/validate",
             response_model=IncidentResponse,
             summary="Valider un incident")
def validate_incident(incident_id: int, current_user: UserResponse = Depends(get_current_authority_user)):
    try:
        incident_to_validate_res = supabase.table("incidents").select("statut").eq("id", incident_id).in_("statut", ["NOUVEAU", "URGENT"]).single().execute()
        if not incident_to_validate_res.data:
            raise HTTPException(status_code=404, detail="Incident non trouvé, déjà traité ou ne peut être validé.")
        
        old_status = incident_to_validate_res.data['statut']

        # FIX: Étape 1 - Mettre à jour le statut
        update_response = supabase.table("incidents").update({"statut": "VALIDE"}).eq("id", incident_id).execute()
        if not update_response.data:
            raise HTTPException(status_code=404, detail="La validation de l'incident a échoué.")
        
        # FIX: Étape 2 - Récupérer l'objet complet pour le retour
        response = supabase.table("incidents").select("*, fokontany:fokontany_id(*), typesincident:type_id(*)").eq("id", incident_id).single().execute()

        log_status_change(incident_id, old_status, "VALIDE", current_user.id)
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/incidents/{incident_id}/reject",
             response_model=IncidentResponse,
             summary="Rejeter un incident")
def reject_incident(incident_id: int, current_user: UserResponse = Depends(get_current_authority_user)):
    try:
        incident_to_reject_res = supabase.table("incidents").select("statut").eq("id", incident_id).in_("statut", ["NOUVEAU", "URGENT"]).single().execute()
        if not incident_to_reject_res.data:
            raise HTTPException(status_code=404, detail="Incident non trouvé, déjà traité ou ne peut être rejeté.")
        
        old_status = incident_to_reject_res.data['statut']

        # FIX: Étape 1 - Mettre à jour
        update_response = supabase.table("incidents").update({"statut": "REJETE"}).eq("id", incident_id).execute()
        if not update_response.data:
            raise HTTPException(status_code=404, detail="Le rejet de l'incident a échoué.")

        # FIX: Étape 2 - Récupérer l'objet complet
        response = supabase.table("incidents").select("*, fokontany:fokontany_id(*), typesincident:type_id(*)").eq("id", incident_id).single().execute()

        log_status_change(incident_id, old_status, "REJETE", current_user.id)
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/incidents/{incident_id}/assign/{agent_id}",
             response_model=IncidentResponse,
             summary="Assigner un incident à un agent")
def assign_incident(
    incident_id: int,
    agent_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_authority_user)
):
    try:
        incident_res = supabase.table("incidents").select("statut").eq("id", incident_id).single().execute()
        if not incident_res.data:
            raise HTTPException(status_code=404, detail="L'incident à assigner est introuvable.")
        
        current_status = incident_res.data['statut']
        if current_status not in ["NOUVEAU", "URGENT", "VALIDE"]:
            raise HTTPException(status_code=400, detail=f"Impossible d'assigner un incident avec le statut '{current_status}'.")

        update_data = {
            "statut": "ASSIGNE",
            "assigne_a_id": str(agent_id),
            "date_assignation": datetime.now().isoformat()
        }

        # FIX: Étape 1 - Mettre à jour l'incident
        update_response = supabase.table("incidents").update(update_data).eq("id", incident_id).execute()
        if not update_response.data:
            raise HTTPException(status_code=404, detail="Échec de l'assignation. L'incident n'a pas pu être mis à jour.")

        # FIX: Étape 2 - Récupérer l'incident mis à jour avec toutes ses données
        assign_response = supabase.table("incidents").select("*, typesincident(*), fokontany(*)").eq("id", incident_id).single().execute()
        if not assign_response.data:
             raise HTTPException(status_code=404, detail="Impossible de récupérer l'incident après l'assignation.")
        
        assigned_incident = assign_response.data
        
        log_status_change(incident_id, current_status, "ASSIGNE", current_user.id)

        agent_response = supabase.table("utilisateurs").select("email").eq("id", str(agent_id)).single().execute()
        if agent_response.data:
            agent_email = agent_response.data['email']
            background_tasks.add_task(
                send_assignment_to_security,
                agent_email=agent_email,
                incident_title=assigned_incident['titre'],
                incident_id=assigned_incident['id']
            )
            
        return assigned_incident
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))