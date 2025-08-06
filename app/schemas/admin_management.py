# backend/app/schemas/admin_management.py
# FICHIER MIS À JOUR

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from uuid import UUID

# --- Schémas pour la gestion des Fokontany ---

class FokontanyBase(BaseModel):
    """Schéma de base pour un Fokontany."""
    nom_fokontany: str = Field(..., min_length=3, description="Nom du Fokontany")
    latitude: Optional[float] = Field(None, description="Latitude du centre du Fokontany")
    longitude: Optional[float] = Field(None, description="Longitude du centre du Fokontany")
    radius: Optional[float] = Field(None, description="Rayon en mètres pour délimiter la zone du Fokontany")

class FokontanyCreate(FokontanyBase):
    """Schéma pour la création d'un Fokontany."""
    pass

class FokontanyUpdate(BaseModel):
    """Schéma pour la mise à jour d'un Fokontany (tous les champs sont optionnels)."""
    nom_fokontany: Optional[str] = Field(None, min_length=3)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius: Optional[float] = None

class FokontanyResponse(FokontanyBase):
    """Schéma de réponse complet pour un Fokontany, incluant l'ID."""
    id: int

    class Config:
        from_attributes = True

# --- Schémas pour la gestion des Postes de Sécurité ---

class PosteSecuriteBase(BaseModel):
    """Schéma de base pour un Poste de Sécurité."""
    nom_poste: str = Field(..., min_length=3, description="Nom du poste (ex: Gendarmerie Nationale)")
    description: Optional[str] = Field(None, description="Description des responsabilités du poste")

class PosteSecuriteCreate(PosteSecuriteBase):
    """Schéma pour la création d'un Poste de Sécurité."""
    pass

class PosteSecuriteUpdate(BaseModel):
    """Schéma pour la mise à jour d'un Poste de Sécurité."""
    nom_poste: Optional[str] = Field(None, min_length=3)
    description: Optional[str] = None

class PosteSecuriteResponse(PosteSecuriteBase):
    """Schéma de réponse complet pour un Poste de Sécurité."""
    id: int

    class Config:
        from_attributes = True

# --- NOUVEAUX SCHÉMAS : Gestion des Utilisateurs par l'Admin ---

class AdminUserCreate(BaseModel):
    """Schéma pour la création d'un utilisateur par un admin."""
    email: EmailStr
    mot_de_passe: str = Field(..., min_length=8)
    nom: str
    prenom: str
    telephone: str
    role: str
    fokontany_id: Optional[int] = None
    poste_securite_id: Optional[int] = None
    est_verifie: bool = Field(True, description="Le compte est-il vérifié dès la création ?")

class AdminUserUpdate(BaseModel):
    """Schéma pour la mise à jour d'un utilisateur par un admin."""
    nom: Optional[str] = None
    prenom: Optional[str] = None
    telephone: Optional[str] = None
    role: Optional[str] = None
    fokontany_id: Optional[int] = None
    poste_securite_id: Optional[int] = None
    est_verifie: Optional[bool] = None
    # L'email et le mot de passe ne sont pas modifiables directement ici pour la sécurité
