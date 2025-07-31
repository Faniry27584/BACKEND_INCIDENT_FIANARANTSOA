from fastapi import APIRouter, Depends, HTTPException, status
from ..database.database import supabase
from ..schemas.users import UserResponse
from ..schemas.stats import FokontanyStatsResponse, StatItem, AuthorityKPIsResponse, GlobalStatsResponse
from datetime import datetime
from ..utils.dependencies import role_checker
from typing import List
from collections import Counter

router = APIRouter()
# Dépendance pour s'assurer que seul un Chef de Fokontany peut accéder à cette route
get_current_fokontany_chief_user = role_checker("CHEF_FOKONTANY")
get_current_authority_user = role_checker("AUTORITE_LOCALE")

@router.get("/fokontany",
            response_model=FokontanyStatsResponse,
            summary="Récupérer les statistiques pour le Fokontany du chef connecté")
def get_stats_for_fokontany(current_user: UserResponse = Depends(get_current_fokontany_chief_user)):
    """
    Calcule et retourne les statistiques agrégées (par statut et par type)
    pour tous les incidents du Fokontany associé au chef connecté.
    """
    if not current_user.fokontany_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun Fokontany n'est associé à ce compte."
        )

    try:
        # 1. Récupérer tous les incidents du Fokontany avec le nom du type d'incident
        # La jointure `typesincident(nom_type)` est gérée automatiquement par Supabase
        incidents_response = supabase.table("incidents").select(
            "statut, typesincident(nom_type)"
        ).eq("fokontany_id", current_user.fokontany_id).execute()
        
        if not incidents_response.data:
            # S'il n'y a aucun incident, retourner des statistiques vides
            return FokontanyStatsResponse(incidents_par_statut=[], incidents_par_type=[])

        incidents = incidents_response.data

        # 2. Agréger les données par statut
        stats_by_status = {}
        for incident in incidents:
            status = incident['statut']
            stats_by_status[status] = stats_by_status.get(status, 0) + 1
        
        incidents_par_statut_list: List[StatItem] = [
            StatItem(label=status, value=count) for status, count in stats_by_status.items()
        ]

        # 3. Agréger les données par type d'incident
        stats_by_type = {}
        for incident in incidents:
            # Vérifier que la jointure a bien retourné un type
            if incident.get('typesincident') and incident['typesincident'].get('nom_type'):
                type_name = incident['typesincident']['nom_type']
                stats_by_type[type_name] = stats_by_type.get(type_name, 0) + 1
        
        incidents_par_type_list: List[StatItem] = [
            StatItem(label=type_name, value=count) for type_name, count in stats_by_type.items()
        ]

        return FokontanyStatsResponse(
            incidents_par_statut=incidents_par_statut_list,
            incidents_par_type=incidents_par_type_list
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# NOUVELLE ROUTE POUR LES KPIS DE L'AUTORITÉ LOCALE
@router.get("/authority-kpis",
            response_model=AuthorityKPIsResponse,
            summary="Récupérer les KPIs pour l'Autorité Locale")
def get_kpis_for_authority(current_user: UserResponse = Depends(get_current_authority_user)):
    """
    Calcule et retourne les KPIs pour le tableau de bord principal de l'Autorité Locale.
    """
    try:
        # 1. KPI: Incidents à valider (Nouveau ou Urgent)
        # On utilise 'count' pour laisser la base de données faire le décompte, c'est très efficace.
        pending_incidents_res = supabase.table("incidents").select("id", count='exact').in_("statut", ["NOUVEAU", "URGENT"]).execute()
        incidents_a_valider = pending_incidents_res.count or 0

        # 2. KPI: Nombre d'agents de sécurité actifs
        active_agents_res = supabase.table("utilisateurs").select("id", count='exact').eq("role", "SECURITE_URBAINE").eq("est_verifie", True).execute()
        agents_actifs = active_agents_res.count or 0

        # 3. KPI: Temps de résolution moyen des incidents
        resolved_incidents_res = supabase.table("incidents").select("date_signalement, date_resolution").eq("statut", "RESOLU").not_.is_("date_resolution", "null").execute()
        
        temps_resolution_moyen_heures = None
        if resolved_incidents_res.data:
            total_duration_seconds = 0
            count_resolved = 0
            for incident in resolved_incidents_res.data:
                # Supabase retourne les dates au format ISO 8601, Python peut les parser directement
                start_time = datetime.fromisoformat(incident['date_signalement'])
                end_time = datetime.fromisoformat(incident['date_resolution'])
                duration = end_time - start_time
                total_duration_seconds += duration.total_seconds()
                count_resolved += 1
            
            if count_resolved > 0:
                average_seconds = total_duration_seconds / count_resolved
                # On convertit le résultat en heures pour une meilleure lisibilité
                temps_resolution_moyen_heures = round(average_seconds / 3600, 2)

        return AuthorityKPIsResponse(
            incidents_a_valider=incidents_a_valider,
            agents_actifs=agents_actifs,
            temps_resolution_moyen_heures=temps_resolution_moyen_heures
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# NOUVELLE ROUTE POUR LA PAGE DE STATISTIQUES GLOBALES
@router.get("/global",
            response_model=GlobalStatsResponse,
            summary="Récupérer les statistiques globales pour toute la commune")
def get_global_stats(current_user: UserResponse = Depends(get_current_authority_user)):
    """
    Calcule et retourne les statistiques agrégées pour tous les incidents
    de la commune, destiné à la page de statistiques de l'Autorité Locale.
    """
    try:
        # On récupère tous les incidents avec les noms des types et des fokontany
        # grâce aux jointures automatiques de Supabase.
        incidents_res = supabase.table("incidents").select(
            "statut, typesincident(nom_type), fokontany(nom_fokontany)"
        ).execute()
        
        incidents = incidents_res.data
        if not incidents:
            return GlobalStatsResponse(
                incidents_par_statut=[],
                incidents_par_type=[],
                incidents_par_fokontany=[]
            )

        # Utilisation de collections.Counter pour un comptage plus efficace
        status_counts = Counter(inc['statut'] for inc in incidents)
        type_counts = Counter(
            inc['typesincident']['nom_type'] for inc in incidents if inc.get('typesincident')
        )
        fokontany_counts = Counter(
            inc['fokontany']['nom_fokontany'] for inc in incidents if inc.get('fokontany')
        )

        # Transformation en listes de StatItem
        statut_list = [StatItem(label=k, value=v) for k, v in status_counts.items()]
        type_list = [StatItem(label=k, value=v) for k, v in type_counts.items()]
        fokontany_list = [StatItem(label=k, value=v) for k, v in fokontany_counts.items()]

        return GlobalStatsResponse(
            incidents_par_statut=statut_list,
            incidents_par_type=type_list,
            incidents_par_fokontany=fokontany_list
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
