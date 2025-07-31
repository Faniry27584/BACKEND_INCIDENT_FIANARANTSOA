# CHEMIN : backend/app/routers/security.py
# Fichier complet et re-corrigé

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from ..database.database import supabase
from ..utils.dependencies import role_checker
from ..schemas.incidents import IncidentResponse
from ..schemas.reports import ReportCreate, StatusUpdate, ReportResponse
from ..schemas.users import UserResponse
from uuid import UUID
from datetime import datetime

router = APIRouter()
get_current_security_user = role_checker("SECURITE_URBAINE")

# --- Helper function pour la traçabilité ---
def log_status_change(incident_id: int, old_status: str, new_status: str, user_id: UUID):
    try:
        supabase.table("historiquestatuts").insert({
            "incident_id": incident_id,
            "ancien_statut": old_status,
            "nouveau_statut": new_status,
            "modifie_par_id": str(user_id)
        }).execute()
    except Exception as e:
        print(f"ERROR logging status change for incident {incident_id}: {e}")

@router.get("/incidents/assigned",
            response_model=List[IncidentResponse],
            summary="Lister les incidents assignés à l'agent connecté")
def get_my_assigned_incidents(current_user: UserResponse = Depends(get_current_security_user)):
    try:
        response = supabase.table("incidents").select("*, fokontany:fokontany_id(*), typesincident:type_id(*)").eq("assigne_a_id", str(current_user.id)).order("date_assignation", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/incidents/{incident_id}/status",
             response_model=IncidentResponse,
             summary="Mettre à jour le statut d'un incident")
def update_incident_status(incident_id: int, status_update: StatusUpdate, current_user: UserResponse = Depends(get_current_security_user)):
    try:
        res = supabase.table("incidents").select("statut").eq("id", incident_id).eq("assigne_a_id", str(current_user.id)).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Incident non trouvé ou non assigné à cet agent.")
        
        incident_current_status = res.data['statut']
        new_status = status_update.nouveau_statut.upper()

        if new_status in ["RESOLU", "NON_RESOLU"]:
            report_res = supabase.table("rapportsintervention").select("id").eq("incident_id", incident_id).execute()
            if not report_res.data:
                raise HTTPException(status_code=403, detail="Un rapport d'intervention est requis avant de pouvoir clôturer cet incident.")
        
        update_data = {"statut": new_status}
        if new_status in ["RESOLU", "NON_RESOLU"]:
            update_data["date_resolution"] = datetime.now().isoformat()
        
        update_response = supabase.table("incidents").update(update_data).eq("id", incident_id).execute()
        if not update_response.data:
            raise HTTPException(status_code=500, detail="La mise à jour du statut a échoué.")
        
        response = supabase.table("incidents").select("*, fokontany:fokontany_id(*), typesincident:type_id(*)").eq("id", incident_id).single().execute()

        log_status_change(incident_id, incident_current_status, new_status, current_user.id)
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/incidents/{incident_id}/report",
             status_code=status.HTTP_201_CREATED,
             response_model=ReportResponse,
             summary="Soumettre un rapport d'intervention")
def submit_intervention_report(incident_id: int, report: ReportCreate, current_user: UserResponse = Depends(get_current_security_user)):
    res = supabase.table("incidents").select("id").eq("id", incident_id).eq("assigne_a_id", str(current_user.id)).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Incident non trouvé ou non assigné à cet agent.")

    report_res = supabase.table("rapportsintervention").select("id").eq("incident_id", incident_id).execute()
    if report_res.data:
        raise HTTPException(status_code=409, detail="Un rapport existe déjà pour cet incident.")

    try:
        report_data = {
            "contenu": report.contenu,
            "redige_par_id": str(current_user.id),
            "incident_id": incident_id
        }
        
        # FIX: Étape 1 - Insérer le rapport
        insert_response = supabase.table("rapportsintervention").insert(report_data).execute()
        if not insert_response.data:
            raise HTTPException(status_code=500, detail="Échec de la création du rapport (insertion).")

        new_report_id = insert_response.data[0]['id']

        # FIX: Étape 2 - Récupérer le rapport complet avec les données de l'incident pour le retour
        response = supabase.table("rapportsintervention").select("*, incident:incidents(id, titre)").eq("id", new_report_id).single().execute()
        if not response.data:
             raise HTTPException(status_code=500, detail="Échec de la récupération du rapport après création.")

        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/me",
            response_model=List[ReportResponse],
            summary="Lister tous les rapports rédigés par l'agent connecté")
def get_my_reports(current_user: UserResponse = Depends(get_current_security_user)):
    try:
        response = supabase.table("rapportsintervention").select(
            "id, contenu, date_rapport, incident:incidents(id, titre)"
        ).eq("redige_par_id", str(current_user.id)).order("date_rapport", desc=True).execute()
        
        return response.data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))