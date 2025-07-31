# CHEMIN: backend/app/schemas/auth.py
# NOUVEAU FICHIER

from pydantic import BaseModel, EmailStr, Field

class ForgotPasswordRequest(BaseModel):
    """Schéma pour la demande de réinitialisation de mot de passe."""
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    """Schéma pour la soumission du nouveau mot de passe avec le token."""
    token: str
    new_password: str = Field(..., min_length=8, description="Le nouveau mot de passe doit contenir au moins 8 caractères.")

#Code pour l'APP mobile
class ResetPasswordCodeRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str