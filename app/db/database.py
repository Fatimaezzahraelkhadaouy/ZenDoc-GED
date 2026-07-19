from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base

# Chemin vers le fichier de base de données SQLite
DATABASE_URL = "sqlite:///./data/ged.db"

# Création du moteur de connexion
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Création d'une "fabrique" de sessions (pour interagir avec la BDD)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Crée toutes les tables dans la base de données si elles n'existent pas."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Fournit une session de base de données, utilisée dans toute l'application."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()