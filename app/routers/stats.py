# Fichier complet : backend/app/routers/stats.py

from fastapi import APIRouter, Depends, HTTPException, status
from ..database.database import supabase
from ..schemas.users import UserResponse
from ..schemas.stats import FokontanyStatsResponse, StatItem, AuthorityKPIsResponse, GlobalStatsResponse
from datetime import datetime, timedelta
from ..utils.dependencies import role_checker
from typing import List
from collections import Counter

router = APIRouter()

get_current_fokontany_chief_user = role_checker("CHEF_FOKONTANY")
get_current_authority_user = role_checker("AUTORITE_LOCALE")
# NOUVEAU : Dépendance pour l'agent de sécurité
get_current_security_user = role_checker("SECURITE_URBAINE")

@router.get("/fokontany",
            response_model=FokontanyStatsResponse,
            summary="Récupérer les statistiques pour le Fokontany du chef connecté")
def get_stats_for_fokontany(current_user: UserResponse = Depends(get_current_fokontany_chief_user)):
    if not current_user.fokontany_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun Fokontany n'est associé à ce compte."
        )
    try:
        incidents_response = supabase.table("incidents").select(
            "statut, typesincident(nom_type)"
        ).eq("fokontany_id", current_user.fokontany_id).execute()

        if not incidents_response.data:
            return FokontanyStatsResponse(incidents_par_statut=[], incidents_par_type=[])

        incidents = incidents_response.data
        stats_by_status = Counter(incident['statut'] for incident in incidents)
        stats_by_type = Counter(
            incident['typesincident']['nom_type'] for incident in incidents if incident.get('typesincident')
        )
        
        return FokontanyStatsResponse(
            incidents_par_statut=[StatItem(label=k, value=v) for k, v in stats_by_status.items()],
            incidents_par_type=[StatItem(label=k, value=v) for k, v in stats_by_type.items()]
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/authority-kpis",
            response_model=AuthorityKPIsResponse,
            summary="Récupérer les KPIs pour l'Autorité Locale")
def get_kpis_for_authority(current_user: UserResponse = Depends(get_current_authority_user)):
    try:
        pending_incidents_res = supabase.table("incidents").select("id", count='exact').in_("statut", ["NOUVEAU", "URGENT"]).execute()
        incidents_a_valider = pending_incidents_res.count or 0
        
        active_agents_res = supabase.table("utilisateurs").select("id", count='exact').eq("role", "SECURITE_URBAINE").eq("est_verifie", True).execute()
        agents_actifs = active_agents_res.count or 0

        resolved_incidents_res = supabase.table("incidents").select("date_signalement, date_resolution").eq("statut", "RESOLU").not_.is_("date_resolution", "null").execute()
        temps_resolution_moyen_heures = None
        if resolved_incidents_res.data:
            total_duration_seconds = sum(
                (datetime.fromisoformat(inc['date_resolution']) - datetime.fromisoformat(inc['date_signalement'])).total_seconds()
                for inc in resolved_incidents_res.data
            )
            count_resolved = len(resolved_incidents_res.data)
            if count_resolved > 0:
                temps_resolution_moyen_heures = round((total_duration_seconds / count_resolved) / 3600, 2)
        
        return AuthorityKPIsResponse(
            incidents_a_valider=incidents_a_valider,
            agents_actifs=agents_actifs,
            temps_resolution_moyen_heures=temps_resolution_moyen_heures
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/global",
            response_model=GlobalStatsResponse,
            summary="Récupérer les statistiques globales pour toute la commune")
def get_global_stats(current_user: UserResponse = Depends(get_current_authority_user)):
    try:
        incidents_res = supabase.table("incidents").select(
            "statut, typesincident(nom_type), fokontany(nom_fokontany)"
        ).execute()
        
        incidents = incidents_res.data
        if not incidents:
            return GlobalStatsResponse(incidents_par_statut=[], incidents_par_type=[], incidents_par_fokontany=[])
            
        status_counts = Counter(inc['statut'] for inc in incidents)
        type_counts = Counter(inc['typesincident']['nom_type'] for inc in incidents if inc.get('typesincident'))
        fokontany_counts = Counter(inc['fokontany']['nom_fokontany'] for inc in incidents if inc.get('fokontany'))
        
        return GlobalStatsResponse(
            incidents_par_statut=[StatItem(label=k, value=v) for k, v in status_counts.items()],
            incidents_par_type=[StatItem(label=k, value=v) for k, v in type_counts.items()],
            incidents_par_fokontany=[StatItem(label=k, value=v) for k, v in fokontany_counts.items()]
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# NOUVELLE ROUTE : Statistiques pour l'agent de sécurité
@router.get("/security/me",
            response_model=FokontanyStatsResponse, # On réutilise ce schéma car il correspond aux besoins
            summary="Récupérer les statistiques des missions de l'agent connecté")
def get_stats_for_security_agent(current_user: UserResponse = Depends(get_current_security_user)):
    """
    Calcule et retourne les statistiques (par statut et par type)
    pour tous les incidents assignés à l'agent de sécurité connecté.
    """
    try:
        incidents_response = supabase.table("incidents").select(
            "statut, typesincident(nom_type)"
        ).eq("assigne_a_id", str(current_user.id)).execute()

        if not incidents_response.data:
            return FokontanyStatsResponse(incidents_par_statut=[], incidents_par_type=[])

        incidents = incidents_response.data
        
        stats_by_status = Counter(incident['statut'] for incident in incidents)
        stats_by_type = Counter(
            incident['typesincident']['nom_type'] for incident in incidents if incident.get('typesincident')
        )
        
        return FokontanyStatsResponse(
            incidents_par_statut=[StatItem(label=k, value=v) for k, v in stats_by_status.items()],
            incidents_par_type=[StatItem(label=k, value=v) for k, v in stats_by_type.items()]
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))