from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from app.db.database import SessionLocal
from app.services.auth_service import connecter_utilisateur, inscrire_utilisateur
from app.services.stats_service import (
    get_statistiques_generales,
    get_repartition_par_categorie,
    get_repartition_actions,
    get_actions_recentes
)
from app.services.document_service import create_document_entry, get_document_path
from app.services.ai_service import analyser_document
from app.services.search_service import add_document_to_index, search_documents
from app.services.rag_service import poser_question, enregistrer_feedback_utilisateur
from app.services.corbeille_service import (
    supprimer_document, restaurer_document,
    get_documents_actifs, get_documents_corbeille,
    supprimer_definitivement
)
from app.services.historique_service import get_historique_complet, get_historique_utilisateur
from app.db.seed_data import get_categorie_id_par_nom
import os

app = Flask(__name__)
app.secret_key = "cle_secrete_dev_a_changer_plus_tard"


@app.route("/")
def index():
    if "utilisateur_id" in session:
        return redirect(url_for("bienvenue"))
    return render_template("accueil.html")


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        email = request.form.get("email")
        mot_de_passe = request.form.get("mot_de_passe")

        db = SessionLocal()
        try:
            utilisateur = connecter_utilisateur(db, email, mot_de_passe)
            session["utilisateur_id"] = utilisateur.id
            session["utilisateur_nom"] = utilisateur.nom_complet
            session["utilisateur_role"] = utilisateur.role
            return redirect(url_for("bienvenue"))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("connexion"))
        finally:
            db.close()

    return render_template("connexion.html")


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if request.method == "POST":
        nom_complet = request.form.get("nom_complet")
        email = request.form.get("email")
        mot_de_passe = request.form.get("mot_de_passe")

        db = SessionLocal()
        try:
            inscrire_utilisateur(db, nom_complet, email, mot_de_passe, role="utilisateur")
            flash("✅ Compte créé avec succès ! Vous pouvez vous connecter.", "success")
            return redirect(url_for("connexion"))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("inscription"))
        finally:
            db.close()

    return render_template("inscription.html")


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


@app.route("/bienvenue")
def bienvenue():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        stats = get_statistiques_generales(db)
        actions_recentes = get_actions_recentes(db, limite=5)
        documents_recents = get_documents_actifs(db)[:3]

        heure = datetime.now().hour
        if heure < 12:
            salutation = "Bonjour"
        elif heure < 18:
            salutation = "Bon après-midi"
        else:
            salutation = "Bonsoir"

        return render_template(
            "bienvenue.html",
            nom=session.get("utilisateur_nom"),
            role=session.get("utilisateur_role"),
            stats=stats,
            salutation=salutation,
            actions_recentes=actions_recentes,
            documents_recents=documents_recents
        )
    finally:
        db.close()


@app.route("/dashboard")
def dashboard():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        stats = get_statistiques_generales(db)
        repartition_categories = get_repartition_par_categorie(db)
        repartition_actions = get_repartition_actions(db)

        categories_labels = [item["categorie"] for item in repartition_categories]
        categories_valeurs = [item["nombre"] for item in repartition_categories]
        actions_labels = [item["action"] for item in repartition_actions]
        actions_valeurs = [item["nombre"] for item in repartition_actions]
        actions_recentes = get_actions_recentes(db, limite=8)

        return render_template(
            "dashboard.html",
            actions_recentes=actions_recentes,
            nom=session.get("utilisateur_nom"),
            role=session.get("utilisateur_role"),
            stats=stats,
            categories_labels=categories_labels,
            categories_valeurs=categories_valeurs,
            actions_labels=actions_labels,
            actions_valeurs=actions_valeurs
        )
    finally:
        db.close()


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    resultat_analyse = None

    if request.method == "POST":
        fichier = request.files.get("fichier")

        if fichier and fichier.filename != "":
            db = SessionLocal()
            try:
                chemin_temp = os.path.join("data", "uploads", fichier.filename)
                os.makedirs(os.path.dirname(chemin_temp), exist_ok=True)
                fichier.save(chemin_temp)

                document = create_document_entry(
                    db=db,
                    file_path=chemin_temp,
                    original_filename=fichier.filename,
                    uploaded_by=session["utilisateur_id"]
                )

                analyse = analyser_document(document.contenu_extrait)
                categorie_id = get_categorie_id_par_nom(db, analyse["categorie"])
                document.resume_ia = analyse["resume"]
                document.categorie_id = categorie_id
                db.commit()

                add_document_to_index(
                    document_id=document.id,
                    texte=document.contenu_extrait,
                    nom_fichier=document.nom_original
                )

                resultat_analyse = {
                    "nom": document.nom_original,
                    "categorie": analyse["categorie"],
                    "resume": analyse["resume"]
                }
                flash("✅ Document déposé et analysé avec succès !", "success")
            except Exception as e:
                flash(f"❌ Erreur : {e}", "error")
            finally:
                db.close()
        else:
            flash("⚠️ Merci de sélectionner un fichier.", "error")

    return render_template(
        "upload.html",
        nom=session.get("utilisateur_nom"),
        role=session.get("utilisateur_role"),
        resultat_analyse=resultat_analyse
    )


@app.route("/recherche", methods=["GET", "POST"])
def recherche():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    resultats_affichage = None
    requete = ""

    if request.method == "POST":
        requete = request.form.get("requete", "")

        if requete.strip():
            db = SessionLocal()
            try:
                resultats = search_documents(
                    query=requete,
                    utilisateur_id=session["utilisateur_id"],
                    db=db,
                    n_results=5
                )

                resultats_affichage = []
                for i, doc_id in enumerate(resultats["ids"][0]):
                    nom = resultats["metadatas"][0][i]["nom_fichier"]
                    distance = resultats["distances"][0][i]
                    pertinence = round((1 - distance) * 100, 1)
                    resultats_affichage.append({"nom": nom, "pertinence": pertinence})
            except Exception as e:
                flash(f"❌ Erreur : {e}", "error")
            finally:
                db.close()
        else:
            flash("⚠️ Merci de saisir une recherche.", "error")

    return render_template(
        "recherche.html",
        nom=session.get("utilisateur_nom"),
        role=session.get("utilisateur_role"),
        resultats=resultats_affichage,
        requete=requete
    )


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    if "historique_chat" not in session:
        session["historique_chat"] = []

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if question:
            db = SessionLocal()
            try:
                resultat = poser_question(
                    question=question,
                    utilisateur_id=session["utilisateur_id"],
                    db=db
                )

                historique = session["historique_chat"]
                historique.append({
                    "question": question,
                    "reponse": resultat["reponse"],
                    "sources": resultat["sources"],
                    "score_ia": resultat["score_ia"],
                    "feedback_id": resultat["feedback_id"]
                })
                session["historique_chat"] = historique
            except Exception as e:
                flash(f"❌ Erreur : {e}", "error")
            finally:
                db.close()

    return render_template(
        "chat.html",
        nom=session.get("utilisateur_nom"),
        role=session.get("utilisateur_role"),
        historique=session.get("historique_chat", [])
    )


@app.route("/chat/feedback/<int:feedback_id>/<positif>")
def chat_feedback(feedback_id, positif):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        enregistrer_feedback_utilisateur(db, feedback_id, positif == "oui")
        flash("✅ Merci pour votre retour !", "success")
    except Exception as e:
        flash(f"❌ Erreur : {e}", "error")
    finally:
        db.close()

    return redirect(url_for("chat"))


@app.route("/documents")
def documents():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        docs = get_documents_actifs(
            db,
            utilisateur_id=session["utilisateur_id"],
            role=session.get("utilisateur_role")
        )
        return render_template(
            "documents.html",
            nom=session.get("utilisateur_nom"),
            role=session.get("utilisateur_role"),
            documents=docs
        )
    finally:
        db.close()


@app.route("/documents/voir/<int:document_id>")
def voir_document(document_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        chemin = get_document_path(
            db, document_id,
            session["utilisateur_id"],
            session.get("utilisateur_role")
        )
        return send_file(chemin)
    except (ValueError, FileNotFoundError, PermissionError) as e:
        flash(f"❌ {e}", "error")
        return redirect(url_for("documents"))
    finally:
        db.close()


@app.route("/documents/telecharger/<int:document_id>")
def telecharger_document(document_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        chemin = get_document_path(
            db, document_id,
            session["utilisateur_id"],
            session.get("utilisateur_role")
        )
        return send_file(chemin, as_attachment=True)
    except (ValueError, FileNotFoundError, PermissionError) as e:
        flash(f"❌ {e}", "error")
        return redirect(url_for("documents"))
    finally:
        db.close()


@app.route("/documents/supprimer/<int:document_id>")
def supprimer_document_route(document_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        doc = supprimer_document(
            db, document_id,
            session["utilisateur_id"],
            session.get("utilisateur_role")
        )
        flash(f"🗑️ '{doc.nom_original}' déplacé vers la corbeille.", "success")
    except (ValueError, PermissionError) as e:
        flash(f"❌ {e}", "error")
    finally:
        db.close()

    return redirect(url_for("documents"))


@app.route("/corbeille")
def corbeille():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        docs = get_documents_corbeille(
            db,
            utilisateur_id=session["utilisateur_id"],
            role=session.get("utilisateur_role")
        )
        return render_template(
            "corbeille.html",
            nom=session.get("utilisateur_nom"),
            role=session.get("utilisateur_role"),
            documents=docs
        )
    finally:
        db.close()


@app.route("/corbeille/restaurer/<int:document_id>")
def restaurer_document_route(document_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        doc = restaurer_document(
            db, document_id,
            session["utilisateur_id"],
            session.get("utilisateur_role")
        )
        flash(f"♻️ '{doc.nom_original}' restauré avec succès.", "success")
    except (ValueError, PermissionError) as e:
        flash(f"❌ {e}", "error")
    finally:
        db.close()

    return redirect(url_for("corbeille"))


@app.route("/corbeille/supprimer-definitivement/<int:document_id>")
def supprimer_definitivement_route(document_id):
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        supprimer_definitivement(
            db, document_id,
            session["utilisateur_id"],
            session.get("utilisateur_role")
        )
        flash("🗑️ Document supprimé définitivement.", "success")
    except (ValueError, PermissionError) as e:
        flash(f"❌ {e}", "error")
    finally:
        db.close()

    return redirect(url_for("corbeille"))


@app.route("/historique")
def historique():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    db = SessionLocal()
    try:
        if session.get("utilisateur_role") == "admin":
            entrees = get_historique_complet(db, limite=100)
        else:
            entrees = get_historique_utilisateur(db, session["utilisateur_id"], limite=100)

        historique_affichage = [
            {
                "date": e.date_action.strftime("%Y-%m-%d %H:%M"),
                "action": e.action,
                "details": e.details,
                "utilisateur": e.utilisateur.nom_complet if e.utilisateur else "—"
            }
            for e in entrees
        ]

        return render_template(
            "historique.html",
            nom=session.get("utilisateur_nom"),
            role=session.get("utilisateur_role"),
            historique=historique_affichage
        )
    finally:
        db.close()