import bcrypt
from sqlalchemy.orm import Session
from app.db.models import User


def hash_password(mot_de_passe: str) -> str:
    """
    Transforme un mot de passe en clair en un hash sécurisé
    (impossible à "dé-hasher", seulement à vérifier).
    """
    mot_de_passe_bytes = mot_de_passe.encode("utf-8")
    hash_bytes = bcrypt.hashpw(mot_de_passe_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")


def verifier_password(mot_de_passe: str, hash_stocke: str) -> bool:
    """
    Vérifie qu'un mot de passe en clair correspond bien au hash stocké.
    """
    return bcrypt.checkpw(
        mot_de_passe.encode("utf-8"),
        hash_stocke.encode("utf-8")
    )


def inscrire_utilisateur(db: Session, nom_complet: str, email: str, mot_de_passe: str, role: str = "utilisateur") -> User:
    """
    Crée un nouvel utilisateur avec mot de passe sécurisé.
    """
    # Vérifier que l'email n'existe pas déjà
    utilisateur_existant = db.query(User).filter(User.email == email).first()
    if utilisateur_existant:
        raise ValueError(f"Un utilisateur avec l'email '{email}' existe déjà.")

    mot_de_passe_hash = hash_password(mot_de_passe)

    nouvel_utilisateur = User(
        nom_complet=nom_complet,
        email=email,
        mot_de_passe=mot_de_passe_hash,
        role=role
    )

    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)

    return nouvel_utilisateur


def connecter_utilisateur(db: Session, email: str, mot_de_passe: str) -> User:
    """
    Vérifie les identifiants et retourne l'utilisateur si c'est correct.
    """
    utilisateur = db.query(User).filter(User.email == email).first()

    if not utilisateur:
        raise ValueError("Email ou mot de passe incorrect.")

    if not utilisateur.actif:
        raise ValueError("Ce compte a été désactivé.")

    if not verifier_password(mot_de_passe, utilisateur.mot_de_passe):
        raise ValueError("Email ou mot de passe incorrect.")

    return utilisateur


def verifier_permission(db: Session, utilisateur_id: int, categorie_id: int, action: str) -> bool:
    """
    Vérifie si un utilisateur a le droit de faire une action
    (lire / ajouter / supprimer) sur une catégorie donnée.
    Les admins ont toujours tous les droits.
    """
    from app.db.models import Permission

    utilisateur = db.query(User).filter(User.id == utilisateur_id).first()

    if utilisateur and utilisateur.role == "admin":
        return True

    permission = db.query(Permission).filter(
        Permission.utilisateur_id == utilisateur_id,
        Permission.categorie_id == categorie_id
    ).first()

    if not permission:
        return False

    if action == "lire":
        return permission.peut_lire
    elif action == "ajouter":
        return permission.peut_ajouter
    elif action == "supprimer":
        return permission.peut_supprimer

    return False