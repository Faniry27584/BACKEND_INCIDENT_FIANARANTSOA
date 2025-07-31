# CHEMIN: backend/app/schemas/stats.py

from pydantic import BaseModel
from typing import List, Optional

class StatItem(BaseModel):
    """Représente une seule entrée de statistique (ex: 'Vol', 10)."""
    label: str
    value: int

class FokontanyStatsResponse(BaseModel):
    """Définit la structure complète des statistiques pour un Fokontany."""
    incidents_par_statut: List[StatItem]
    incidents_par_type: List[StatItem]

class AuthorityKPIsResponse(BaseModel): # Renommé pour plus de clarté
    """Définit les KPIs pour le tableau de bord de l'Autorité Locale."""
    incidents_a_valider: int
    agents_actifs: int
    temps_resolution_moyen_heures: Optional[float] = None

# NOUVEAU SCHÉMA POUR LA PAGE DE STATISTIQUES GLOBALES
class GlobalStatsResponse(BaseModel):
    """Définit la structure pour la page de statistiques de l'Autorité Locale."""
    incidents_par_statut: List[StatItem]
    incidents_par_type: List[StatItem]
    incidents_par_fokontany: List[StatItem]


    