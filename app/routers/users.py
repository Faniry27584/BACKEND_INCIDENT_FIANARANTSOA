from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
import logging

from pydantic import parse_obj_as
from ..database.database import supabase
# NOUVEAU: Importer les nouveaux schémas et utilitaires
from ..schemas.users import UserResponse, UserUpdate, PasswordUpdate, UserPhotoUpdate
from ..utils.dependencies import get_current_user_data
from ..utils.security import verify_password, hash_password
router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Route existante ---
@router.get("/role/{role_name}",
            response_model=List[UserResponse],
            summary="Lister les utilisateurs par rôle")
def get_users_by_role(role_name: str, current_user: UserResponse = Depends(get_current_user_data)):
    # ... (code de vérification des droits inchangé)
    if current_user.role not in ["ADMIN", "AUTORITE_LOCALE"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action non autorisée."
        )
    try:
        query = "id, nom, prenom, email, telephone, role, est_verifie, fokontany_id, poste_securite_id, postes_securite(nom_poste)"
        response = supabase.table("utilisateurs").select(query).eq("role", role_name.upper()).eq("est_verifie", True).execute()
        logger.info("Utilisateurs récupérés : %s", response.data)
        
        return response.data
    except Exception as e:
        logger.error("Erreur lors de la récupération des utilisateurs : %s", str(e))
        raise HTTPException(status_code=500, detail="Erreur serveur : " + str(e))

# --- NOUVELLE ROUTE POUR FILTRER LES AGENTS PAR FOKONTANY ---
@router.get("/agents-by-fokontany/{fokontany_id}",
            response_model=List[UserResponse],
            summary="Lister les agents de sécurité par Fokontany")
def get_security_agents_by_fokontany(fokontany_id: int, current_user: UserResponse = Depends(get_current_user_data)):
    """
    Récupère la liste des agents de la sécurité urbaine actifs
    qui sont spécifiquement rattachés à un Fokontany donné.
    Utilisé par l'Autorité Locale pour l'assignation des incidents.
    """
    # Seuls l'admin ou l'autorité locale peuvent appeler cette route
    if current_user.role not in ["ADMIN", "AUTORITE_LOCALE"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action non autorisée."
        )
    try:
        query = "id, nom, prenom, email, telephone, role, est_verifie, fokontany_id, poste_securite_id, postes_securite(nom_poste)"
        response = supabase.table("utilisateurs").select(query)\
            .eq("role", "SECURITE_URBAINE")\
            .eq("est_verifie", True)\
            .eq("fokontany_id", fokontany_id)\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error("Erreur lors de la récupération des agents par fokontany : %s", str(e))
        raise HTTPException(status_code=500, detail="Erreur serveur : " + str(e))


# --- NOUVELLES ROUTES POUR LE PROFIL ---
@router.get("/me",
            response_model=UserResponse,
            summary="Récupérer les informations du profil de l'utilisateur connecté")
def get_my_profile(current_user: UserResponse = Depends(get_current_user_data)):
    """
    Retourne les informations détaillées du profil de l'utilisateur actuellement authentifié.
    La dépendance `get_current_user_data` fait déjà tout le travail.
    """
    return current_user

@router.put("/me",
            response_model=UserResponse,
            summary="Mettre à jour le profil de l'utilisateur connecté")
def update_my_profile(user_update: UserUpdate, current_user: UserResponse = Depends(get_current_user_data)):
    """
    Met à jour le nom, prénom et numéro de téléphone de l'utilisateur connecté.
    """
    update_data = user_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune donnée à mettre à jour.")
    try:
        # Met à jour la base de données
        response = supabase.table("utilisateurs").update(update_data).eq("id", current_user.id).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur non trouvé.")
        
        # Récupère et retourne les données mises à jour pour le frontend
        updated_user_response = supabase.table("utilisateurs").select("*").eq("id", current_user.id).single().execute()
        return updated_user_response.data
    except Exception as e:
        # Gère les erreurs potentielles (ex: numéro de téléphone déjà utilisé)
        if "duplicate key value violates unique constraint" in str(e):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Le numéro de téléphone est déjà utilisé.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/me/password",
            status_code=status.HTTP_204_NO_CONTENT,
            summary="Changer le mot de passe de l'utilisateur connecté")
def change_my_password(password_update: PasswordUpdate, current_user: UserResponse = Depends(get_current_user_data)):
    """
    Permet à l'utilisateur de changer son propre mot de passe après avoir vérifié l'ancien.
    """
    try:
        # 1. Récupérer le hash du mot de passe actuel depuis la BDD
        user_record = supabase.table("utilisateurs").select("mot_de_passe_hash").eq("id", current_user.id).single().execute()
        if not user_record.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur non trouvé.")
        
        current_password_hash = user_record.data['mot_de_passe_hash']
        # 2. Vérifier si l'ancien mot de passe fourni est correct
        if not verify_password(password_update.ancien_mot_de_passe, current_password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="L'ancien mot de passe est incorrect.")
        # 3. Hasher le nouveau mot de passe
        new_password_hash = hash_password(password_update.nouveau_mot_de_passe)
        # 4. Mettre à jour le mot de passe dans la base de données
        supabase.table("utilisateurs").update({"mot_de_passe_hash": new_password_hash}).eq("id", current_user.id).execute()
        # Pas de contenu à retourner, juste un statut 204
        return
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#Nouvelle route pour le photo d'USER
@router.put("/me/photo",
            summary="Mettre à jour la photo de profil de l'utilisateur connecté")
def update_user_photo(
    payload: UserPhotoUpdate,
    current_user: UserResponse = Depends(get_current_user_data)
):
    """
    Met à jour l'URL de la photo de profil de l'utilisateur connecté dans la base de données.
    """
    try:
        response = supabase.table("utilisateurs").update({
            "photo_url": payload.photo_url
        }).eq("id", current_user.id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé ou mise à jour échouée.")

        return {"message": "Photo de profil mise à jour avec succès.", "photo_url": payload.photo_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur : {str(e)}")

# Route pour la fonctionnalité "Contacter les Secours"
@router.get("/panic-contacts",
            response_model=List[UserResponse],
            summary="Récupérer les contacts d'urgence pour le mode panique")
def get_panic_contacts(
    fokontany_id: int = Query(..., description="ID du Fokontany de l'utilisateur"),
    type_id: int = Query(..., description="ID du type d'incident"),
    current_user: UserResponse = Depends(get_current_user_data)
):
    """
    Récupère une liste de contacts d'urgence pour le mode panique.
    
    La liste inclut toutes les autorités locales et les agents de sécurité urbaine
    liés au fokontany de l'utilisateur et au poste de sécurité recommandé pour l'incident.
    """
    if current_user.role not in ["CITOYEN", "CHEF_FOKONTANY"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée.")
    
    try:
        contact_list = []
        
        # 1. Récupérer toutes les Autorités Locales
        authorities_res = supabase.table("utilisateurs").select("*, postes_securite(nom_poste)").eq("role", "AUTORITE_LOCALE").eq("est_verifie", True).execute()
        if authorities_res.data:
            contact_list.extend(authorities_res.data)
        
        logger.info(f"Étape 1: {len(contact_list)} Autorités Locales trouvées.")

        # 2. Récupérer le poste recommandé pour le type d'incident
        # On utilise .execute() pour une meilleure gestion des erreurs
        type_res = supabase.table("typesincident").select("poste_recommande_id").eq("id", type_id).execute()
        
        # On vérifie si un poste recommandé a été trouvé
        if type_res.data and type_res.data[0].get("poste_recommande_id"):
            poste_id = type_res.data[0]["poste_recommande_id"]
            logger.info(f"Étape 2: Incident de type {type_id} recommande le poste_id {poste_id}.")
            
            # 3. Récupérer les agents de sécurité correspondants
            # La requête filtre par le fokontany_id ET le poste_securite_id
            security_res = supabase.table("utilisateurs").select("*, postes_securite(nom_poste)") \
                .eq("role", "SECURITE_URBAINE") \
                .eq("est_verifie", True) \
                .eq("fokontany_id", fokontany_id) \
                .eq("poste_securite_id", poste_id) \
                .execute()
            
            logger.info(f"Étape 3: Recherche d'agents pour fokontany_id={fokontany_id} et poste_id={poste_id}. Trouvé: {len(security_res.data)} agent(s).")
            
            if security_res.data:
                # Ajoute les agents de sécurité à la liste sans créer de doublons
                existing_ids = {user.get('id') for user in contact_list}
                for agent in security_res.data:
                    if agent.get('id') not in existing_ids:
                        contact_list.append(agent)
        else:
            logger.warning(f"Aucun poste recommandé trouvé pour le type d'incident ID {type_id}.")
        
        # 4. Validation finale de la liste complète des contacts
        return parse_obj_as(List[UserResponse], contact_list)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des contacts d'urgence : {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur serveur lors de la récupération des contacts.")
