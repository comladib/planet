
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # استخدام واجهة خلفية غير تفاعلية
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from sklearn.linear_model import LinearRegression
import numpy as np
import joblib

app = Flask(__name__)
# استخدام مفتاح سري من متغيرات البيئة إذا كان متوفراً
app.secret_key = os.environ.get('SECRET_KEY', 'stock_management_secret_key')

# إعدادات قاعدة البيانات
# استخدام قاعدة بيانات PostgreSQL على Render أو SQLite محلياً
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    # تعديل رابط PostgreSQL ليتوافق مع SQLAlchemy
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///stock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Définition des modèles de base de données
class Marque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), unique=True, nullable=False)
    ecrans = db.relationship('Ecran', backref='marque', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"Marque('{self.nom}')"

class Ecran(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(100), unique=True, nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    prix_achat = db.Column(db.Float, nullable=False)
    prix_vente = db.Column(db.Float, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    seuil_alerte = db.Column(db.Integer, default=5)
    marque_id = db.Column(db.Integer, db.ForeignKey('marque.id'), nullable=False)
    ventes = db.relationship('Vente', backref='ecran', lazy=True)
    historiques = db.relationship('Historique', backref='ecran', lazy=True)

    def __repr__(self):
        return f"Ecran('{self.nom}', '{self.barcode}', Quantité: {self.quantite})"

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    adresse = db.Column(db.String(200), nullable=True)
    ventes = db.relationship('Vente', backref='client', lazy=True)

    def __repr__(self):
        return f"Client('{self.nom}', '{self.prenom}')"

class Vente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_vente = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False)
    ecran_id = db.Column(db.Integer, db.ForeignKey('ecran.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)

    def __repr__(self):
        return f"Vente(ID: {self.id}, Date: {self.date_vente}, Quantité: {self.quantite})"

class Historique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_operation = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    type_operation = db.Column(db.String(50), nullable=False)  # 'ajout' ou 'retrait'
    quantite = db.Column(db.Integer, nullable=False)
    ecran_id = db.Column(db.Integer, db.ForeignKey('ecran.id'), nullable=False)

    def __repr__(self):
        return f"Historique('{self.type_operation}', {self.quantite}, {self.date_operation})"

# Routes pour l'application
@app.route('/')
def index():
    return render_template('index.html')

# Routes pour les marques
@app.route('/marques')
def marques():
    marques_list = Marque.query.all()
    return render_template('marques.html', marques=marques_list)

@app.route('/ajouter_marque', methods=['POST'])
def ajouter_marque():
    nom = request.form.get('nom')
    if nom:
        nouvelle_marque = Marque(nom=nom)
        db.session.add(nouvelle_marque)
        db.session.commit()
        flash('Marque ajoutée avec succès!', 'success')
    else:
        flash('Le nom de la marque est requis!', 'danger')
    return redirect(url_for('marques'))

@app.route('/modifier_marque/<int:id>', methods=['POST'])
def modifier_marque(id):
    marque = Marque.query.get_or_404(id)
    nom = request.form.get('nom')
    if nom:
        marque.nom = nom
        db.session.commit()
        flash('Marque modifiée avec succès!', 'success')
    else:
        flash('Le nom de la marque est requis!', 'danger')
    return redirect(url_for('marques'))

@app.route('/supprimer_marque/<int:id>')
def supprimer_marque(id):
    marque = Marque.query.get_or_404(id)
    db.session.delete(marque)
    db.session.commit()
    flash('Marque supprimée avec succès!', 'success')
    return redirect(url_for('marques'))

# Routes pour les écrans
@app.route('/ecrans')
def ecrans():
    ecrans_list = Ecran.query.all()
    marques_list = Marque.query.all()
    return render_template('ecrans.html', ecrans=ecrans_list, marques=marques_list)

@app.route('/ajouter_ecran', methods=['POST'])
def ajouter_ecran():
    barcode = request.form.get('barcode')
    nom = request.form.get('nom')
    prix_achat = float(request.form.get('prix_achat'))
    prix_vente = float(request.form.get('prix_vente'))
    quantite = int(request.form.get('quantite'))
    seuil_alerte = int(request.form.get('seuil_alerte', 5))
    marque_id = int(request.form.get('marque_id'))

    if all([barcode, nom, prix_achat, prix_vente, quantite, marque_id]):
        # Vérifier si le barcode existe déjà
        existing_barcode = Ecran.query.filter_by(barcode=barcode).first()
        if existing_barcode:
            flash('Ce barcode existe déjà!', 'danger')
            return redirect(url_for('ecrans'))

        nouvel_ecran = Ecran(
            barcode=barcode,
            nom=nom,
            prix_achat=prix_achat,
            prix_vente=prix_vente,
            quantite=quantite,
            seuil_alerte=seuil_alerte,
            marque_id=marque_id
        )
        db.session.add(nouvel_ecran)
        try:
            db.session.commit()  # Commit first to get the ID

            # Ajouter à l'historique
            historique = Historique(
                type_operation='ajout',
                quantite=quantite,
                ecran_id=nouvel_ecran.id
            )
            db.session.add(historique)
            db.session.commit()  # Commit again to save the history
            flash('Écran ajouté avec succès!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de l\'ajout: {str(e)}', 'danger')
    else:
        flash('Tous les champs sont requis!', 'danger')
    return redirect(url_for('ecrans'))

@app.route('/modifier_ecran/<int:id>', methods=['POST'])
def modifier_ecran(id):
    ecran = Ecran.query.get_or_404(id)
    
    try:
        barcode = request.form.get('barcode')
        nom = request.form.get('nom')
        prix_achat = float(request.form.get('prix_achat'))
        prix_vente = float(request.form.get('prix_vente'))
        quantite = int(request.form.get('quantite'))
        seuil_alerte = int(request.form.get('seuil_alerte', 5))
        marque_id = int(request.form.get('marque_id'))
    except (ValueError, TypeError) as e:
        flash(f'Erreur de conversion des données: {str(e)}', 'danger')
        return redirect(url_for('ecrans'))

    if all([barcode, nom, prix_achat, prix_vente, quantite, seuil_alerte, marque_id]):
        # Vérifier si le barcode existe déjà et n'appartient pas à cet écran
        existing_barcode = Ecran.query.filter_by(barcode=barcode).first()
        if existing_barcode and existing_barcode.id != id:
            flash('Ce barcode existe déjà!', 'danger')
            return redirect(url_for('ecrans'))

        # Calculer la différence de quantité pour l'historique
        diff_quantite = quantite - ecran.quantite
        type_operation = 'ajout' if diff_quantite > 0 else 'retrait'

        ecran.barcode = barcode
        ecran.nom = nom
        ecran.prix_achat = prix_achat
        ecran.prix_vente = prix_vente
        ecran.quantite = quantite
        ecran.seuil_alerte = seuil_alerte
        ecran.marque_id = marque_id

        # Ajouter à l'historique si la quantité a changé
        if diff_quantite != 0:
            historique = Historique(
                type_operation=type_operation,
                quantite=abs(diff_quantite),
                ecran_id=ecran.id
            )
            db.session.add(historique)

        try:
            db.session.commit()
            flash('Écran modifié avec succès!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la modification: {str(e)}', 'danger')
    else:
        flash('Tous les champs sont requis!', 'danger')
    return redirect(url_for('ecrans'))

@app.route('/supprimer_ecran/<int:id>')
def supprimer_ecran(id):
    ecran = Ecran.query.get_or_404(id)
    db.session.delete(ecran)
    db.session.commit()
    flash('Écran supprimé avec succès!', 'success')
    return redirect(url_for('ecrans'))

@app.route('/recherche_ecrans')
def recherche_ecrans():
    terme = request.args.get('terme', '')
    critere = request.args.get('critere', 'nom')

    if critere == 'nom':
        ecrans = Ecran.query.filter(Ecran.nom.contains(terme)).all()
    elif critere == 'barcode':
        ecrans = Ecran.query.filter(Ecran.barcode.contains(terme)).all()
    elif critere == 'quantite':
        try:
            quantite = int(terme)
            ecrans = Ecran.query.filter(Ecran.quantite == quantite).all()
        except ValueError:
            ecrans = []
    else:
        ecrans = []

    return render_template('recherche_ecrans.html', ecrans=ecrans, terme=terme, critere=critere)

@app.route('/generer_barcode/<barcode>')
def generer_barcode(barcode):
    # Générer le code-barres
    rv = BytesIO()
    Code128(barcode, writer=ImageWriter()).write(rv)
    rv.seek(0)

    # Retourner l'image en base64
    return send_file(rv, mimetype='image/png')

# Routes pour les clients
@app.route('/clients')
def clients():
    clients_list = Client.query.all()
    return render_template('clients.html', clients=clients_list)

@app.route('/ajouter_client', methods=['POST'])
def ajouter_client():
    nom = request.form.get('nom')
    prenom = request.form.get('prenom')
    telephone = request.form.get('telephone')
    email = request.form.get('email')
    adresse = request.form.get('adresse')

    if nom and prenom:
        nouveau_client = Client(
            nom=nom,
            prenom=prenom,
            telephone=telephone,
            email=email,
            adresse=adresse
        )
        db.session.add(nouveau_client)
        db.session.commit()
        flash('Client ajouté avec succès!', 'success')
    else:
        flash('Le nom et le prénom sont requis!', 'danger')
    return redirect(url_for('clients'))

@app.route('/modifier_client/<int:id>', methods=['POST'])
def modifier_client(id):
    client = Client.query.get_or_404(id)
    nom = request.form.get('nom')
    prenom = request.form.get('prenom')
    telephone = request.form.get('telephone')
    email = request.form.get('email')
    adresse = request.form.get('adresse')

    if nom and prenom:
        client.nom = nom
        client.prenom = prenom
        client.telephone = telephone
        client.email = email
        client.adresse = adresse
        db.session.commit()
        flash('Client modifié avec succès!', 'success')
    else:
        flash('Le nom et le prénom sont requis!', 'danger')
    return redirect(url_for('clients'))

@app.route('/supprimer_client/<int:id>')
def supprimer_client(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    flash('Client supprimé avec succès!', 'success')
    return redirect(url_for('clients'))

# Routes pour les ventes
@app.route('/vente')
def vente():
    ecrans = Ecran.query.all()
    clients = Client.query.all()
    return render_template('vente.html', ecrans=ecrans, clients=clients)

@app.route('/recherche_ecran_barcode')
def recherche_ecran_barcode():
    barcode = request.args.get('barcode', '')
    ecran = Ecran.query.filter_by(barcode=barcode).first()

    if ecran:
        return jsonify({
            'id': ecran.id,
            'nom': ecran.nom,
            'marque': ecran.marque.nom,
            'prix_vente': ecran.prix_vente,
            'quantite': ecran.quantite
        })
    else:
        return jsonify({'error': 'Écran non trouvé'}), 404

@app.route('/effectuer_vente', methods=['POST'])
def effectuer_vente():
    ecran_id = int(request.form.get('ecran_id'))
    client_id = int(request.form.get('client_id'))
    quantite = int(request.form.get('quantite'))

    ecran = Ecran.query.get_or_404(ecran_id)
    client = Client.query.get_or_404(client_id)

    if ecran.quantite >= quantite:
        # Mettre à jour la quantité en stock
        ecran.quantite -= quantite

        # Créer la vente
        nouvelle_vente = Vente(
            quantite=quantite,
            prix_unitaire=ecran.prix_vente,
            ecran_id=ecran.id,
            client_id=client.id
        )

        # Ajouter à l'historique
        historique = Historique(
            type_operation='retrait',
            quantite=quantite,
            ecran_id=ecran.id
        )

        db.session.add(nouvelle_vente)
        db.session.add(historique)
        db.session.commit()

        flash('Vente effectuée avec succès!', 'success')
        return redirect(url_for('facture', vente_id=nouvelle_vente.id))
    else:
        flash('Quantité insuffisante en stock!', 'danger')
        return redirect(url_for('vente'))

@app.route('/facture/<int:vente_id>')
def facture(vente_id):
    vente = Vente.query.get_or_404(vente_id)
    return render_template('facture.html', vente=vente)

@app.route('/generer_facture_pdf/<int:vente_id>')
def generer_facture_pdf(vente_id):
    vente = Vente.query.get_or_404(vente_id)
    ecran = vente.ecran
    client = vente.client

    # Créer un buffer pour le PDF
    buffer = BytesIO()

    # Créer le PDF
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Ajouter le titre
    p.setFont("Helvetica-Bold", 16)
    p.drawString(inch, height - inch, "FACTURE")

    # Ajouter les informations de la vente
    p.setFont("Helvetica", 12)
    p.drawString(inch, height - 1.5 * inch, f"Date: {vente.date_vente.strftime('%d/%m/%Y %H:%M')}")
    p.drawString(inch, height - 1.75 * inch, f"ID Vente: {vente.id}")

    # Ajouter les informations du client
    p.setFont("Helvetica-Bold", 12)
    p.drawString(inch, height - 2.25 * inch, "Client:")
    p.setFont("Helvetica", 12)
    p.drawString(inch, height - 2.5 * inch, f"Nom: {client.nom} {client.prenom}")
    if client.telephone:
        p.drawString(inch, height - 2.75 * inch, f"Téléphone: {client.telephone}")
    if client.email:
        p.drawString(inch, height - 3 * inch, f"Email: {client.email}")

    # Ajouter les informations du produit
    p.setFont("Helvetica-Bold", 12)
    p.drawString(inch, height - 3.5 * inch, "Produit:")
    p.setFont("Helvetica", 12)
    p.drawString(inch, height - 3.75 * inch, f"Marque: {ecran.marque.nom}")
    p.drawString(inch, height - 4 * inch, f"Écran: {ecran.nom}")
    p.drawString(inch, height - 4.25 * inch, f"Barcode: {ecran.barcode}")
    p.drawString(inch, height - 4.5 * inch, f"Quantité: {vente.quantite}")
    p.drawString(inch, height - 4.75 * inch, f"Prix unitaire: {ecran.prix_vente} TND")

    # Calculer le total
    total = vente.quantite * vente.prix_unitaire
    p.setFont("Helvetica-Bold", 12)
    p.drawString(inch, height - 5.25 * inch, f"Total: {total} TND")

    # Finaliser le PDF
    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'facture_{vente.id}.pdf', mimetype='application/pdf')

# Routes pour l'historique
@app.route('/historique')
def historique():
    historique_stock = Historique.query.order_by(Historique.date_operation.desc()).all()
    ventes = Vente.query.order_by(Vente.date_vente.desc()).all()
    return render_template('historique.html', historique_stock=historique_stock, ventes=ventes)

# Routes pour les statistiques
@app.route('/statistiques')
def statistiques():
    # Calculer les statistiques de base
    total_ecrans = Ecran.query.count()
    total_ventes = Vente.query.count()
    total_clients = Client.query.count()

    # Calculer le chiffre d'affaires
    chiffre_affaires = 0
    for vente in Vente.query.all():
        chiffre_affaires += vente.quantite * vente.prix_unitaire

    # Calculer le coût d'achat total
    cout_achat_total = 0
    for vente in Vente.query.all():
        cout_achat_total += vente.quantite * vente.ecran.prix_achat

    # Calculer le bénéfice
    benefice = chiffre_affaires - cout_achat_total

    # Préparation des données pour les graphiques
    ventes_par_mois = {}
    for vente in Vente.query.all():
        mois = vente.date_vente.strftime('%Y-%m')
        if mois not in ventes_par_mois:
            ventes_par_mois[mois] = 0
        ventes_par_mois[mois] += vente.quantite * vente.prix_unitaire

    ventes_par_marque = {}
    for vente in Vente.query.all():
        marque = vente.ecran.marque.nom
        if marque not in ventes_par_marque:
            ventes_par_marque[marque] = 0
        ventes_par_marque[marque] += vente.quantite

    # Création des graphiques
    # Graphique des ventes par mois
    plt.figure(figsize=(10, 5))
    mois = list(ventes_par_mois.keys())
    ventes = list(ventes_par_mois.values())
    plt.bar(mois, ventes, color='skyblue')
    plt.xlabel('Mois')
    plt.ylabel("Chiffre d'affaires (TND)")
    plt.title("Chiffre d'affaires par mois")
    plt.xticks(rotation=45)
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    graphique_ventes_mois = base64.b64encode(img.getvalue()).decode('utf-8')
    plt.close()

    # Graphique des ventes par marque
    plt.figure(figsize=(10, 5))
    marques = list(ventes_par_marque.keys())
    quantites = list(ventes_par_marque.values())
    plt.pie(quantites, labels=marques, autopct='%1.1f%%')
    plt.title('Répartition des ventes par marque')
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    graphique_ventes_marque = base64.b64encode(img.getvalue()).decode('utf-8')
    plt.close()

    # Prédiction des ventes avec l'IA
    try:
        # Préparation des données pour la prédiction
        ventes_data = []
        for vente in Vente.query.all():
            ventes_data.append({
                'date': vente.date_vente,
                'quantite': vente.quantite,
                'prix': vente.prix_unitaire,
                'total': vente.quantite * vente.prix_unitaire
            })

        if ventes_data:
            df = pd.DataFrame(ventes_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df['mois'] = df['date'].dt.to_period('M')

            # Agréger les ventes par mois
            ventes_mensuelles = df.groupby('mois')['total'].sum().reset_index()
            ventes_mensuelles['mois_num'] = ventes_mensuelles['mois'].astype(int)

            # Entraîner le modèle de régression linéaire
            X = np.array(ventes_mensuelles['mois_num']).reshape(-1, 1)
            y = np.array(ventes_mensuelles['total'])

            model = LinearRegression()
            model.fit(X, y)

            # Sauvegarder le modèle
            joblib.dump(model, 'ventes_model.pkl')

            # Prédire les ventes pour les 3 prochains mois
            dernier_mois = ventes_mensuelles['mois_num'].max()
            mois_futurs = np.array([dernier_mois + 1, dernier_mois + 2, dernier_mois + 3]).reshape(-1, 1)
            predictions = model.predict(mois_futurs)

            # Créer un graphique avec les prédictions
            plt.figure(figsize=(10, 5))
            plt.plot(ventes_mensuelles['mois_num'], ventes_mensuelles['total'], 'o-', label='Ventes réelles')
            plt.plot(mois_futurs, predictions, 'o--', label='Prédictions')
            plt.xlabel('Mois')
            plt.ylabel("Chiffre d'affaires (TND)")
            plt.title("Prédiction des ventes pour les 3 prochains mois")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()

            img = io.BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            graphique_predictions = base64.b64encode(img.getvalue()).decode('utf-8')
            plt.close()

            # Formater les prédictions pour l'affichage
            predictions_formatees = [f"{pred:.2f} TND" for pred in predictions]
        else:
            graphique_predictions = None
            predictions_formatees = []
    except Exception as e:
        print(f"Erreur lors de la prédiction: {e}")
        graphique_predictions = None
        predictions_formatees = []

    return render_template(
        'statistiques.html',
        total_ecrans=total_ecrans,
        total_ventes=total_ventes,
        total_clients=total_clients,
        chiffre_affaires=chiffre_affaires,
        cout_achat_total=cout_achat_total,
        benefice=benefice,
        graphique_ventes_mois=graphique_ventes_mois,
        graphique_ventes_marque=graphique_ventes_marque,
        graphique_predictions=graphique_predictions,
        predictions=predictions_formatees
    )

# Route pour les statistiques de la page d'accueil
@app.route('/stats_accueil')
def stats_accueil():
    # Calculer les statistiques de base
    total_ecrans = Ecran.query.count()
    total_ventes = Vente.query.count()
    total_clients = Client.query.count()
    total_marques = Marque.query.count()
    
    # Récupérer les dernières ventes
    dernieres_ventes = Vente.query.order_by(Vente.date_vente.desc()).limit(5).all()
    
    # Récupérer les écrans en stock faible
    ecrans_faible_stock = Ecran.query.filter(Ecran.quantite <= Ecran.seuil_alerte).all()
    
    return jsonify({
        'total_ecrans': total_ecrans,
        'total_ventes': total_ventes,
        'total_clients': total_clients,
        'total_marques': total_marques,
        'dernieres_ventes': len(dernieres_ventes),
        'ecrans_faible_stock': len(ecrans_faible_stock)
    })

# Vérifier les seuils d'alerte
@app.route('/verifier_alertes')
def verifier_alertes():
    ecrans_alerte = Ecran.query.filter(Ecran.quantite <= Ecran.seuil_alerte).all()
    return jsonify({
        'alertes': len(ecrans_alerte) > 0,
        'ecrans': [{'id': e.id, 'nom': e.nom, 'quantite': e.quantite, 'seuil': e.seuil_alerte} for e in ecrans_alerte]
    })

# Créer les tables de la base de données
def create_tables():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # تشغيل التطبيق على الخادم المحلي
    app.run(debug=True)
else:
    # عند النشر على Render
    with app.app_context():
        db.create_all()
