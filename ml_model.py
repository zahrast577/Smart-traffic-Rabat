import pandas as pd
import sqlite3
import os
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder

DB_PATH = os.path.expanduser("~/smart_traffic/sumo/traffic.db")
MODEL_PATH = os.path.expanduser("~/smart_traffic/sumo/model.pkl")

def load_data():
    # Charge depuis CSV si DB vide
    csv = os.path.expanduser("~/smart_traffic/sumo/traffic_data.csv")
    df = pd.read_csv(csv)
    # Insère dans la DB
    conn = sqlite3.connect(DB_PATH)
    df["congested"] = df["congested"].map({True: 1, False: 0, "True": 1, "False": 0})
    df.to_sql("traffic_data", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Données chargées : {len(df)} lignes")
    return df

def train_model(df):
    le = LabelEncoder()
    df["camera_enc"] = le.fit_transform(df["camera"])

    features = ["time_s", "camera_enc", "vehicles", "speed_kmh", "occupancy"]
    X = df[features]
    y = df["congested"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n=== Performance du modèle ===")
    print(classification_report(y_test, y_pred,
          target_names=["Fluide", "Congestionné"]))

    # Sauvegarde
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "encoder": le}, f)
    print(f"Modèle sauvegardé : {MODEL_PATH}")
    return model, le

def predict(camera, time_s, vehicles, speed_kmh, occupancy):
    with open(MODEL_PATH, "rb") as f:
        obj = pickle.load(f)
    model = obj["model"]
    le    = obj["encoder"]
    cam_enc = le.transform([camera])[0] if camera in le.classes_ else 0
    X = [[time_s, cam_enc, vehicles, speed_kmh, occupancy]]
    pred = model.predict(X)[0]
    proba = model.predict_proba(X)[0][pred]
    return bool(pred), round(float(proba), 2)

if __name__ == "__main__":
    df = load_data()
    train_model(df)
    # Test
    congested, conf = predict("cam_06", 1800, 11, 15.6, 0.0)
    print(f"\nTest cam_06 : congestionné={congested}, confiance={conf}")
