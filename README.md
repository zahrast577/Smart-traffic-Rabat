# Smart Traffic Monitoring — Rabat

Système de monitoring du trafic urbain basé sur la simulation SUMO et un dashboard web Flask.

## Description
Ce projet simule le trafic routier de la ville de Rabat (Maroc) en utilisant SUMO,
collecte les données via 20 détecteurs virtuels, entraîne un modèle ML de prédiction
de congestion, et affiche les résultats sur un dashboard web temps réel.

## Architecture
- **Simulation** : SUMO + TraCI (Python)
- **Collecte** : 20 boucles inductives E1 sur le réseau de Rabat
- **Base de données** : SQLite
- **Machine Learning** : Random Forest (scikit-learn)
- **Backend** : Flask (Python)
- **Frontend** : HTML + CSS + Chart.js

## Fichiers principaux
- `traffic_monitor.py` — collecte les données depuis SUMO
- `database.py` — initialise et gère la base SQLite
- `ml_model.py` — entraîne le modèle de prédiction
- `app.py` — serveur Flask et dashboard web
- `detectors.add.xml` — configuration des 20 détecteurs
- `rabat.sumocfg` — configuration de la simulation SUMO

## Installation
```bash
python3 -m venv smart_traffic_env
source smart_traffic_env/bin/activate
pip install traci sumolib pandas flask flask-cors scikit-learn matplotlib seaborn
```

## Lancement
```bash
python3 database.py
python3 ml_model.py
python3 app.py
```
Ouvrez `http://localhost:5000` dans le navigateur.

## Données
Le réseau routier `rabat.net.xml` est trop volumineux pour GitHub (79 Mo).
Téléchargez-le depuis OpenStreetMap via JOSM ou osm.org.
