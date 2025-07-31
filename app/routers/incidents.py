# CHEMIN : backend/app/routers/incidents.py
# Fichier complet et re-corrigé

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
from pydantic import BaseModel
from ..database.database import supabase
from ..utils.dependencies import get_current_user_data, role_checker
from ..schemas.incidents import (
    IncidentCreate,
    IncidentUpdate,
    IncidentResponse,
    IncidentDetailResponse,
    IncidentTypeResponse
)
from ..schemas.users import UserResponse
from ..utils.email_sender import send_new_incident_to_authorities, send_panic_alert_notification
from ..utils import socket_events

router = APIRouter()

get_current_fokontany_chief_user = role_checker("CHEF_FOKONTANY")

class PanicPayload(BaseModel):
    latitude: float
    longitude: float
    type_id: int
    fokontany_id: int

@router.get("/types", response_model=List[IncidentTypeResponse])
def get_incident_types():
    try:
        response = supabase.table("typesincident").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=IncidentResponse)
def create_incident(
    incident: IncidentCreate,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user_data)
):
    pieces_jointes_urls = incident.pieces_jointes_urls
    incident_dict = incident.model_dump(exclude={"pieces_jointes_urls"})
    incident_dict['signale_par_id'] = str(current_user.id)
    incident_dict['statut'] = 'NOUVEAU'

    try:
        response = supabase.table("incidents").insert(incident_dict).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="La création de l'incident a échoué.")
        
        created_incident = response.data[0]
        incident_id = created_incident['id']

        if pieces_jointes_urls:
            supabase.table("piecesjointes").insert([
                {"incident_id": incident_id, "url_fichier": url, "type_fichier": "image"}
                for url in pieces_jointes_urls
            ]).execute()

        authorities_response = supabase.table("utilisateurs").select("email").eq("role", "AUTORITE_LOCALE").eq("est_verifie", True).execute()
        if authorities_response.data:
            authority_emails = [user['email'] for user in authorities_response.data]
            background_tasks.add_task(
                send_new_incident_to_authorities,
                authority_emails=authority_emails,
                incident_title=created_incident['titre'],
                incident_id=incident_id,
                user_name=f"{current_user.prenom} {current_user.nom}",
                incident_description=created_incident['description']
            )

        enrich_query = supabase.table("incidents").select(
            "*, fokontany:fokontany_id(*), typesincident:type_id(*)"
        ).eq("id", incident_id).single().execute()
        
        return IncidentResponse(**enrich_query.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me", response_model=List[IncidentResponse])
def get_my_incidents(current_user: UserResponse = Depends(get_current_user_data)):
    try:
        response = supabase.table("incidents").select(
            "*, fokontany:fokontany_id(*), typesincident:type_id(*)"
        ).eq("signale_par_id", str(current_user.id)).order("date_signalement", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fokontany", response_model=List[IncidentResponse])
def get_incidents_for_fokontany(current_user: UserResponse = Depends(get_current_fokontany_chief_user)):
    if not current_user.fokontany_id:
        raise HTTPException(status_code=400, detail="Aucun Fokontany associé.")
    try:
        response = supabase.table("incidents").select(
            "*, fokontany:fokontany_id(*), typesincident:type_id(*)"
        ).eq("fokontany_id", current_user.fokontany_id).order("date_signalement", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident_by_id(incident_id: int, current_user: UserResponse = Depends(get_current_user_data)):
    try:
        query = supabase.table("incidents").select(
            "*, fokontany:fokontany_id(*), typesincident:type_id(*), piecesjointes(*)"
        ).eq("id", incident_id).single().execute()

        if not query.data:
            raise HTTPException(status_code=404, detail="Incident non trouvé")

        data = query.data
        # Vérifie si l'utilisateur est le signaleur
        is_owner = UUID(data["signale_par_id"]) == current_user.id
        # Vérifie si l'utilisateur est un chef Fokontany associé
        is_chief = (
            current_user.role == "CHEF_FOKONTANY" and 
            current_user.fokontany_id and 
            data["fokontany_id"] == current_user.fokontany_id
        )
        # can_edit_delete est true si l'utilisateur est soit le signaleur, soit le chef Fokontany
        data["can_edit_delete"] = is_owner or is_chief
        
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération de l'incident.")
    
@router.put("/{incident_id}", response_model=IncidentResponse)
def update_incident(incident_id: int, incident_update: IncidentUpdate, current_user: UserResponse = Depends(get_current_user_data)):
    existing_res = supabase.table("incidents").select("signale_par_id, fokontany_id").eq("id", incident_id).single().execute()
    if not existing_res.data:
        raise HTTPException(status_code=404, detail="Incident non trouvé.")
    
    data = existing_res.data
    is_owner = UUID(data["signale_par_id"]) == current_user.id
    is_chief = current_user.role == "CHEF_FOKONTANY" and data["fokontany_id"] == current_user.fokontany_id

    if not is_owner and not is_chief:
        raise HTTPException(status_code=403, detail="Action non autorisée.")

    update_data = incident_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour.")

    try:
        # FIX: Étape 1 - Mettre à jour
        update_response = supabase.table("incidents").update(update_data).eq("id", incident_id).execute()
        if not update_response.data:
            raise HTTPException(status_code=500, detail="Échec de la mise à jour.")
        
        # FIX: Étape 2 - Récupérer l'objet complet pour le retour
        response = supabase.table("incidents").select("*, fokontany:fokontany_id(*), typesincident:type_id(*)").eq("id", incident_id).single().execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{incident_id}", status_code=204)
def delete_incident(incident_id: int, current_user: UserResponse = Depends(get_current_user_data)):
    res = supabase.table("incidents").select("signale_par_id, fokontany_id").eq("id", incident_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Incident non trouvé.")
    
    data = res.data
    is_owner = UUID(data["signale_par_id"]) == current_user.id
    is_chief = current_user.role == "CHEF_FOKONTANY" and data["fokontany_id"] == current_user.fokontany_id

    if not is_owner and not is_chief:
        raise HTTPException(status_code=403, detail="Action non autorisée.")
    
    try:
        supabase.table("incidents").delete().eq("id", incident_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/panic", response_model=IncidentResponse)
def trigger_panic_mode(
    payload: PanicPayload,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user_data)
):
    if current_user.role not in ["CITOYEN", "CHEF_FOKONTANY"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé.")

    try:
        type_res = supabase.table("typesincident").select("*").eq("id", payload.type_id).single().execute()
        type_info = type_res.data or {"nom_type": "Type inconnu", "categorie": ""}
        fokontany_res = supabase.table("fokontany").select("*").eq("id", payload.fokontany_id).single().execute()
        fokontany_info = fokontany_res.data or {"nom_fokontany": "Fokontany inconnu"}

        panic_data = {
            "titre": f"URGENCE: {type_info['nom_type']}",
            "description": f"Activation du Mode danger par {current_user.prenom} {current_user.nom}.",
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "type_id": payload.type_id,
            "fokontany_id": payload.fokontany_id,
            "signale_par_id": str(current_user.id),
            "statut": "URGENT"
        }
        response = supabase.table("incidents").insert(panic_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Échec de la création.")

        incident = response.data[0]
        incident["typesincident"] = type_info
        incident["fokontany"] = fokontany_info

        background_tasks.add_task(socket_events.broadcast_panic_alert, incident_data=incident)

        notify_roles = ["AUTORITE_LOCALE", "SECURITE_URBAINE"]
        notify_users = supabase.table("utilisateurs").select("email").in_("role", notify_roles).eq("est_verifie", True).execute()
        if notify_users.data:
            emails = [u["email"] for u in notify_users.data]
            background_tasks.add_task(
                send_panic_alert_notification,
                emails=emails,
                incident_id=incident["id"],
                location={"lat": incident["latitude"], "lng": incident["longitude"]}
            )
        
        return incident
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))