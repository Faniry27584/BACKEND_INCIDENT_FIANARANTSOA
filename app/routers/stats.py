# Fichier complet : backend/app/routers/stats.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from ..database.database import supabase
from ..schemas.users import UserResponse
from ..schemas.stats import FokontanyStatsResponse, StatItem, AuthorityKPIsResponse, GlobalStatsResponse
from datetime import datetime, timedelta, timezone, date
from ..utils.dependencies import role_checker
from typing import List, Optional
from collections import Counter, defaultdict
import calendar

router = APIRouter()
get_current_fokontany_chief_user = role_checker("CHEF_FOKONTANY")
get_current_authority_user = role_checker("AUTORITE_LOCALE")
get_current_security_user = role_checker("SECURITE_URBAINE")

# MODIFIÉ: Fonction d'agrégation améliorée
def aggregate_incidents_by_period(incidents: List[dict], period: str, start_date: date, end_date: date):
    """Agrège les incidents par jour, semaine ou mois sur une période donnée."""
    
    # Générer les labels pour la période
    labels = []
    if period == 'day':
        delta = end_date - start_date
        labels = [(start_date + timedelta(days=i)).strftime('%d/%m') for i in range(delta.days + 1)]
    elif period == 'week':
        # Générer des labels pour chaque semaine dans la plage
        current_date = start_date
        while current_date <= end_date:
            # Format: Année-NuméroDeSemaine
            labels.append(current_date.strftime('%Y-W%U'))
            current_date += timedelta(weeks=1)
    elif period == 'month':
        # Générer des labels pour chaque mois dans la plage
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime('%Y-%m'))
            # Aller au premier jour du mois suivant
            current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)

    period_counts = {label: 0 for label in labels}
    
    for incident in incidents:
        incident_date = datetime.fromisoformat(incident['date_signalement']).date()
        if start_date <= incident_date <= end_date:
            if period == 'day':
                label = incident_date.strftime('%d/%m')
            elif period == 'week':
                label = incident_date.strftime('%Y-W%U')
            elif period == 'month':
                label = incident_date.strftime('%Y-%m')
            
            if label in period_counts:
                period_counts[label] += 1
                
    return [StatItem(label=day, value=count) for day, count in period_counts.items()]


@router.get("/fokontany",
            response_model=FokontanyStatsResponse,
            summary="Récupérer les statistiques pour le Fokontany du chef connecté")
def get_stats_for_fokontany(
    current_user: UserResponse = Depends(get_current_fokontany_chief_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    type_id: Optional[int] = Query(None),
    period: str = Query("day", enum=["day", "week", "month"])
):
    if not current_user.fokontany_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun Fokontany n'est associé à ce compte."
        )
    try:
        query = supabase.table("incidents").select(
            "statut, typesincident(nom_type), date_signalement"
        ).eq("fokontany_id", current_user.fokontany_id)

        # Application des filtres
        effective_end_date = end_date or date.today()
        effective_start_date = start_date or (effective_end_date - timedelta(days=29))
        
        query = query.gte("date_signalement", effective_start_date.isoformat())
        query = query.lte("date_signalement", (effective_end_date + timedelta(days=1)).isoformat())

        if type_id:
            query = query.eq("type_id", type_id)

        incidents_response = query.execute()
        
        if not incidents_response.data:
            return FokontanyStatsResponse(incidents_par_statut=[], incidents_par_type=[], incidents_over_time=[])

        incidents = incidents_response.data
        
        stats_by_status = Counter(incident['statut'] for incident in incidents)
        stats_by_type = Counter(
            incident['typesincident']['nom_type'] for incident in incidents if incident.get('typesincident')
        )
        
        incidents_over_time = aggregate_incidents_by_period(incidents, period, effective_start_date, effective_end_date)
        
        return FokontanyStatsResponse(
            incidents_par_statut=[StatItem(label=k, value=v) for k, v in stats_by_status.items()],
            incidents_par_type=[StatItem(label=k, value=v) for k, v in stats_by_type.items()],
            incidents_over_time=incidents_over_time
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
def get_global_stats(
    current_user: UserResponse = Depends(get_current_authority_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    type_id: Optional[int] = Query(None),
    period: str = Query("day", enum=["day", "week", "month"])
):
    try:
        query = supabase.table("incidents").select(
            "statut, date_signalement, typesincident(nom_type), fokontany(nom_fokontany)"
        )

        # Application des filtres
        effective_end_date = end_date or date.today()
        effective_start_date = start_date or (effective_end_date - timedelta(days=29))

        query = query.gte("date_signalement", effective_start_date.isoformat())
        query = query.lte("date_signalement", (effective_end_date + timedelta(days=1)).isoformat())

        if type_id:
            query = query.eq("type_id", type_id)

        incidents_res = query.execute()
        
        incidents = incidents_res.data
        if not incidents:
            return GlobalStatsResponse(incidents_par_statut=[], incidents_par_type=[], incidents_par_fokontany=[], incidents_over_time=[])
            
        status_counts = Counter(inc['statut'] for inc in incidents)
        type_counts = Counter(inc['typesincident']['nom_type'] for inc in incidents if inc.get('typesincident'))
        fokontany_counts = Counter(inc['fokontany']['nom_fokontany'] for inc in incidents if inc.get('fokontany'))
        
        incidents_over_time = aggregate_incidents_by_period(incidents, period, effective_start_date, effective_end_date)
        
        return GlobalStatsResponse(
            incidents_par_statut=[StatItem(label=k, value=v) for k, v in status_counts.items()],
            incidents_par_type=[StatItem(label=k, value=v) for k, v in type_counts.items()],
            incidents_par_fokontany=[StatItem(label=k, value=v) for k, v in fokontany_counts.items()],
            incidents_over_time=incidents_over_time
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/security/me",
            response_model=FokontanyStatsResponse,
            summary="Récupérer les statistiques des missions de l'agent connecté")
def get_stats_for_security_agent(
    current_user: UserResponse = Depends(get_current_security_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    type_id: Optional[int] = Query(None),
    period: str = Query("day", enum=["day", "week", "month"])
):
    try:
        query = supabase.table("incidents").select(
            "statut, date_signalement, typesincident(nom_type)"
        ).eq("assigne_a_id", str(current_user.id))

        # Application des filtres
        effective_end_date = end_date or date.today()
        effective_start_date = start_date or (effective_end_date - timedelta(days=29))
        
        query = query.gte("date_signalement", effective_start_date.isoformat())
        query = query.lte("date_signalement", (effective_end_date + timedelta(days=1)).isoformat())

        if type_id:
            query = query.eq("type_id", type_id)
        
        incidents_response = query.execute()

        if not incidents_response.data:
            return FokontanyStatsResponse(incidents_par_statut=[], incidents_par_type=[], incidents_over_time=[])
        
        incidents = incidents_response.data
        
        stats_by_status = Counter(incident['statut'] for incident in incidents)
        stats_by_type = Counter(
            incident['typesincident']['nom_type'] for incident in incidents if incident.get('typesincident')
        )
        
        incidents_over_time = aggregate_incidents_by_period(incidents, period, effective_start_date, effective_end_date)
        
        return FokontanyStatsResponse(
            incidents_par_statut=[StatItem(label=k, value=v) for k, v in stats_by_status.items()],
            incidents_par_type=[StatItem(label=k, value=v) for k, v in stats_by_type.items()],
            incidents_over_time=incidents_over_time
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))