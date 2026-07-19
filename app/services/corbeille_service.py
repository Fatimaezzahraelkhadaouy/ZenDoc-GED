from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Document
from app.services.historique_service import enregistrer_action


def supprimer_document(db: Session, document_id: int, utilisateur_id: int, role: str = "utilisateur") -> Document:
    """
    Suppression douce : marque le document comme supprimé
    au lieu de l'effacer définitivement.
    Un utilisateur non-admin ne peut supprimer que ses propres documents.
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise ValueError(f"Document avec l'id {document_id} introuvable.")

    if role != "admin" and document.uploaded_by != utilisateur_id:
        raise PermissionError("Vous n'avez pas le droit de supprimer ce document.")

    if document.date_suppression is not None:
        raise ValueError("Ce document est déjà dans la corbeille.")

    document.date_suppression = datetime.utcnow()
    db.commit()

    enregistrer_action(
        db=db,
        utilisateur_id=utilisateur_id,
        action="suppression",
        document_id=document.id,
        details=f"Déplacement de '{document.nom_original}' vers la corbeille"
    )

    return document


def restaurer_document(db: Session, document_id: int, utilisateur_id: int, role: str = "utilisateur") -> Document:
    """
    Restaure un document depuis la corbeille.
    Un utilisateur non-admin ne peut restaurer que ses propres documents.
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise ValueError(f"Document avec l'id {document_id} introuvable.")

    if role != "admin" and document.uploaded_by != utilisateur_id:
        raise PermissionError("Vous n'avez pas le droit de restaurer ce document.")

    if document.date_suppression is None:
        raise ValueError("Ce document n'est pas dans la corbeille.")

    document.date_suppression = None
    db.commit()

    enregistrer_action(
        db=db,
        utilisateur_id=utilisateur_id,
        action="modification",
        document_id=document.id,
        details=f"Restauration de '{document.nom_original}' depuis la corbeille"
    )

    return document


def get_documents_actifs(db: Session, categorie_id: int = None, utilisateur_id: int = None, role: str = None):
    """
    Retourne les documents NON supprimés.
    Si role != 'admin' et utilisateur_id est fourni, ne retourne que les
    documents de cet utilisateur. Sans utilisateur_id (ex. dashboard global),
    retourne tout.
    """
    requete = db.query(Document).filter(Document.date_suppression.is_(None))

    if categorie_id:
        requete = requete.filter(Document.categorie_id == categorie_id)

    if role != "admin" and utilisateur_id is not None:
        requete = requete.filter(Document.uploaded_by == utilisateur_id)

    return requete.order_by(Document.date_upload.desc()).all()


def get_documents_corbeille(db: Session, utilisateur_id: int = None, role: str = None):
    """
    Retourne les documents dans la corbeille.
    Filtré par utilisateur si non-admin.
    """
    requete = db.query(Document).filter(Document.date_suppression.isnot(None))

    if role != "admin" and utilisateur_id is not None:
        requete = requete.filter(Document.uploaded_by == utilisateur_id)

    return requete.order_by(Document.date_suppression.desc()).all()


def supprimer_definitivement(db: Session, document_id: int, utilisateur_id: int, role: str = "utilisateur"):
    """
    Suppression définitive et irréversible (uniquement pour un document
    déjà dans la corbeille, par sécurité).
    Un utilisateur non-admin ne peut supprimer définitivement que ses propres documents.
    """
    import os
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise ValueError(f"Document avec l'id {document_id} introuvable.")

    if role != "admin" and document.uploaded_by != utilisateur_id:
        raise PermissionError("Vous n'avez pas le droit de supprimer définitivement ce document.")

    if document.date_suppression is None:
        raise ValueError("Le document doit d'abord être dans la corbeille avant suppression définitive.")

    nom_fichier = document.nom_original

    # Supprimer le fichier physique s'il existe
    if os.path.exists(document.chemin_fichier):
        os.remove(document.chemin_fichier)

    db.delete(document)
    db.commit()

    enregistrer_action(
        db=db,
        utilisateur_id=utilisateur_id,
        action="suppression",
        document_id=None,
        details=f"Suppression définitive de '{nom_fichier}'"
    )