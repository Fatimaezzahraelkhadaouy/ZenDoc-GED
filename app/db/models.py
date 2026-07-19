from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    nom_complet = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    mot_de_passe = Column(String(255), nullable=False)
    role = Column(String(20), default="utilisateur")
    date_creation = Column(DateTime, default=datetime.utcnow)
    actif = Column(Boolean, default=True)

    documents = relationship("Document", back_populates="uploader")
    historique = relationship("Historique", back_populates="utilisateur")
    permissions = relationship("Permission", back_populates="utilisateur")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    description = Column(String(255))
    couleur = Column(String(20), default="#4A90D9")

    documents = relationship("Document", back_populates="categorie")
    permissions = relationship("Permission", back_populates="categorie")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    nom_original = Column(String(255), nullable=False)
    chemin_fichier = Column(String(500), nullable=False)
    type_fichier = Column(String(20))
    taille = Column(Integer)
    categorie_id = Column(Integer, ForeignKey("categories.id"))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    date_upload = Column(DateTime, default=datetime.utcnow)
    date_suppression = Column(DateTime, nullable=True)
    resume_ia = Column(Text)
    contenu_extrait = Column(Text)
    embedding_id = Column(String(100))

    categorie = relationship("Category", back_populates="documents")
    uploader = relationship("User", back_populates="documents")
    tags = relationship("DocumentTag", back_populates="document")
    historique = relationship("Historique", back_populates="document")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    nom = Column(String(50), unique=True, nullable=False)

    documents = relationship("DocumentTag", back_populates="tag")


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id = Column(Integer, ForeignKey("documents.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    document = relationship("Document", back_populates="tags")
    tag = relationship("Tag", back_populates="documents")


class Historique(Base):
    __tablename__ = "historique"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("users.id"))
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    action = Column(String(50))
    details = Column(String(255))
    date_action = Column(DateTime, default=datetime.utcnow)

    utilisateur = relationship("User", back_populates="historique")
    document = relationship("Document", back_populates="historique")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("users.id"))
    categorie_id = Column(Integer, ForeignKey("categories.id"))
    peut_lire = Column(Boolean, default=True)
    peut_ajouter = Column(Boolean, default=False)
    peut_supprimer = Column(Boolean, default=False)

    utilisateur = relationship("User", back_populates="permissions")
    categorie = relationship("Category", back_populates="permissions")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("users.id"))
    question = Column(Text)
    reponse = Column(Text)
    score_ia = Column(Integer)
    feedback_utilisateur = Column(Boolean, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)