from sqlalchemy.orm import Session
from app.db.models import Historique


def enregistrer_action(
    db: Session,
    utilisateur_id: int,
    action: str,
    document_id: int = None,
    details: str = None
):
    """
    Enregistre une action dans l'historique.

    Actions possibles : "upload", "recherche", "telechargement",
    "suppression", "modification", "connexion"
    """
    nouvelle_entree = Historique(
        utilisateur_id=utilisateur_id,
        document_id=document_id,
        action=action,
        details=details
    )

    db.add(nouvelle_entree)
    db.commit()

    return nouvelle_entree


def get_historique_utilisateur(db: Session, utilisateur_id: int, limite: int = 20):
    """
    Récupère les dernières actions d'un utilisateur, les plus récentes d'abord.
    """
    return (
        db.query(Historique)
        .filter(Historique.utilisateur_id == utilisateur_id)
        .order_by(Historique.date_action.desc())
        .limit(limite)
        .all()
    )


def get_historique_complet(db: Session, limite: int = 50):
    """
    Récupère l'historique complet (utile pour un admin), le plus récent d'abord.
    """
    return (
        db.query(Historique)
        .order_by(Historique.date_action.desc())
        .limit(limite)
        .all()
    )