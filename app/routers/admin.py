# Fichier complet : backend/app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from ..database.database import supabase
from ..utils.dependencies import get_current_admin_user
from ..schemas.users import UserResponse, AdminKPIsResponse
from ..schemas.admin_management import (
    FokontanyResponse, FokontanyCreate, FokontanyUpdate,
    PosteSecuriteResponse, PosteSecuriteCreate, PosteSecuriteUpdate,
    AdminUserCreate, AdminUserUpdate # NOUVEAUX IMPORTS
)
from datetime import date, datetime, timedelta, timezone
from ..utils.email_sender import send_account_validated_to_user
from ..utils.security import hash_password # NOUVEL IMPORT
from uuid import UUID
import dns.resolver # NOUVEAU: Import pour la vérification DNS

router = APIRouter()

# --- Routes de gestion de la validation (existantes) ---
@router.get("/users/pending-validation",
            response_model=List[UserResponse],
            summary="Lister les utilisateurs non-vérifiés avec filtres",
            dependencies=[Depends(get_current_admin_user)])
def get_users_to_validate(role: Optional[str] = None):
    # ... (code inchangé)
    try:
        query = supabase.table("utilisateurs").select("*, postes_securite(*)").eq("est_verifie", False)
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
    # ... (code inchangé)
    try:
        response = supabase.table("utilisateurs").update({"est_verifie": True}).eq("id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Utilisateur ID {user_id} non trouvé.")
        validated_user = response.data[0]
        background_tasks.add_task(
            send_account_validated_to_user,
            user_email=validated_user.get("email")
        )
        return validated_user
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/users/{user_id}/reject",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Rejeter (supprimer) une demande d'inscription")
def reject_user_account(user_id: UUID, current_admin: UserResponse = Depends(get_current_admin_user)):
    try:
        # On s'assure de ne pouvoir rejeter qu'un utilisateur non vérifié
        response = supabase.table("utilisateurs").delete().match({"id": user_id, "est_verifie": False}).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Demande d'inscription ID {user_id} non trouvée ou utilisateur déjà validé.")
        
        # On doit aussi le supprimer de `auth.users`
        supabase.auth.admin.delete_user(str(user_id))
        return
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- NOUVELLES ROUTES : CRUD complet pour les Utilisateurs ---
@router.get("/users/all", response_model=List[UserResponse], summary="Lister TOUS les utilisateurs")
def list_all_users(current_user: UserResponse = Depends(get_current_admin_user)):
    """
    CORRECTION : Cette route est pour la page "Gestion des Utilisateurs" et liste tout le monde.
    """
    try:
        response = supabase.table("utilisateurs").select("*, postes_securite(nom_poste), fokontany(nom_fokontany)").order("nom").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users", response_model=UserResponse, status_code=201, summary="Créer un utilisateur (Admin)")
def create_user_by_admin(user_data: AdminUserCreate, current_user: UserResponse = Depends(get_current_admin_user)):
    try:
        auth_response = supabase.auth.sign_up({"email": user_data.email, "password": user_data.mot_de_passe})
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Impossible de créer l'utilisateur. L'email est peut-être déjà pris.")

        profile_data = user_data.model_dump(exclude={"mot_de_passe"})
        profile_data["mot_de_passe_hash"] = hash_password(user_data.mot_de_passe)
        
        # CORRECTION : Gérer les IDs nuls pour éviter l'erreur de clé étrangère
        if not profile_data.get("fokontany_id"):
            profile_data["fokontany_id"] = None
        if not profile_data.get("poste_securite_id"):
            profile_data["poste_securite_id"] = None

        update_response = supabase.table("utilisateurs").update(profile_data).eq("id", auth_response.user.id).execute()
        if not update_response.data:
            supabase.auth.admin.delete_user(auth_response.user.id)
            raise HTTPException(status_code=500, detail="Échec de la mise à jour du profil public.")

        return update_response.data[0]
    except Exception as e:
        if "duplicate key value" in str(e):
            raise HTTPException(status_code=409, detail=f"L'email '{user_data.email}' est déjà utilisé.")
        raise HTTPException(status_code=500, detail=f"Erreur de base de données : {e}")

@router.put("/users/{user_id}", response_model=UserResponse, summary="Mettre à jour un utilisateur (Admin)")
def update_user_by_admin(user_id: UUID, user_data: AdminUserUpdate, current_user: UserResponse = Depends(get_current_admin_user)):
    update_dict = user_data.model_dump(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour.")
    
    # CORRECTION : Gérer les IDs nuls
    if "fokontany_id" in update_dict and not update_dict["fokontany_id"]:
        update_dict["fokontany_id"] = None
    if "poste_securite_id" in update_dict and not update_dict["poste_securite_id"]:
        update_dict["poste_securite_id"] = None

    try:
        response = supabase.table("utilisateurs").update(update_dict).eq("id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de base de données : {e}")

@router.delete("/users/{user_id}", status_code=204, summary="Supprimer un utilisateur (Admin)")
def delete_user_by_admin(user_id: UUID, current_user: UserResponse = Depends(get_current_admin_user)):
    try:
        # La suppression dans `auth.users` déclenche la suppression en cascade dans `public.utilisateurs`
        supabase.auth.admin.delete_user(str(user_id))
    except Exception as e:
        # Gérer le cas où l'utilisateur n'existe pas déjà
        if "User not found" in str(e):
             raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")

@router.get("/kpis",
            response_model=AdminKPIsResponse,
            summary="Récupérer les KPIs pour le tableau de bord de l'administrateur")
def get_admin_kpis(current_admin: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        pending_users_res = supabase.table("utilisateurs").select("id", count='exact').eq("est_verifie", False).execute()
        utilisateurs_en_attente = pending_users_res.count or 0
        
        total_incidents_res = supabase.table("incidents").select("id", count='exact').execute()
        incidents_total = total_incidents_res.count or 0
        
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


@router.get("/fokontany", response_model=List[FokontanyResponse], summary="Lister tous les Fokontany")
def list_fokontany(current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("fokontany").select("*").order("nom_fokontany").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fokontany", response_model=FokontanyResponse, status_code=201, summary="Créer un Fokontany")
def create_fokontany(fokontany: FokontanyCreate, current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("fokontany").insert(fokontany.model_dump()).execute()
        return response.data[0]
    except Exception as e:
        if "duplicate key value" in str(e):
            raise HTTPException(status_code=409, detail=f"Le Fokontany '{fokontany.nom_fokontany}' existe déjà.")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/fokontany/{fokontany_id}", response_model=FokontanyResponse, summary="Mettre à jour un Fokontany")
def update_fokontany(fokontany_id: int, fokontany: FokontanyUpdate, current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("fokontany").update(fokontany.model_dump(exclude_unset=True)).eq("id", fokontany_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Fokontany non trouvé.")
        return response.data[0]
    except Exception as e:
        if "duplicate key value" in str(e):
            raise HTTPException(status_code=409, detail="Ce nom de Fokontany est déjà utilisé.")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/fokontany/{fokontany_id}", status_code=204, summary="Supprimer un Fokontany")
def delete_fokontany(fokontany_id: int, current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("fokontany").delete().eq("id", fokontany_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Fokontany non trouvé.")
    except Exception as e:
        if "foreign key constraint" in str(e):
            raise HTTPException(status_code=409, detail="Impossible de supprimer ce Fokontany car il est lié à des utilisateurs ou des incidents.")
        raise HTTPException(status_code=500, detail=str(e))


# --- Routes de gestion des Postes de Sécurité (existantes) ---

@router.get("/postes", response_model=List[PosteSecuriteResponse], summary="Lister tous les Postes de Sécurité")
def list_postes(current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("postes_securite").select("*").order("nom_poste").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/postes", response_model=PosteSecuriteResponse, status_code=201, summary="Créer un Poste de Sécurité")
def create_poste(poste: PosteSecuriteCreate, current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("postes_securite").insert(poste.model_dump()).execute()
        return response.data[0]
    except Exception as e:
        if "duplicate key value" in str(e):
            raise HTTPException(status_code=409, detail=f"Le poste '{poste.nom_poste}' existe déjà.")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/postes/{poste_id}", response_model=PosteSecuriteResponse, summary="Mettre à jour un Poste de Sécurité")
def update_poste(poste_id: int, poste: PosteSecuriteUpdate, current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("postes_securite").update(poste.model_dump(exclude_unset=True)).eq("id", poste_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Poste de sécurité non trouvé.")
        return response.data[0]
    except Exception as e:
        if "duplicate key value" in str(e):
            raise HTTPException(status_code=409, detail="Ce nom de poste est déjà utilisé.")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/postes/{poste_id}", status_code=204, summary="Supprimer un Poste de Sécurité")
def delete_poste(poste_id: int, current_user: UserResponse = Depends(get_current_admin_user)):
    # ... (code inchangé)
    try:
        response = supabase.table("postes_securite").delete().eq("id", poste_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Poste de sécurité non trouvé.")
    except Exception as e:
        if "foreign key constraint" in str(e):
            raise HTTPException(status_code=409, detail="Impossible de supprimer ce poste car il est lié à des utilisateurs ou des types d'incidents.")
        raise HTTPException(status_code=500, detail=str(e))
    
# --- CORRECTION: Logique de validation d'email ---
@router.post("/users/{user_id}/check-email-validity",
             summary="Vérifier la validité d'un email (via DNS)",
             dependencies=[Depends(get_current_admin_user)])
def check_email_validity(user_id: UUID):
    try:
        user_res = supabase.table("utilisateurs").select("email").eq("id", user_id).single().execute()
        if not user_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur non trouvé.")
        
        email = user_res.data['email']
        domain = email.split('@')[1]

        # VRAIE VÉRIFICATION: On vérifie si le domaine a des enregistrements MX
        try:
            dns.resolver.resolve(domain, 'MX')
            return {"email": email, "is_valid": True, "message": "Le domaine de l'e-mail est valide et accepte des e-mails."}
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
            return {"email": email, "is_valid": False, "message": "Le domaine de l'e-mail semble invalide ou n'a pas pu être contacté."}
            
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
