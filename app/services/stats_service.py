from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Document, Category, Historique, User


def get_statistiques_generales(db: Session) -> dict:
    """
    Calcule les statistiques générales de l'application.
    """
    total_documents = db.query(func.count(Document.id)).scalar()
    total_utilisateurs = db.query(func.count(User.id)).filter(User.actif == True).scalar()
    total_actions = db.query(func.count(Historique.id)).scalar()

    # Taille totale occupée (en Ko puis convertie en Mo)
    taille_totale_ko = db.query(func.sum(Document.taille)).scalar() or 0
    taille_totale_mo = round(taille_totale_ko / 1024, 2)

    return {
        "total_documents": total_documents or 0,
        "total_utilisateurs": total_utilisateurs or 0,
        "total_actions": total_actions or 0,
        "taille_totale_mo": taille_totale_mo
    }


def get_repartition_par_categorie(db: Session) -> list:
    """
    Retourne le nombre de documents par catégorie.
    Utile pour un graphique en barres ou camembert.
    """
    resultats = (
        db.query(Category.nom, func.count(Document.id).label("nombre"))
        .outerjoin(Document, Document.categorie_id == Category.id)
        .group_by(Category.nom)
        .all()
    )

    return [{"categorie": nom, "nombre": nombre} for nom, nombre in resultats]


def get_actions_recentes(db: Session, limite: int = 10) -> list:
    """
    Retourne les dernières actions effectuées sur la plateforme,
    tous utilisateurs confondus (utile pour un admin).
    """
    resultats = (
        db.query(Historique, User.nom_complet)
        .join(User, Historique.utilisateur_id == User.id)
        .order_by(Historique.date_action.desc())
        .limit(limite)
        .all()
    )

    return [
        {
            "date": entree.date_action.strftime("%Y-%m-%d %H:%M"),
            "utilisateur": nom_utilisateur,
            "action": entree.action,
            "details": entree.details
        }
        for entree, nom_utilisateur in resultats
    ]


def get_repartition_actions(db: Session) -> list:
    """
    Retourne le nombre d'occurrences de chaque type d'action
    (upload, recherche, téléchargement...).
    Utile pour visualiser l'usage global de l'application.
    """
    resultats = (
        db.query(Historique.action, func.count(Historique.id).label("nombre"))
        .group_by(Historique.action)
        .all()
    )

    return [{"action": action, "nombre": nombre} for action, nombre in resultats]