"""
mqtt_publisher.py
-----------------
Simule la couche Edge (capteurs / SUMO) et publie les données
de trafic sur le broker MQTT (Mosquitto).

Remplace traffic_monitor.py dans le pipeline.

Topic utilisé : traffic/sensors
"""

import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime

# ─── Configuration MQTT ───────────────────────────────────────────────────────
BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC       = "traffic/sensors"
CLIENT_ID   = "sumo_publisher"

# ─── Paramètres de simulation ─────────────────────────────────────────────────
CAPTEURS = [
    {"device_id": "sensor_A1", "location": "Carrefour Nord"},
    {"device_id": "sensor_A2", "location": "Boulevard Central"},
    {"device_id": "sensor_B1", "location": "Rue du Marché"},
    {"device_id": "sensor_B2", "location": "Avenue Sud"},
]

NB_MESSAGES   = 120   # nombre total de messages à publier
INTERVAL_SEC  = 1.0   # intervalle entre chaque envoi (secondes)


# ─── Callbacks MQTT ───────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    codes = {
        0: "Connecté au broker MQTT ✅",
        1: "Refus : mauvaise version du protocole",
        2: "Refus : identifiant client rejeté",
        3: "Refus : serveur indisponible",
        4: "Refus : identifiants incorrects",
        5: "Refus : non autorisé",
    }
    print(codes.get(rc, f"Code inconnu : {rc}"))

def on_publish(client, userdata, mid):
    print(f"  📤 Message {mid} publié")


# ─── Génération d'une mesure simulée ──────────────────────────────────────────
def generer_donnees(capteur: dict) -> dict:
    """
    Simule les données qu'un capteur de trafic enverrait.
    En production, ces valeurs viendraient directement de SUMO
    via l'API TraCI (traci.edge.getLastStepVehicleNumber, etc.)
    """
    return {
        "device_id":      capteur["device_id"],
        "location":       capteur["location"],
        "timestamp":      datetime.now().isoformat(),
        "nb_vehicles":    random.randint(0, 40),
        "avg_speed_kmh":  round(random.uniform(10.0, 90.0), 1),
        "occupancy_pct":  round(random.uniform(0.0, 100.0), 1),
        "status":         random.choice(["normal", "congested", "fluide"]),
    }


# ─── Programme principal ──────────────────────────────────────────────────────
def main():
    client = mqtt.Client(client_id=CLIENT_ID)
    client.on_connect = on_connect
    client.on_publish  = on_publish

    print(f"🔌 Connexion au broker MQTT → {BROKER_HOST}:{BROKER_PORT}")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    time.sleep(1)  # laisser la connexion s'établir

    print(f"\n🚦 Début de la publication — {NB_MESSAGES} messages sur '{TOPIC}'\n")

    for i in range(NB_MESSAGES):
        capteur = CAPTEURS[i % len(CAPTEURS)]
        payload = generer_donnees(capteur)

        result = client.publish(
            topic   = TOPIC,
            payload = json.dumps(payload),
            qos     = 1,          # QoS 1 = au moins une fois
        )

        print(f"[{i+1:03d}/{NB_MESSAGES}] {payload['device_id']} → "
              f"véhicules={payload['nb_vehicles']:02d}  "
              f"vitesse={payload['avg_speed_kmh']} km/h  "
              f"état={payload['status']}")

        time.sleep(INTERVAL_SEC)

    client.loop_stop()
    client.disconnect()
    print(f"\n✅ Terminé — {NB_MESSAGES} messages publiés sur '{TOPIC}'")


if __name__ == "__main__":
    main()
