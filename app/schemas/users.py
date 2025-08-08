# CHEMIN : backend/app/schemas/users.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from uuid import UUID  # IMPORTANT : Importez UUID

# --- Schémas divers ---

class AdminKPIsResponse(BaseModel):
    utilisateurs_en_attente: int
    incidents_total: int
    incidents_aujourdhui: int

class PosteSecurite(BaseModel):
    nom_poste: str
    class Config:
        from_attributes = True

# --- Schémas Utilisateur ---

class UserCreate(BaseModel):
    nom: str = Field(..., min_length=2, description="Nom de famille de l'utilisateur")
    prenom: str = Field(..., min_length=2, description="Prénom de l'utilisateur")
    email: EmailStr = Field(..., description="Adresse e-mail unique de l'utilisateur")
    telephone: str = Field(..., min_length=10, description="Numéro de téléphone")
    mot_de_passe: Optional[str] = Field(None, min_length=8, description="Mot de passe (non requis pour l'auth Google)")
    role: str = Field(..., description="Rôle choisi : Citoyen, Chef Fokontany, etc.")
    fokontany_id: Optional[int] = Field(None, description="ID du Fokontany (si rôle est 'Chef Fokontany')")
    poste_securite_id: Optional[int] = Field(None, description="ID du poste (si rôle est 'Sécurité Urbaine')")

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: UUID
    nom: str
    prenom: str
    email: str
    role: Optional[str] = None  # Changement ici : role peut être None
    telephone: Optional[str] = None
    fokontany_id: Optional[int] = None
    poste_securite_id: Optional[int] = None
    est_verifie: bool
    photo_url: Optional[str] = None
    postes_securite: Optional[PosteSecurite] = None

    class Config:
        from_attributes = True
        json_encoders = {UUID: str}
        
class UserPhotoUpdate(BaseModel):
    photo_url: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[UUID] = None # <-- MODIFIÉ
    email: Optional[str] = None
    role: Optional[str] = None
    nom: Optional[str] = None
    prenom: Optional[str] = None

class UserUpdate(BaseModel):
    nom: Optional[str] = Field(None, min_length=2)
    prenom: Optional[str] = Field(None, min_length=2)
    telephone: Optional[str] = Field(None, min_length=10)

class PasswordUpdate(BaseModel):
    ancien_mot_de_passe: str
    nouveau_mot_de_passe: str = Field(..., min_length=8)

class UserProfileCompletion(BaseModel):
    telephone: str = Field(..., min_length=10)
    role: str
    fokontany_id: Optional[int] = None
    poste_securite_id: Optional[int] = None