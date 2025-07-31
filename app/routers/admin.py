from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from ..database.database import supabase
from ..utils.dependencies import get_current_admin_user
from ..schemas.users import UserResponse, AdminKPIsResponse
from datetime import date, datetime, timedelta, timezone
from ..utils.email_sender import send_account_validated_to_user
from uuid import UUID

router = APIRouter()

@router.get("/users",
            response_model=List[UserResponse],
            summary="Lister tous les utilisateurs non-vérifiés avec filtres",
            dependencies=[Depends(get_current_admin_user)])
def get_users_to_validate(role: Optional[str] = None):
    """
    Récupère la liste des utilisateurs non vérifiés.
    Peut être filtrée par rôle.
    Ex: /users?role=CHEF_FOKONTANY
    """
    try:
        query = supabase.table("utilisateurs").select("*").eq("est_verifie", False)
        
        if role:
            query = query.eq("role", role)
            
        response = query.execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/users/{user_id}/validate",
             response_model=UserResponse,
             summary="Valider le compte d'un utilisateur",
             dependencies=[Depends(get_current_admin_user)])
def validate_user_account(user_id: UUID, background_tasks: BackgroundTasks, current_admin: UserResponse = Depends(get_current_admin_user)):
    try:
        # On met à jour l'utilisateur ET on récupère ses données en une seule fois
        response = supabase.table("utilisateurs").update({"est_verifie": True}).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Utilisateur ID {user_id} non trouvé.")
        
        validated_user = response.data[0]
        
        # --- AJOUT DE LA NOTIFICATION ---
        # On envoie un email à l'utilisateur pour lui dire que son compte est actif
        background_tasks.add_task(
            send_account_validated_to_user,
            user_email=validated_user.get("email")
        )

        return validated_user
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/users/{user_id}/reject",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Rejeter (supprimer) une demande d'inscription",
               dependencies=[Depends(get_current_admin_user)])
def reject_user_account(user_id: UUID):
    """
    Supprime un utilisateur qui n'a pas encore été vérifié.
    C'est une action destructive.
    """
    try:
        # On s'assure de ne pouvoir supprimer que les non-vérifiés pour la sécurité
        response = supabase.table("utilisateurs").delete().match({"id": user_id, "est_verifie": False}).execute()
        
        # Si aucune ligne n'est affectée, l'utilisateur n'existait pas ou était déjà vérifié
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Demande d'inscription ID {user_id} non trouvée ou utilisateur déjà validé.")
            
        return
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    
# --- NOUVELLE ROUTE POUR LES KPIS DE L'ADMINISTRATEUR ---
@router.get("/kpis",
            response_model=AdminKPIsResponse,
            summary="Récupérer les KPIs pour le tableau de bord de l'administrateur")
def get_admin_kpis(current_admin: UserResponse = Depends(get_current_admin_user)):
    """
    Calcule et retourne les indicateurs de performance clés pour la supervision
    de la plateforme par l'administrateur.
    """
    try:
        # KPI 1: Utilisateurs en attente
        pending_users_res = supabase.table("utilisateurs").select("id", count='exact').eq("est_verifie", False).execute()
        utilisateurs_en_attente = pending_users_res.count or 0

        # KPI 2: Total des incidents
        total_incidents_res = supabase.table("incidents").select("id", count='exact').execute()
        incidents_total = total_incidents_res.count or 0

        # KPI 3: Incidents signalés aujourd'hui
        # On définit le début et la fin de la journée en UTC pour être compatible avec Supabase
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        today_end = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
        
        today_incidents_res = supabase.table("incidents").select("id", count='exact').gte("date_signalement", today_start).lt("date_signalement", today_end).execute()
        incidents_aujourdhui = today_incidents_res.count or 0

        return AdminKPIsResponse(
            utilisateurs_en_attente=utilisateurs_en_attente,
            incidents_total=incidents_total,
            incidents_aujourdhui=incidents_aujourdhui
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
