import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from app.services.search_service import search_documents
from app.db.models import Feedback

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3
)

prompt_template = ChatPromptTemplate.from_template("""
Tu es un assistant qui répond aux questions en te basant UNIQUEMENT sur le contexte fourni ci-dessous,
extrait des documents de l'utilisateur. Si l'information n'est pas dans le contexte, dis clairement
que tu ne trouves pas la réponse dans les documents disponibles. Réponds en français, de façon claire et concise.

Contexte (extrait des documents) :
{contexte}

Question : {question}

Réponse :
""")

# Prompt utilisé pour l'auto-évaluation ("LLM-as-judge")
prompt_evaluation = ChatPromptTemplate.from_template("""
Voici une question, le contexte utilisé, et la réponse générée par une IA.
Évalue la qualité de cette réponse sur une échelle de 1 à 5, où :
1 = la réponse est hors-sujet ou fausse par rapport au contexte
5 = la réponse est précise, pertinente et bien fondée sur le contexte

Contexte : {contexte}
Question : {question}
Réponse générée : {reponse}

Réponds UNIQUEMENT avec un chiffre entre 1 et 5, rien d'autre.
""")


def extraire_texte(contenu) -> str:
    """Fonction utilitaire pour extraire du texte propre, peu importe le format retourné."""
    if isinstance(contenu, list):
        return "".join(bloc.get("text", "") for bloc in contenu if isinstance(bloc, dict)).strip()
    return str(contenu).strip()


def evaluer_reponse(contexte: str, question: str, reponse: str) -> int:
    """
    Demande à Gemini d'évaluer la qualité de sa propre réponse (1 à 5).
    """
    try:
        chaine_eval = prompt_evaluation | llm
        resultat = chaine_eval.invoke({
            "contexte": contexte,
            "question": question,
            "reponse": reponse
        })
        texte = extraire_texte(resultat.content)
        score = int("".join(filter(str.isdigit, texte))[:1])
        return max(1, min(5, score))  # sécurité : toujours entre 1 et 5
    except Exception:
        return 3  # valeur neutre par défaut en cas d'erreur d'évaluation


def poser_question(question: str, utilisateur_id: int, db: Session = None, n_documents: int = 3) -> dict:
    """
    Pose une question en langage naturel, obtient une réponse générée (RAG),
    et l'IA s'auto-évalue sur la qualité de sa réponse.
    """
    resultats = search_documents(
        query=question,
        utilisateur_id=utilisateur_id,
        db=db,
        n_results=n_documents
    )

    documents_trouves = resultats["documents"][0]
    noms_fichiers = [meta["nom_fichier"] for meta in resultats["metadatas"][0]]

    if not documents_trouves:
        return {
            "reponse": "Aucun document pertinent n'a été trouvé pour répondre à cette question.",
            "sources": [],
            "score_ia": None,
            "feedback_id": None
        }

    contexte = "\n\n---\n\n".join(documents_trouves)

    chaine = prompt_template | llm
    resultat = chaine.invoke({"contexte": contexte, "question": question})
    texte_reponse = extraire_texte(resultat.content)

    # Auto-évaluation de la réponse par l'IA
    score_ia = evaluer_reponse(contexte, question, texte_reponse)

    feedback_id = None
    if db is not None:
        nouveau_feedback = Feedback(
            utilisateur_id=utilisateur_id,
            question=question,
            reponse=texte_reponse,
            score_ia=score_ia
        )
        db.add(nouveau_feedback)
        db.commit()
        db.refresh(nouveau_feedback)
        feedback_id = nouveau_feedback.id

    return {
        "reponse": texte_reponse,
        "sources": list(set(noms_fichiers)),
        "score_ia": score_ia,
        "feedback_id": feedback_id
    }


def enregistrer_feedback_utilisateur(db: Session, feedback_id: int, positif: bool):
    """
    Enregistre le retour de l'utilisateur (👍 ou 👎) sur une réponse donnée.
    """
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise ValueError(f"Feedback avec l'id {feedback_id} introuvable.")

    feedback.feedback_utilisateur = positif
    db.commit()
    return feedback