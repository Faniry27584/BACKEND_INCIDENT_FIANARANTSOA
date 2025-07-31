import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from ..schemas.users import TokenData
from ..database.database import supabase
from ..schemas.users import UserResponse # Importer UserResponse
# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# Ce schéma indique à FastAPI de chercher le token dans l'en-tête "Authorization: Bearer <token>"
# L'URL "tokenUrl" pointe vers notre endpoint de login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user_data(token: str = Depends(oauth2_scheme)) -> UserResponse:
    """
    Décode le token, puis récupère et retourne l'objet utilisateur complet depuis la BDD.
    Ceci remplace l'ancienne fonction get_current_user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les informations d'identification",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Récupérer l'utilisateur complet depuis la BDD
    response = supabase.table("utilisateurs").select("*").eq("email", email).single().execute()
    if not response.data:
        raise credentials_exception
        
    return UserResponse(**response.data)

def role_checker(required_role: str):
    """Vérifie si l'utilisateur a le rôle requis."""
    async def check_user_role(current_user: UserResponse = Depends(get_current_user_data)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôle '{required_role}' requis."
            )
        return current_user
    return check_user_role

# Création de dépendances spécifiques pour chaque rôle pour un code plus propre
# Note: Nous ajoutons le rôle 'ADMIN' ici.
# Assurez-vous d'avoir un utilisateur avec ce rôle dans votre base de données.
# ... et ainsi de suite pour les autres rôles
get_current_admin_user = role_checker("ADMIN")
get_current_citizen_user = role_checker("CITOYEN")
get_current_fokontany_chief_user = role_checker("CHEF_FOKONTANY")
get_current_fokontany_security_user = role_checker("SÉCURITÉ_URBAINE")
get_current_fokontany_autority_user = role_checker("AUTORITÉ_LOCALE")


