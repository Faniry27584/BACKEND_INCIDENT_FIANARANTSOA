import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from decouple import config
from typing import List, Dict

# Charger les variables d'environnement
SMTP_SERVER = config('SMTP_SERVER')
SMTP_PORT = config('SMTP_PORT', cast=int)
FROM_EMAIL = config('FROM_EMAIL')
PASSWORD = config('PASSWORD')

def send_email(to_email: str, subject: str, body: str):
    """
    Envoie un email via le serveur SMTP de Gmail.
    """
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(FROM_EMAIL, PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email envoyé avec succès à {to_email}")
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")
        return False

# --- Fonctions spécifiques pour chaque type de notification ---

def send_new_registration_to_admin(admin_email: str, new_user_email: str, new_user_role: str):
    """Notifie l'admin d'une nouvelle inscription à valider."""
    subject = "[GIF Mada] Nouvelle inscription en attente de validation"
    body = (
        f"Bonjour Administrateur,\n\n"
        f"Un nouvel utilisateur s'est inscrit et requiert votre validation.\n"
        f"  - Email: {new_user_email}\n"
        f"  - Rôle demandé: {new_user_role}\n\n"
        f"Veuillez vous connecter à votre tableau de bord pour l'approuver ou le rejeter.\n\n"
        f"L'équipe GIF Mada."
    )
    send_email(admin_email, subject, body)

def send_account_validated_to_user(user_email: str):
    """Informe un utilisateur que son compte a été validé."""
    subject = "[GIF Mada] Votre compte a été approuvé !"
    body = (
        f"Bonjour,\n\n"
        f"Bonne nouvelle ! Votre compte sur la plateforme de Gestion des Incidents de Fianarantsoa (GIF) a été validé par un administrateur.\n\n"
        f"Vous pouvez dès à présent vous connecter à l'application et utiliser toutes ses fonctionnalités.\n\n"
        f"Merci pour votre engagement pour la sécurité de notre ville.\n\n"
        f"L'équipe GIF Mada."
    )
    send_email(user_email, subject, body)

# MISE À JOUR : Remplacement de send_new_incident_to_authorities par une fonction plus complète
def send_new_incident_notification(recipient_emails: List[str], incident_title: str, incident_id: int, user_name: str, incident_description: str, fokontany_name: str):
    """Notifie toutes les parties prenantes d'un nouvel incident."""
    subject = f"[GIF Mada] Nouvel Incident Signalé: #{incident_id} - {incident_title}"
    body = (
        f"Bonjour,\n\n"
        f"Un nouvel incident a été signalé dans le Fokontany de {fokontany_name} et requiert votre attention.\n\n"
        f"  - Incident ID: {incident_id}\n"
        f"  - Titre: {incident_title}\n"
        f"  - Signalé par: {user_name}\n"
        f"  - Description: {incident_description}\n\n"
        f"Veuillez vous connecter à votre tableau de bord pour le consulter.\n\n"
        f"L'équipe GIF Mada."
    )
    for email in recipient_emails:
        send_email(email, subject, body)


def send_assignment_to_security(agent_email: str, incident_title: str, incident_id: int):
    """Informe un agent de sécurité qu'une nouvelle mission lui a été assignée."""
    subject = f"[GIF Mada] Nouvelle Mission Assignée: #{incident_id} - {incident_title}"
    body = (
        f"Bonjour,\n\n"
        f"Une nouvelle mission vous a été assignée.\n"
        f"  - Incident ID: {incident_id}\n"
        f"  - Titre de l'incident: {incident_title}\n\n"
        f"Veuillez consulter votre tableau de bord pour plus de détails et commencer l'intervention.\n\n"
        f"L'équipe GIF Mada."
    )
    send_email(agent_email, subject, body)

def send_panic_alert_notification(emails: List[str], incident_id: int, location: Dict):
    """Envoie une notification d'urgence pour le mode panique."""
    subject = f"--- ALERTE DANGER IMMÉDIAT --- Incident d'Urgence #{incident_id}"
    body = (
        f"!!! ATTENTION : ALERTE DANGER IMMÉDIAT !!!\n\n"
        f"Un utilisateur a activé le mode danger. Intervention immédiate requise.\n"
        f"  - Incident d'urgence ID: {incident_id}\n"
        f"  - Localisation approximative: Latitude {location['lat']}, Longitude {location['lng']}\n\n"
        f"Veuillez vous connectez immédiatement sur l'App Gif afin de l'assigné à un Sécurité Urbaine car Toutes les unités disponibles sont priées de consulter l'application pour les détails et de se rendre sur les lieux.\n\n"
        f"--- CECI EST UNE ALERTE AUTOMATISÉE DE HAUTE PRIORITÉ ---"
    )
    for email in emails:
        send_email(email, subject, body)

def send_password_reset_email(user_email: str, reset_token: str):
    """Envoie l'email contenant le lien de réinitialisation."""
    reset_url = f"http://localhost:3000/reset-password?token={reset_token}"
    subject = "[GIF Mada] Réinitialisation de votre mot de passe"
    body = (
        f"Bonjour,\n\n"
        f"Vous avez demandé une réinitialisation de votre mot de passe pour la plateforme GIF Mada.\n\n"
        f"Veuillez cliquer sur le lien ci-dessous pour créer un nouveau mot de passe :\n"
        f"{reset_url}\n\n"
        f"Ce lien expirera dans 15 minutes.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.\n\n"
        f"L'équipe GIF Mada."
    )
    send_email(user_email, subject, body)

def send_password_reset_code_email(user_email: str, verification_code: str):
    """Envoie l'email contenant le code de vérification pour la réinitialisation mobile."""
    subject = "[GIF Mada] Votre code de réinitialisation de mot de passe"
    body = (
        f"Bonjour,\n\n"
        f"Vous avez demandé une réinitialisation de votre mot de passe pour l'application mobile GIF Mada.\n\n"
        f"Votre code de vérification est : {verification_code}\n\n"
        f"Ce code expirera dans 15 minutes.\n\n"
        f"Veuillez entrer ce code dans l'application mobile pour définir un nouveau mot de passe.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.\n\n"
        f"L'équipe GIF Mada."
    )
    send_email(user_email, subject, body)
