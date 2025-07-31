# D:\...\backend\app\routers\history.py

from fastapi import APIRouter, Depends, HTTPException, status
from ..database.database import supabase
from ..schemas.users import UserResponse
from ..schemas.history import HistoryLogItem
from ..utils.dependencies import role_checker
from typing import List

router = APIRouter()
get_current_authority_user = role_checker("AUTORITE_LOCALE")

@router.get("/",
            response_model=List[HistoryLogItem],
            summary="Récupérer l'historique de toutes les actions de changement de statut")
def get_action_history(current_user: UserResponse = Depends(get_current_authority_user)):
    """
    Retourne une liste de toutes les actions enregistrées dans la table `historiquestatuts`.
    Chaque entrée est enrichie avec le titre de l'incident et le nom de l'utilisateur
    qui a effectué la modification.
    """
    try:
        # --- MODIFICATION DE LA REQUÊTE ---
        # On ajoute 'role' à la sélection de l'utilisateur.
        response = supabase.table("historiquestatuts").select(
        "id, date_changement, ancien_statut, nouveau_statut, "
        "incident:incidents(titre), "
        "user:utilisateurs!modifie_par_id(nom, prenom, role)"
        ).order("date_changement", desc=False).execute()


        if not response.data:
            return []

        formatted_history = []
        for item in response.data:
            user_info = item.get('user')
            incident_info = item.get('incident')
            
            # --- MODIFICATION DU FORMATAGE ---
            # On construit la chaîne "Prénom Nom (Rôle)"
            modified_by_str = 'Utilisateur Inconnu'
            if user_info:
                user_role = user_info.get('role', 'Rôle Inconnu')
                modified_by_str = f"{user_info.get('nom', '')} {user_info.get('prenom', '')} - ({user_role})".strip()


            formatted_item = {
                "id": item['id'],
                "date_changement": item['date_changement'],
                "incident_title": incident_info.get('titre', 'Incident Inconnu') if incident_info else 'Incident Inconnu',
                "modified_by_name": modified_by_str, # <-- Utilisation de la nouvelle chaîne
                "old_status": item['ancien_statut'],
                "new_status": item['nouveau_statut']
            }
            formatted_history.append(HistoryLogItem(**formatted_item))

        return formatted_history

    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))