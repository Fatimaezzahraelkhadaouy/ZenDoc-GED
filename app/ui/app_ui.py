import gradio as gr
from app.db.database import SessionLocal
from app.db.models import User, Category, Document
from app.services.auth_service import connecter_utilisateur, inscrire_utilisateur
from app.services.document_service import create_document_entry, get_document_path
from app.services.ai_service import analyser_document
from app.services.search_service import add_document_to_index, search_documents
from app.services.rag_service import poser_question, enregistrer_feedback_utilisateur
from app.services.corbeille_service import (
    supprimer_document, restaurer_document,
    get_documents_actifs, get_documents_corbeille
)
from app.services.stats_service import (
    get_statistiques_generales,
    get_repartition_par_categorie,
    get_repartition_actions
)
from app.db.seed_data import get_categorie_id_par_nom


# ============================================================
#  THEME & STYLE PERSONNALISÉS
# ============================================================

theme_personnalise = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="blue",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui"]
)

css_personnalise = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

.gradio-container {
    max-width: 1100px !important;
    margin: auto !important;
    font-family: 'Inter', sans-serif !important;
}

#banniere {
    background: linear-gradient(135deg, #4338ca 0%, #6366f1 50%, #818cf8 100%);
    padding: 28px 36px;
    border-radius: 18px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px rgba(67, 56, 202, 0.3);
    position: relative;
    overflow: hidden;
}
#banniere h1 {
    color: white !important;
    font-size: 30px !important;
    margin: 0 !important;
    font-weight: 700 !important;
}
#banniere p {
    color: #e0e7ff !important;
    margin-top: 8px !important;
    font-size: 14px !important;
}

#carte_bienvenue {
    background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
    border-radius: 14px;
    padding: 16px 22px;
    border-left: 4px solid #4338ca;
    margin-bottom: 16px;
    font-size: 15px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.tabitem {
    padding-top: 20px !important;
}
button[role="tab"] {
    font-weight: 600 !important;
    border-radius: 10px 10px 0 0 !important;
    transition: all 0.2s ease !important;
}
button[role="tab"]:hover {
    background: #eef2ff !important;
}

button.primary {
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(67, 56, 202, 0.25) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
button.primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(67, 56, 202, 0.35) !important;
}

.block {
    border-radius: 14px !important;
}

table {
    border-radius: 10px !important;
    overflow: hidden !important;
}
thead {
    background: #4338ca !important;
}
thead th {
    color: white !important;
    font-weight: 600 !important;
}

.upload-container {
    border-radius: 14px !important;
    border: 2px dashed #a5b4fc !important;
}

.message.user {
    background: #4338ca !important;
    color: white !important;
    border-radius: 14px 14px 2px 14px !important;
}
.message.bot {
    background: #f1f5f9 !important;
    border-radius: 14px 14px 14px 2px !important;
}

footer {
    display: none !important;
}
"""

HTML_BANNIERE = """
<div id="banniere" style="display: flex; align-items: center; justify-content: space-between; gap: 24px;">
    <div>
        <h1> ZenDoc </h1>
        <p>Enhanced Technologies · Gestion Électronique de Documents propulsée par l'IA</p>
    </div>
    <img src="https://cdn.jsdelivr.net/gh/undraw/undraw-assets@main/svg/undraw_online_organizer_re_ejeg.svg" 
         style="width: 150px; height: auto; opacity: 0.95;" 
         alt="illustration"/>
</div>
"""

HTML_ILLUSTRATION_CONNEXION = """
<div style="text-align: center; margin-bottom: 10px;">
    <img src="https://cdn.jsdelivr.net/gh/undraw/undraw-assets@main/svg/undraw_secure_login_pdn4.svg" 
         style="width: 200px; height: auto;" alt="connexion"/>
</div>
"""


# ============================================================
#  FONCTIONS MÉTIER
# ============================================================

def action_connexion(email, mot_de_passe):
    db = SessionLocal()
    try:
        utilisateur = connecter_utilisateur(db, email, mot_de_passe)
        message_bienvenue = f"<div id='carte_bienvenue'>👋 Bienvenue <b>{utilisateur.nom_complet}</b> — rôle : <b>{utilisateur.role}</b></div>"
        return "", utilisateur.id, utilisateur.nom_complet, gr.update(visible=False), gr.update(visible=True), message_bienvenue
    except ValueError as e:
        return f"❌ {e}", None, None, gr.update(visible=True), gr.update(visible=False), ""
    finally:
        db.close()


def action_inscription(nom_complet, email, mot_de_passe):
    db = SessionLocal()
    try:
        utilisateur = inscrire_utilisateur(db, nom_complet, email, mot_de_passe, role="utilisateur")
        return f"✅ Compte créé avec succès pour {utilisateur.nom_complet} ! Vous pouvez maintenant vous connecter."
    except ValueError as e:
        return f"❌ {e}"
    finally:
        db.close()


def action_deconnexion():
    return None, None, gr.update(visible=True), gr.update(visible=False), ""


def action_upload(fichier, utilisateur_id):
    if fichier is None:
        return "⚠️ Merci de sélectionner un fichier."
    if utilisateur_id is None:
        return "❌ Vous devez être connecté."

    db = SessionLocal()
    try:
        nom_original = fichier.name.split("\\")[-1].split("/")[-1]

        document = create_document_entry(
            db=db,
            file_path=fichier.name,
            original_filename=nom_original,
            uploaded_by=utilisateur_id
        )

        resultat = analyser_document(document.contenu_extrait)
        categorie_id = get_categorie_id_par_nom(db, resultat["categorie"])
        document.resume_ia = resultat["resume"]
        document.categorie_id = categorie_id
        db.commit()

        add_document_to_index(
            document_id=document.id,
            texte=document.contenu_extrait,
            nom_fichier=document.nom_original
        )

        message = f"""✅ **Document déposé avec succès !**

📄 **Nom :** {document.nom_original}
📂 **Catégorie détectée :** {resultat['categorie']}
📝 **Résumé :** {resultat['resume']}
"""
        return message
    except Exception as e:
        return f"❌ Erreur : {e}"
    finally:
        db.close()


def action_recherche(requete, utilisateur_id):
    if not requete or requete.strip() == "":
        return "⚠️ Merci de saisir une recherche."
    if utilisateur_id is None:
        return "❌ Vous devez être connecté."

    db = SessionLocal()
    try:
        resultats = search_documents(
            query=requete,
            utilisateur_id=utilisateur_id,
            db=db,
            n_results=5
        )

        ids_trouves = resultats["ids"][0]
        if not ids_trouves:
            return "Aucun résultat trouvé."

        texte_resultats = f"### 🔍 Résultats pour : *{requete}*\n\n"
        for i, doc_id in enumerate(ids_trouves):
            nom = resultats["metadatas"][0][i]["nom_fichier"]
            distance = resultats["distances"][0][i]
            pertinence = round((1 - distance) * 100, 1)
            texte_resultats += f"**{i+1}. 📄 {nom}** — pertinence : {pertinence}%\n\n"

        return texte_resultats
    except Exception as e:
        return f"❌ Erreur : {e}"
    finally:
        db.close()


def action_chat(question, utilisateur_id, historique_chat):
    if not question or question.strip() == "":
        return historique_chat, "", None
    if utilisateur_id is None:
        return historique_chat, "", None

    if historique_chat is None:
        historique_chat = []

    db = SessionLocal()
    try:
        resultat = poser_question(question=question, utilisateur_id=utilisateur_id, db=db)

        reponse_affichee = resultat["reponse"]
        if resultat["sources"]:
            reponse_affichee += f"\n\n📄 *Sources : {', '.join(resultat['sources'])}*"
        if resultat["score_ia"]:
            reponse_affichee += f"\n⭐ *Auto-évaluation IA : {resultat['score_ia']}/5*"

        historique_chat = historique_chat + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": reponse_affichee}
        ]
        return historique_chat, "", resultat["feedback_id"]
    except Exception as e:
        historique_chat = historique_chat + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": f"❌ Erreur : {e}"}
        ]
        return historique_chat, "", None
    finally:
        db.close()


def action_feedback_positif(feedback_id):
    if feedback_id is None:
        return "Aucune réponse récente à noter."
    db = SessionLocal()
    try:
        enregistrer_feedback_utilisateur(db, feedback_id, positif=True)
        return "✅ Merci pour votre retour positif !"
    except Exception as e:
        return f"❌ Erreur : {e}"
    finally:
        db.close()


def action_feedback_negatif(feedback_id):
    if feedback_id is None:
        return "Aucune réponse récente à noter."
    db = SessionLocal()
    try:
        enregistrer_feedback_utilisateur(db, feedback_id, positif=False)
        return "📝 Merci, votre retour a été pris en compte."
    except Exception as e:
        return f"❌ Erreur : {e}"
    finally:
        db.close()


def formater_liste_documents(documents):
    if not documents:
        return [["Aucun document", "", "", ""]]
    return [
        [doc.id, doc.nom_original, doc.categorie.nom if doc.categorie else "Non classé", f"{doc.taille} Ko"]
        for doc in documents
    ]


def action_rafraichir_documents(utilisateur_id):
    if utilisateur_id is None:
        return formater_liste_documents([])
    db = SessionLocal()
    try:
        documents = get_documents_actifs(db)
        return formater_liste_documents(documents)
    finally:
        db.close()


def action_rafraichir_corbeille(utilisateur_id):
    if utilisateur_id is None:
        return formater_liste_documents([])
    db = SessionLocal()
    try:
        documents = get_documents_corbeille(db)
        return formater_liste_documents(documents)
    finally:
        db.close()


def action_supprimer(document_id_texte, utilisateur_id):
    if utilisateur_id is None:
        return "❌ Vous devez être connecté.", formater_liste_documents([])
    try:
        document_id = int(document_id_texte)
    except (ValueError, TypeError):
        return "⚠️ Merci de saisir un id de document valide (nombre).", formater_liste_documents([])

    db = SessionLocal()
    try:
        document = supprimer_document(db, document_id, utilisateur_id)
        message = f"🗑️ '{document.nom_original}' déplacé vers la corbeille."
        nouvelle_liste = formater_liste_documents(get_documents_actifs(db))
        return message, nouvelle_liste
    except ValueError as e:
        return f"❌ {e}", formater_liste_documents(get_documents_actifs(db))
    finally:
        db.close()


def action_restaurer(document_id_texte, utilisateur_id):
    if utilisateur_id is None:
        return "❌ Vous devez être connecté.", formater_liste_documents([])
    try:
        document_id = int(document_id_texte)
    except (ValueError, TypeError):
        return "⚠️ Merci de saisir un id de document valide (nombre).", formater_liste_documents([])

    db = SessionLocal()
    try:
        document = restaurer_document(db, document_id, utilisateur_id)
        message = f"♻️ '{document.nom_original}' restauré avec succès."
        nouvelle_liste = formater_liste_documents(get_documents_corbeille(db))
        return message, nouvelle_liste
    except ValueError as e:
        return f"❌ {e}", formater_liste_documents(get_documents_corbeille(db))
    finally:
        db.close()


def action_telecharger(document_id_texte, utilisateur_id):
    if utilisateur_id is None:
        return None, "❌ Vous devez être connecté."
    try:
        document_id = int(document_id_texte)
    except (ValueError, TypeError):
        return None, "⚠️ Merci de saisir un id de document valide (nombre)."

    db = SessionLocal()
    try:
        chemin = get_document_path(db, document_id, utilisateur_id)
        return chemin, f"✅ Fichier prêt : {chemin}"
    except (ValueError, FileNotFoundError) as e:
        return None, f"❌ {e}"
    finally:
        db.close()


def action_rafraichir_dashboard(utilisateur_id):
    if utilisateur_id is None:
        return "", [], []

    db = SessionLocal()
    try:
        stats = get_statistiques_generales(db)
        texte_stats = f"""
### 📊 Statistiques générales

- 📄 **Documents totaux :** {stats['total_documents']}
- 👤 **Utilisateurs actifs :** {stats['total_utilisateurs']}
- 📈 **Actions enregistrées :** {stats['total_actions']}
- 💾 **Espace utilisé :** {stats['taille_totale_mo']} Mo
"""
        repartition_cat = get_repartition_par_categorie(db)
        tableau_categories = [[item["categorie"], item["nombre"]] for item in repartition_cat]

        repartition_act = get_repartition_actions(db)
        tableau_actions = [[item["action"], item["nombre"]] for item in repartition_act]

        return texte_stats, tableau_categories, tableau_actions
    finally:
        db.close()


# ============================================================
#  CONSTRUCTION DE L'INTERFACE
# ============================================================

with gr.Blocks(title="ZenDoc — Enhanced Technologies", theme=theme_personnalise, css=css_personnalise) as app:

    utilisateur_id_state = gr.State(None)
    utilisateur_nom_state = gr.State(None)
    dernier_feedback_id = gr.State(None)

    gr.HTML(HTML_BANNIERE)

    with gr.Column(visible=True) as bloc_connexion:
        gr.HTML(HTML_ILLUSTRATION_CONNEXION)

        with gr.Tab("🔐 Se connecter"):
            email_connexion = gr.Textbox(label="Email", placeholder="votre.email@exemple.com")
            password_connexion = gr.Textbox(label="Mot de passe", type="password")
            btn_connexion = gr.Button("Se connecter", variant="primary", size="lg")
            message_connexion = gr.Markdown()

        with gr.Tab("✨ Créer un compte"):
            nom_inscription = gr.Textbox(label="Nom complet")
            email_inscription = gr.Textbox(label="Email")
            password_inscription = gr.Textbox(label="Mot de passe", type="password")
            btn_inscription = gr.Button("Créer mon compte", variant="primary", size="lg")
            message_inscription = gr.Markdown()

    with gr.Column(visible=False) as bloc_application:
        with gr.Row():
            with gr.Column(scale=4):
                info_utilisateur = gr.HTML()
            with gr.Column(scale=1):
                btn_deconnexion = gr.Button("🚪 Déconnexion", size="sm")

        with gr.Tabs():
            with gr.Tab("📤 Dépôt de documents"):
                gr.Markdown("### Déposer un nouveau document")
                gr.Markdown("*Formats acceptés : PDF, Word — analyse et classification automatiques par IA*")
                fichier_upload = gr.File(label="Choisir un fichier", file_types=[".pdf", ".docx"])
                btn_upload = gr.Button("✨ Analyser et enregistrer", variant="primary", size="lg")
                resultat_upload = gr.Markdown()

            with gr.Tab("🔍 Recherche"):
                gr.Markdown("### Recherche sémantique")
                gr.Markdown("*Recherchez par sens, pas seulement par mots-clés exacts*")
                requete_recherche = gr.Textbox(label="Que cherchez-vous ?", placeholder="Ex: principes d'économie, contrats de travail...")
                btn_recherche = gr.Button("Rechercher", variant="primary")
                resultat_recherche = gr.Markdown()

            with gr.Tab("💬 Chat avec les documents"):
                gr.Markdown("### Assistant intelligent")
                gr.Markdown("*Posez une question, l'IA répond en se basant sur vos documents*")
                chatbot = gr.Chatbot(label="Assistant GED", height=400)
                question_chat = gr.Textbox(label="Votre question", placeholder="Ex: Qui est l'auteur mentionné dans le document ?")
                btn_envoyer_chat = gr.Button("Envoyer", variant="primary")
                with gr.Row():
                    btn_pouce_haut = gr.Button("👍 Utile")
                    btn_pouce_bas = gr.Button("👎 Pas utile")
                message_feedback = gr.Markdown()

            with gr.Tab("📁 Mes documents"):
                gr.Markdown("### Documents actifs")
                btn_rafraichir_docs = gr.Button("🔄 Rafraîchir la liste")
                tableau_documents = gr.Dataframe(
                    headers=["ID", "Nom", "Catégorie", "Taille"],
                    interactive=False
                )
                gr.Markdown("*Copiez l'ID du document ci-dessus pour le télécharger ou le supprimer*")
                id_document_action = gr.Textbox(label="ID du document")
                with gr.Row():
                    btn_telecharger = gr.Button("⬇️ Télécharger")
                    btn_supprimer = gr.Button("🗑️ Supprimer (vers corbeille)", variant="stop")
                message_action_document = gr.Markdown()
                fichier_telecharge = gr.File(label="Fichier téléchargé", visible=True)

            with gr.Tab("🗑️ Corbeille"):
                gr.Markdown("### Documents supprimés (récupérables)")
                btn_rafraichir_corbeille = gr.Button("🔄 Rafraîchir la corbeille")
                tableau_corbeille = gr.Dataframe(
                    headers=["ID", "Nom", "Catégorie", "Taille"],
                    interactive=False
                )
                id_document_restaurer = gr.Textbox(label="ID du document à restaurer")
                btn_restaurer = gr.Button("♻️ Restaurer ce document", variant="primary")
                message_restauration = gr.Markdown()

            with gr.Tab("📊 Tableau de bord"):
                gr.Markdown("### Vue d'ensemble de l'activité")
                btn_rafraichir_dashboard = gr.Button("🔄 Rafraîchir les statistiques", variant="primary")
                stats_generales = gr.Markdown()
                gr.Markdown("#### Répartition par catégorie")
                tableau_categories = gr.Dataframe(headers=["Catégorie", "Nombre de documents"], interactive=False)
                gr.Markdown("#### Répartition des actions")
                tableau_actions = gr.Dataframe(headers=["Action", "Nombre"], interactive=False)

    btn_connexion.click(
        fn=action_connexion,
        inputs=[email_connexion, password_connexion],
        outputs=[message_connexion, utilisateur_id_state, utilisateur_nom_state, bloc_connexion, bloc_application, info_utilisateur]
    )

    btn_inscription.click(
        fn=action_inscription,
        inputs=[nom_inscription, email_inscription, password_inscription],
        outputs=[message_inscription]
    )

    btn_deconnexion.click(
        fn=action_deconnexion,
        outputs=[utilisateur_id_state, utilisateur_nom_state, bloc_connexion, bloc_application, info_utilisateur]
    )

    btn_upload.click(
        fn=action_upload,
        inputs=[fichier_upload, utilisateur_id_state],
        outputs=[resultat_upload]
    )

    btn_recherche.click(
        fn=action_recherche,
        inputs=[requete_recherche, utilisateur_id_state],
        outputs=[resultat_recherche]
    )

    btn_envoyer_chat.click(
        fn=action_chat,
        inputs=[question_chat, utilisateur_id_state, chatbot],
        outputs=[chatbot, question_chat, dernier_feedback_id]
    )

    btn_pouce_haut.click(
        fn=action_feedback_positif,
        inputs=[dernier_feedback_id],
        outputs=[message_feedback]
    )

    btn_pouce_bas.click(
        fn=action_feedback_negatif,
        inputs=[dernier_feedback_id],
        outputs=[message_feedback]
    )

    btn_rafraichir_docs.click(
        fn=action_rafraichir_documents,
        inputs=[utilisateur_id_state],
        outputs=[tableau_documents]
    )

    btn_telecharger.click(
        fn=action_telecharger,
        inputs=[id_document_action, utilisateur_id_state],
        outputs=[fichier_telecharge, message_action_document]
    )

    btn_supprimer.click(
        fn=action_supprimer,
        inputs=[id_document_action, utilisateur_id_state],
        outputs=[message_action_document, tableau_documents]
    )

    btn_rafraichir_corbeille.click(
        fn=action_rafraichir_corbeille,
        inputs=[utilisateur_id_state],
        outputs=[tableau_corbeille]
    )

    btn_restaurer.click(
        fn=action_restaurer,
        inputs=[id_document_restaurer, utilisateur_id_state],
        outputs=[message_restauration, tableau_corbeille]
    )

    btn_rafraichir_dashboard.click(
        fn=action_rafraichir_dashboard,
        inputs=[utilisateur_id_state],
        outputs=[stats_generales, tableau_categories, tableau_actions]
    )


if __name__ == "__main__":
    app.launch()