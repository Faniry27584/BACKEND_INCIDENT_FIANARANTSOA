import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from typing import Dict, List, Set
import os
from dotenv import load_dotenv
from jose import jwt, JWTError
from .routers import auth, fokontany, admin, incidents, users, authority, security, postes, stats, history, incident_types
from .utils import socket_events
from fastapi.openapi.utils import get_openapi

load_dotenv()

ALLOWED_ORIGINS = [
    "*"
    ""  # Mise à jour pour correspondre à votre frontend et le vercel en production
]

app = FastAPI(
    title="API pour la Gestion des Incidents à Fianarantsoa",
    description="Cette API gère toutes les opérations pour l'application web et mobile.",
    version="0.1.0"
)
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Ton API",
        version="1.0.0",
        description="API avec Auth Bearer",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
FROM_EMAIL = os.getenv("FROM_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_PASSWORD = os.getenv("PASSWORD")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([SECRET_KEY, ALGORITHM, FROM_EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_PASSWORD, SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Les variables d'environnement essentielles doivent être définies dans le fichier .env.")

from supabase import create_client, Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

active_websockets_by_user_id: Dict[str, WebSocket] = {}
active_websockets_by_fokontany: Dict[int, Set[str]] = {}
active_websockets_by_role: Dict[str, Set[str]] = {
    "AUTORITE_LOCALE": set(),
    "SECURITE_URBAINE": set(),
    "CHEF_FOKONTANY": set(),
    "CITOYEN": set(),
    "ADMIN": set(),
}

async def get_user_data_from_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email = payload.get("sub")
        if user_email is None:
            return None
        response = supabase.table("utilisateurs").select("id, role, fokontany_id, nom, prenom").eq("email", user_email).single().execute()
        if response.data:
            return response.data
        return None
    except JWTError as e:
        print(f"Erreur JWT lors du décodage du token: {e}")
        return None
    except Exception as e:
        print(f"Erreur lors de la récupération de l'utilisateur depuis la base de données: {e}")
        return None

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await websocket.accept()
    user_data = None
    user_id = None
    user_role = None
    fokontany_id = None
    try:
        user_data = await get_user_data_from_token(token)
        if not user_data:
            print(f"Connexion WebSocket refusée pour token invalide.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        user_id = user_data['id']
        user_role = user_data['role']
        fokontany_id = user_data.get('fokontany_id')
        
        active_websockets_by_user_id[user_id] = websocket

        if user_role in active_websockets_by_role:
            active_websockets_by_role[user_role].add(user_id)
            print(f"Client {user_id} (rôle: {user_role}) a rejoint la room '{user_role}'")
        
        if user_role == "CHEF_FOKONTANY" and fokontany_id:
            if fokontany_id not in active_websockets_by_fokontany:
                active_websockets_by_fokontany[fokontany_id] = set()
            active_websockets_by_fokontany[fokontany_id].add(user_id)
            print(f"Client {user_id} (rôle: CHEF_FOKONTANY) a rejoint la room 'fokontany_{fokontany_id}'")

        print(f"Client WebSocket connecté: {user_id} (Rôle: {user_role}, Fokontany: {fokontany_id if fokontany_id else 'N/A'})")
        
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        print(f"Client WebSocket déconnecté: {user_id}")
    except Exception as e:
        print(f"Erreur inattendue sur WebSocket pour {user_id}: {e}")
    finally:
        if user_id in active_websockets_by_user_id:
            del active_websockets_by_user_id[user_id]
        if user_role and user_role in active_websockets_by_role and user_id in active_websockets_by_role[user_role]:
            active_websockets_by_role[user_role].remove(user_id)
        if fokontany_id and fokontany_id in active_websockets_by_fokontany:
            if user_id in active_websockets_by_fokontany[fokontany_id]:
                active_websockets_by_fokontany[fokontany_id].remove(user_id)
            if not active_websockets_by_fokontany[fokontany_id]:
                del active_websockets_by_fokontany[fokontany_id]

async def _broadcast_panic_alert_impl(incident_data: dict):
    users_to_notify_uniquely = set()
    roles_globaux_a_notifier = ["AUTORITE_LOCALE", "SECURITE_URBAINE"]
    for role in roles_globaux_a_notifier:
        users_to_notify_uniquely.update(active_websockets_by_role.get(role, set()))

    fokontany_id_incident = incident_data.get('fokontany_id')
    if fokontany_id_incident:
        try:
            res_chefs_fokontany_db = supabase.table("utilisateurs") \
                .select("id") \
                .eq("role", "CHEF_FOKONTANY") \
                .eq("fokontany_id", fokontany_id_incident) \
                .execute()
            if res_chefs_fokontany_db.data:
                chefs_fokontany_incident_db_ids = {u['id'] for u in res_chefs_fokontany_db.data}
                connected_and_relevant_chefs = active_websockets_by_role.get("CHEF_FOKONTANY", set()).intersection(chefs_fokontany_incident_db_ids)
                users_to_notify_uniquely.update(connected_and_relevant_chefs)
        except Exception as e:
            print(f"Erreur lors de la récupération des Chefs Fokontany: {e}")

    notified_count = 0
    message_id = str(uuid.uuid4())  # Génération d’un ID unique pour chaque notification
    print(f"Tentative de diffusion de l'alerte à {len(users_to_notify_uniquely)} utilisateurs uniques.")
    for user_id in users_to_notify_uniquely:
        websocket = active_websockets_by_user_id.get(user_id)
        if websocket and user_id in active_websockets_by_user_id:
            try:
                await websocket.send_json({"type": "panic_alert", "data": incident_data, "message_id": message_id})
                notified_count += 1
                print(f"Notification envoyée avec succès à l'utilisateur {user_id} avec message_id: {message_id}")
            except Exception as e:
                print(f"Erreur d'envoi WebSocket à l'utilisateur {user_id}: {e}")
        else:
            print(f"Utilisateur {user_id} n'a pas de connexion WebSocket active.")
    print(f"Alerte diffusée pour incident ID: {incident_data.get('id')}. Utilisateurs notifiés: {notified_count}")

socket_events.broadcast_panic_alert = _broadcast_panic_alert_impl

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Bienvenue sur l'API de Gestion des Incidents de Fianarantsoa!"}

# Routeur du Backend
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentification"])
app.include_router(fokontany.router, prefix="/api/v1/fokontany", tags=["Fokontany"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Administration"])
app.include_router(incidents.router, prefix="/api/v1/incidents", tags=["Incidents"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Utilisateurs"])
app.include_router(authority.router, prefix="/api/v1/authority", tags=["Autorité Locale"])
app.include_router(security.router, prefix="/api/v1/security", tags=["Sécurité Urbaine"])
app.include_router(postes.router, prefix="/api/v1/postes", tags=["Postes de Sécurité"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Statistiques"])
app.include_router(history.router, prefix="/api/v1/history", tags=["Historique"])
app.include_router(incident_types.router, prefix="/api/v1/admin/incident-types", tags=["Admin - Gestion des Types d'Incidents"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)