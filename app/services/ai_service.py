from google import genai
import os
import json
from dotenv import load_dotenv
import time
load_dotenv()
client_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Liste des catégories possibles (tu peux l'adapter à ton contexte)
CATEGORIES_DISPONIBLES = [
    "Cours / Formation",
    "Facture",
    "Contrat",
    "Rapport",
    "Correspondance / Email",
    "Ressources Humaines",
    "Administratif",
    "Autre"
]


def generer_resume(texte: str, tentatives: int = 3) -> str:
    """
    Demande à Gemini de générer un résumé court (3-4 phrases) du document.
    Réessaie automatiquement en cas de surcharge du serveur.
    """
    texte_limite = texte[:10000]

    prompt = f"""Voici le contenu d'un document. Résume-le en 3 à 4 phrases claires et concises, en français.

Document :
{texte_limite}

Résumé :"""

    for tentative in range(tentatives):
        try:
            response = client_gemini.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            if tentative < tentatives - 1:
                print(f"⚠️ Serveur occupé, nouvelle tentative dans 5s... ({tentative + 1}/{tentatives})")
                time.sleep(5)
            else:
                raise e

def classifier_document(texte: str, tentatives: int = 3) -> str:
    """
    Demande à Gemini de choisir la catégorie la plus adaptée
    parmi une liste prédéfinie. Réessaie automatiquement en cas de surcharge.
    """
    texte_limite = texte[:5000]
    categories_str = ", ".join(CATEGORIES_DISPONIBLES)

    prompt = f"""Voici le contenu d'un document. Choisis UNE SEULE catégorie parmi cette liste qui correspond le mieux : {categories_str}

Document :
{texte_limite}

Réponds uniquement avec le nom exact de la catégorie, rien d'autre."""

    for tentative in range(tentatives):
        try:
            response = client_gemini.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt
            )
            categorie = response.text.strip()
            if categorie not in CATEGORIES_DISPONIBLES:
                categorie = "Autre"
            return categorie
        except Exception as e:
            if tentative < tentatives - 1:
                print(f"⚠️ Serveur occupé, nouvelle tentative dans 5s... ({tentative + 1}/{tentatives})")
                time.sleep(5)
            else:
                raise e


def analyser_document(texte: str) -> dict:
    """
    Fait les deux opérations d'un coup : résumé + classification.
    """
    resume = generer_resume(texte)
    categorie = classifier_document(texte)

    return {
        "resume": resume,
        "categorie": categorie
    }