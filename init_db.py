
from app import app, db, Marque, Ecran, Client

with app.app_context():
    # Créer les tables
    db.create_all()

    # Ajouter des marques par défaut
    if Marque.query.count() == 0:
        marques = [
            Marque(nom='Samsung'),
            Marque(nom='iPhone'),
            Marque(nom='Huawei'),
            Marque(nom='Xiaomi'),
            Marque(nom='OPPO'),
            Marque(nom='Vivo')
        ]

        for marque in marques:
            db.session.add(marque)

        db.session.commit()
        print("Marques par défaut ajoutées avec succès!")
    else:
        print("Les marques existent déjà dans la base de données.")

    # Ajouter quelques écrans par défaut
    if Ecran.query.count() == 0:
        samsung = Marque.query.filter_by(nom='Samsung').first()
        iphone = Marque.query.filter_by(nom='iPhone').first()

        ecrans = [
            Ecran(barcode='SAM001', nom='Galaxy A10', prix_achat=35.0, prix_vente=50.0, quantite=20, marque_id=samsung.id),
            Ecran(barcode='SAM002', nom='Galaxy A30', prix_achat=45.0, prix_vente=65.0, quantite=15, marque_id=samsung.id),
            Ecran(barcode='SAM003', nom='Galaxy S10', prix_achat=80.0, prix_vente=120.0, quantite=10, marque_id=samsung.id),
            Ecran(barcode='IPH001', nom='iPhone 11', prix_achat=100.0, prix_vente=150.0, quantite=12, marque_id=iphone.id),
            Ecran(barcode='IPH002', nom='iPhone 12', prix_achat=130.0, prix_vente=180.0, quantite=8, marque_id=iphone.id),
            Ecran(barcode='IPH003', nom='iPhone 13', prix_achat=150.0, prix_vente=220.0, quantite=5, marque_id=iphone.id)
        ]

        for ecran in ecrans:
            db.session.add(ecran)

        db.session.commit()
        print("Écrans par défaut ajoutés avec succès!")
    else:
        print("Les écrans existent déjà dans la base de données.")

    # Ajouter quelques clients par défaut
    if Client.query.count() == 0:
        clients = [
            Client(nom='Ben Ali', prenom='Mohamed', telephone='22123456', email='mohamed@example.com'),
            Client(nom='Trabelsi', prenom='Sonia', telephone='98765432', email='sonia@example.com'),
            Client(nom='Khaled', prenom='Amine', telephone='55123456', email='amine@example.com')
        ]

        for client in clients:
            db.session.add(client)

        db.session.commit()
        print("Clients par défaut ajoutés avec succès!")
    else:
        print("Les clients existent déjà dans la base de données.")

    print("Initialisation de la base de données terminée!")
