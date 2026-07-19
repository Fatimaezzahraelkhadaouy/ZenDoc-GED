import chromadb
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.services.historique_service import enregistrer_action

load_dotenv()
client_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

CHROMA_DIR = "data/chroma_db"

client_chroma = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client_chroma.get_or_create_collection(name="documents")


def get_embedding(texte: str, task_type: str = "RETRIEVAL_DOCUMENT"):
    """
    Utilise l'API Gemini pour transformer un texte en embedding
    (liste de nombres représentant son sens).
    """
    resultat = client_gemini.models.embed_content(
        model="gemini-embedding-001",
        contents=texte,
        config=types.EmbedContentConfig(task_type=task_type)
    )
    return resultat.embeddings[0].values


def add_document_to_index(document_id: int, texte: str, nom_fichier: str):
    """
    Ajoute un document à l'index de recherche sémantique.
    """
    texte_limite = texte[:8000]
    embedding = get_embedding(texte_limite, task_type="RETRIEVAL_DOCUMENT")

    collection.add(
        ids=[str(document_id)],
        embeddings=[embedding],
        documents=[texte_limite],
        metadatas=[{"nom_fichier": nom_fichier}]
    )

    return f"doc_{document_id}"


def search_documents(query: str, utilisateur_id: int, db: Session = None, n_results: int = 5):
    """
    Recherche les documents les plus proches en sens de la requête.
    Enregistre l'action dans l'historique si une session db est fournie.
    """
    query_embedding = get_embedding(query, task_type="RETRIEVAL_QUERY")

    resultats = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )

    if db is not None:
        enregistrer_action(
            db=db,
            utilisateur_id=utilisateur_id,
            action="recherche",
            details=f"Recherche : '{query}'"
        )

    return resultats