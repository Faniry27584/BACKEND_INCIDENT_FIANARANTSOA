from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks, Header, Body, Request
from fastapi.security import OAuth2PasswordRequestForm
from ..schemas.users import UserCreate, UserResponse, Token
from ..schemas.auth import ForgotPasswordRequest, ResetPasswordRequest, ResetPasswordCodeRequest
from ..utils.security import hash_password, verify_password, create_access_token
from ..database.database import supabase
from ..utils.email_sender import send_new_registration_to_admin, send_password_reset_code_email, send_password_reset_email
import secrets
from datetime import datetime, timedelta, timezone
import hashlib
from ..utils.dependencies import get_current_user_data 

router = APIRouter()

@router.post("/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Créer ou finaliser l'inscription d'un utilisateur")
def register_user(user: UserCreate, background_tasks: BackgroundTasks):
    """
    Gère 3 cas :
    1. Nouvelle inscription par e-mail/mot de passe.
    2. Finalisation d'un profil après une inscription Google.
    3. Bloque si l'e-mail est déjà utilisé par un compte complet.
    """
    try:
        # Vérifier si un profil public existe déjà pour cet e-mail
        profile_res = supabase.table("utilisateurs").select("id, role").eq("email", user.email).execute()
        existing_profile = profile_res.data[0] if profile_res.data else None

        # Préparer les données du profil à insérer ou mettre à jour
        profile_data = {
            "nom": user.nom,
            "prenom": user.prenom,
            "telephone": user.telephone,
            "role": user.role.upper().replace(" ", "_"),
            "fokontany_id": user.fokontany_id if user.role.upper().replace(" ", "_") == 'CHEF_FOKONTANY' else None,
            "poste_securite_id": user.poste_securite_id if user.role.upper().replace(" ", "_") == 'SECURITE_URBAINE' else None,
            "est_verifie": True if user.role.upper().replace(" ", "_") == 'CITOYEN' else False
        }

        # CAS 1 : Finalisation d'un profil Google (le profil existe mais n'a pas de rôle)
        if existing_profile and not existing_profile.get('role'):
            update_response = supabase.table("utilisateurs").update(profile_data).eq("email", user.email).execute()
            if not update_response.data:
                raise HTTPException(status_code=500, detail="Erreur lors de la finalisation de l'inscription.")
            finalized_user = update_response.data[0]
        
        # CAS 2 : L'e-mail est déjà associé à un profil complet
        elif existing_profile:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"L'e-mail '{user.email}' est déjà utilisé.")
        
        # CAS 3 : Nouvelle inscription par e-mail / mot de passe
        else:
            if not user.mot_de_passe:
                raise HTTPException(status_code=400, detail="Le mot de passe est requis pour une inscription standard.")

            # Étape A : Créer l'utilisateur dans le service d'authentification de Supabase
            auth_response = supabase.auth.sign_up({"email": user.email, "password": user.mot_de_passe})
            if not auth_response.user:
                raise HTTPException(status_code=500, detail="La création de l'utilisateur dans le service d'authentification a échoué.")
            
            # Étape B : Mettre à jour le profil public créé par le trigger SQL
            profile_data["mot_de_passe_hash"] = hash_password(user.mot_de_passe)
            update_response = supabase.table("utilisateurs").update(profile_data).eq("id", auth_response.user.id).execute()
            
            if not update_response.data:
                raise HTTPException(status_code=500, detail="La mise à jour du profil public a échoué après l'inscription.")
            finalized_user = update_response.data[0]

        # Envoyer l'e-mail de notification si nécessaire
        if not finalized_user.get("est_verifie"):
            # ... (votre code d'envoi d'e-mail reste le même)
            pass

        return finalized_user

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Erreur inattendue lors de l'inscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Les autres routes restent inchangées
@router.post("/login",
response_model=Token,
summary="Connecter un utilisateur")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Fournit un token JWT après vérification de l'email et du mot de passe."""
    try:
        response = supabase.table("utilisateurs").select("*").eq("email", form_data.username).single().execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email ou mot de passe incorrect.")

        user = response.data
        if not user.get("est_verifie"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre compte n'a pas encore été validé par un administrateur."
            )
        if not verify_password(form_data.password, user.get("mot_de_passe_hash")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect.")

        token_data = {
            "sub": user.get("email"),
            "id": user.get("id"),
            "role": user.get("role"),
            "nom": user.get("nom"),
            "prenom": user.get("prenom"),
            "fokontany_id": user.get("fokontany_id")
        }
        
        access_token = create_access_token(data=token_data)
        
        return {"access_token": access_token, "token_type": "bearer"}
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Une erreur interne est survenue.")

@router.post("/forgot-password", status_code=status.HTTP_200_OK, summary="Demander une réinitialisation de mot de passe")
def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    try:
        user_res = supabase.table("utilisateurs").select("id, email").eq("email", request.email).single().execute()
        if not user_res.data:
            return {"message": "Si un compte avec cet email existe, un lien de réinitialisation a été envoyé."}

        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode('utf-8')).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        supabase.table("utilisateurs").update({
            "reset_token": token_hash,
            "reset_token_expires": expires_at.isoformat()
        }).eq("email", request.email).execute()

        background_tasks.add_task(
            send_password_reset_email,
            user_email=request.email,
            reset_token=reset_token
        )

        return {"message": "Si un compte avec cet email existe, un lien de réinitialisation a été envoyé."}

    except Exception as e:
        print(f"Forgot password error: {e}")
        return {"message": "Une erreur est survenue. Veuillez réessayer plus tard."}
    




@router.post("/google-login")
def google_login(request: Request, payload: dict = Body(...)):
    """
    Authentifie un utilisateur Google via Supabase.
    Récupère son profil et retourne un JWT local.
    """
    try:
        supabase_token = payload.get("access_token")
        if not supabase_token:
            raise HTTPException(status_code=400, detail="Access token requis")

        # Vérifie le token via l'API Supabase
        user_info_resp = supabase.auth.get_user(jwt=supabase_token)
        if not user_info_resp.user:
            raise HTTPException(status_code=401, detail="Token Supabase invalide")

        user_email = user_info_resp.user.email
        if not user_email:
            raise HTTPException(status_code=400, detail="Email utilisateur manquant")

        # Vérifie dans la table `utilisateurs`
        user_res = supabase.table("utilisateurs").select("*").eq("email", user_email).single().execute()
        if not user_res.data:
            raise HTTPException(status_code=404, detail="Aucun profil trouvé pour cet email.")

        user = user_res.data

        # Finalisation du profil si nécessaire
        if not user.get("est_verifie"):
            raise HTTPException(
                status_code=403,
                detail="Votre compte n'a pas encore été validé par un administrateur."
            )

        token_data = {
            "sub": user_email,
            "id": user.get("id"),
            "role": user.get("role"),
            "nom": user.get("nom"),
            "prenom": user.get("prenom"),
            "fokontany_id": user.get("fokontany_id")
        }

        access_token = create_access_token(data=token_data)
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"[Google Login] Erreur : {e}")
        raise HTTPException(status_code=500, detail="Erreur interne lors de la connexion Google")




@router.post("/reset-password", status_code=status.HTTP_200_OK, summary="Réinitialiser le mot de passe")
def reset_password(request: ResetPasswordRequest):
    try:
        token_hash = hashlib.sha256(request.token.encode('utf-8')).hexdigest()
        user_res = supabase.table("utilisateurs").select("*").eq("reset_token", token_hash).single().execute()
        
        if not user_res.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le lien de réinitialisation est invalide.")
        
        user = user_res.data
        token_expires_str = user.get("reset_token_expires")
        if not token_expires_str or datetime.fromisoformat(token_expires_str) < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le lien de réinitialisation a expiré.")

        new_password_hash = hash_password(request.new_password)
        supabase.table("utilisateurs").update({
            "mot_de_passe_hash": new_password_hash,
            "reset_token": None,
            "reset_token_expires": None
        }).eq("id", user['id']).execute()

        return {"message": "Votre mot de passe a été réinitialisé avec succès."}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Reset password error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Une erreur interne est survenue.")

@router.post("/token/from-supabase",
    response_model=Token,
    summary="Crée un token JWT interne à partir d'un token Supabase")
async def exchange_supabase_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    supabase_token = authorization.split(" ")[1]

    try:
        user_res = supabase.auth.get_user(supabase_token)
        user_supabase = user_res.user
        if not user_supabase:
            raise HTTPException(status_code=401, detail="Invalid Supabase token")

        profile_res = supabase.table("utilisateurs").select("*").eq("id", user_supabase.id).single().execute()
        if not profile_res.data:
            raise HTTPException(status_code=404, detail="Profil utilisateur non trouvé dans la base de données publique.")
        
        user_profile = profile_res.data
        token_data = {
            "sub": user_profile.get("email"),
            "id": user_profile.get("id"),
            "role": user_profile.get("role"),
            "nom": user_profile.get("nom"),
            "prenom": user_profile.get("prenom"),
            "fokontany_id": user_profile.get("fokontany_id")
        }
        access_token = create_access_token(data=token_data)
        return {"access_token": access_token, "access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        print(f"Token exchange error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Impossible de valider le token Supabase.",
        )
    

#Code pour l'APP mobile
@router.post(
    "/forgot-password-mobile-code",
    status_code=status.HTTP_200_OK,
    summary="Demander réinitialisation (envoi CODE pour MOBILE)"
)
def forgot_password_mobile_code(
    reset_request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks
):
    try:
        user_res = supabase.table("utilisateurs") \
            .select("id, email") \
            .eq("email", reset_request.email) \
            .single() \
            .execute()

        if not user_res.data:
            print(f"DEBUG: Tentative de réinitialisation (code) pour {reset_request.email} (utilisateur non trouvé).")
            # Pour des raisons de sécurité, ne pas indiquer si l'email existe ou non
            return {"message": "Si un compte avec cet email existe, un code de vérification a été envoyé."}

        # Générer un code OTP numérique (par exemple, 8 chiffres)
        verification_code = ''.join(secrets.choice('0123456789') for _ in range(8))
        print(f"DEBUG: Code de vérification généré pour {reset_request.email}: {verification_code}")

        # Hacher le code avant de le stocker pour la sécurité
        code_hash = hashlib.sha256(verification_code.encode('utf-8')).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Mettre à jour la BDD avec le code hashé et sa date d’expiration
        supabase.table("utilisateurs").update({
            "reset_token": code_hash,
            "reset_token_expires": expires_at.isoformat()
        }).eq("email", reset_request.email).execute()

        # Envoyer le code en arrière-plan
        background_tasks.add_task(
            send_password_reset_code_email,
            user_email=reset_request.email,
            verification_code=verification_code
        )

        return {"message": "Si un compte avec cet email existe, un code de vérification a été envoyé."}

    except Exception as e:
        print(f"Forgot password error (code generation): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur interne est survenue. Veuillez réessayer plus tard."
        )


@router.post(
    "/reset-password-with-code",
    status_code=status.HTTP_200_OK,
    summary="Réinitialiser le mot de passe avec le code mobile"
)
def reset_password_with_code(request: ResetPasswordCodeRequest):
    """
    Vérifie le code reçu par email et réinitialise le mot de passe de l'utilisateur.
    """
    try:
        # 1. Hacher le code reçu pour le comparer à celui dans la BDD
        code_hash = hashlib.sha256(request.code.encode('utf-8')).hexdigest()

        # 2. Vérifier que l'email et le code haché correspondent ET que le jeton n'est pas expiré
        now_utc = datetime.now(timezone.utc)

        user_res = supabase.table("utilisateurs").select("*") \
            .eq("email", request.email) \
            .eq("reset_token", code_hash) \
            .gt("reset_token_expires", now_utc.isoformat()) \
            .single().execute()

        if not user_res.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le code de vérification est invalide ou a expiré."
            )

        user = user_res.data

        # 3. Hacher le nouveau mot de passe
        new_password_hash = hash_password(request.new_password)

        # 4. Mettre à jour le mot de passe et effacer les jetons de réinitialisation
        supabase.table("utilisateurs").update({
            "mot_de_passe_hash": new_password_hash,
            "reset_token": None,
            "reset_token_expires": None
        }).eq("id", user['id']).execute()

        return {"message": "Votre mot de passe a été réinitialisé avec succès."}

    except HTTPException as http_exc:
        raise http_exc

    except Exception as e:
        print(f"Erreur de réinitialisation du mot de passe avec code : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Une erreur interne est survenue lors de la réinitialisation."
        )

