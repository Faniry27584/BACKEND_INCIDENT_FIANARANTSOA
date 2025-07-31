import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Récupérer les informations de connexion depuis les variables d'environnement
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")

# Vérifier si les variables sont bien définies
if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY doit inclus dans le fichier .env")

# Créer une instance unique du client Supabase
# Cette instance sera importée et utilisée dans tout le projet
supabase: Client = create_client(supabase_url, supabase_key)

print("Supabase client initialized successfully.")
