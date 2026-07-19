from app.db.database import SessionLocal
from app.db.models import Category

# Ces catégories correspondent exactement à celles utilisées par l'IA
# dans ai_service.py (CATEGORIES_DISPONIBLES)
CATEGORIES_DE_BASE = [
    {"nom": "Cours / Formation", "description": "Supports de cours, syllabus, formations", "couleur": "#4A90D9"},
    {"nom": "Facture", "description": "Factures et documents comptables", "couleur": "#E67E22"},
    {"nom": "Contrat", "description": "Contrats et accords légaux", "couleur": "#8E44AD"},
    {"nom": "Rapport", "description": "Rapports d'activité, d'analyse, de stage", "couleur": "#27AE60"},
    {"nom": "Correspondance / Email", "description": "Emails et courriers", "couleur": "#3498DB"},
    {"nom": "Ressources Humaines", "description": "Documents RH, contrats de travail", "couleur": "#E74C3C"},
    {"nom": "Administratif", "description": "Documents administratifs divers", "couleur": "#95A5A6"},
    {"nom": "Autre", "description": "Documents non classés", "couleur": "#7F8C8D"},
]


def peupler_categories():
    """
    Crée les catégories de base si elles n'existent pas déjà.
    """
    db = SessionLocal()

    for cat_data in CATEGORIES_DE_BASE:
        existe = db.query(Category).filter(Category.nom == cat_data["nom"]).first()
        if not existe:
            nouvelle_categorie = Category(
                nom=cat_data["nom"],
                description=cat_data["description"],
                couleur=cat_data["couleur"]
            )
            db.add(nouvelle_categorie)
            print(f"✅ Catégorie créée : {cat_data['nom']}")
        else:
            print(f"ℹ️ Catégorie déjà existante : {cat_data['nom']}")

    db.commit()
    db.close()


def get_categorie_id_par_nom(db, nom_categorie: str) -> int:
    """
    Retourne l'id d'une catégorie à partir de son nom.
    Utile pour lier le résultat de l'IA (qui donne un nom) à la vraie table.
    """
    categorie = db.query(Category).filter(Category.nom == nom_categorie).first()
    if categorie:
        return categorie.id
    # Si jamais la catégorie n'existe pas, on retourne "Autre"
    categorie_autre = db.query(Category).filter(Category.nom == "Autre").first()
    return categorie_autre.id if categorie_autre else None