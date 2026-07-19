from app.db.database import init_db, SessionLocal
from app.db.models import User
from app.services.rag_service import poser_question, enregistrer_feedback_utilisateur

if __name__ == "__main__":
    init_db()
    db = SessionLocal()

    utilisateur = db.query(User).filter(User.email == "fatima.test@insea.ma").first()

    question = "Quels sont les outils méthodologiques essentiels de l'économie ?"
    print(f"💬 Question : {question}\n")

    resultat = poser_question(question=question, utilisateur_id=utilisateur.id, db=db)

    print(f"🤖 Réponse :\n{resultat['reponse']}")
    print(f"\n⭐ Score d'auto-évaluation IA : {resultat['score_ia']}/5")
    print(f"📄 Sources : {', '.join(resultat['sources'])}")
    print(f"🆔 ID du feedback : {resultat['feedback_id']}")

    # On simule un utilisateur qui donne un 👍
    if resultat["feedback_id"]:
        enregistrer_feedback_utilisateur(db, resultat["feedback_id"], positif=True)
        print("\n✅ Feedback utilisateur (👍) enregistré avec succès !")

    db.close()