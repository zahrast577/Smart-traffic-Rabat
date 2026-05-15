from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import sqlite3, os, pickle, json, threading, logging

# ─── MQTT (optionnel : désactivé si paho non installé) ───────────────────────
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.warning("paho-mqtt non installé — subscriber MQTT désactivé. "
                    "Installez-le avec : pip install paho-mqtt")

app = Flask(__name__)
CORS(app)

# ─── Chemins ──────────────────────────────────────────────────────────────────
DB_PATH    = os.path.expanduser("~/smart_traffic/sumo/traffic.db")
MODEL_PATH = os.path.expanduser("~/smart_traffic/sumo/model.pkl")

# ─── MQTT config ──────────────────────────────────────────────────────────────
MQTT_BROKER = "localhost"
MQTT_PORT   = 1883
MQTT_TOPIC  = "traffic/sensors"

# ─── Helpers DB ───────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(sql, args=()):
    conn = get_conn()
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_sensor_data(data: dict):
    """Insère une mesure capteur dans traffic_data."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO traffic_data
                (time_s, camera, vehicles, speed_kmh, occupancy, congested)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get("time_s", 0),
            data.get("camera", "unknown"),
            data.get("vehicles", 0),
            data.get("speed_kmh", 0.0),
            data.get("occupancy", 0.0),
            int(data.get("congested", 0)),
        ))
        conn.commit()
    except Exception as e:
        logging.error(f"[DB] Erreur insertion : {e}")
    finally:
        conn.close()

# ─── MQTT callbacks ───────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info(f"[MQTT] Connecté au broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC, qos=1)
        logging.info(f"[MQTT] Abonné au topic : {MQTT_TOPIC}")
    else:
        logging.error(f"[MQTT] Échec de connexion, code : {rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        insert_sensor_data(data)
        logging.debug(f"[MQTT] Reçu → {data.get('camera')} | "
                      f"{data.get('vehicles')} véh. | {data.get('speed_kmh')} km/h")
    except json.JSONDecodeError as e:
        logging.error(f"[MQTT] Payload JSON invalide : {e}")
    except Exception as e:
        logging.error(f"[MQTT] Erreur traitement message : {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logging.warning(f"[MQTT] Déconnecté de façon inattendue (code {rc}). "
                        "Tentative de reconnexion automatique...")

def start_mqtt():
    """Lance le subscriber MQTT dans un thread daemon."""
    if not MQTT_AVAILABLE:
        return
    try:
        client = mqtt.Client(client_id="flask_subscriber")
        client.on_connect    = on_connect
        client.on_message    = on_message
        client.on_disconnect = on_disconnect
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()          # bloquant — tourne dans son propre thread
    except Exception as e:
        logging.error(f"[MQTT] Impossible de démarrer le subscriber : {e}")

# ─── Endpoints REST ───────────────────────────────────────────────────────────
@app.route("/api/latest")
def latest():
    rows = query_db("""
        SELECT time_s, camera, vehicles, speed_kmh, occupancy, congested
        FROM   traffic_data
        ORDER  BY time_s DESC
        LIMIT  120
    """)
    return jsonify(rows)

@app.route("/api/summary")
def summary():
    rows = query_db("""
        SELECT camera,
               SUM(vehicles)                                          AS total_vehicles,
               ROUND(AVG(CASE WHEN speed_kmh > 0 THEN speed_kmh END), 1) AS avg_speed,
               ROUND(AVG(congested) * 100, 1)                        AS congestion_pct
        FROM   traffic_data
        GROUP  BY camera
        ORDER  BY total_vehicles DESC
    """)
    return jsonify(rows)

@app.route("/api/predict/<camera>/<int:vehicles>/<float:speed>")
def predict(camera, vehicles, speed):
    try:
        with open(MODEL_PATH, "rb") as f:
            obj = pickle.load(f)
        model = obj["model"]
        le    = obj["encoder"]
        cam_enc = le.transform([camera])[0] if camera in le.classes_ else 0
        X       = [[1800, cam_enc, vehicles, speed, 0.0]]
        pred    = model.predict(X)[0]
        proba   = model.predict_proba(X)[0][pred]
        return jsonify({
            "camera":     camera,
            "congested":  bool(pred),
            "confidence": round(float(proba), 2),
            "status":     "Congestionné" if pred else "Fluide",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sensors", methods=["POST"])
def sensors_post():
    """Endpoint HTTP alternatif pour injecter des données sans MQTT."""
    from flask import request
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Payload JSON manquant"}), 400
    insert_sensor_data(data)
    return jsonify({"status": "ok"}), 201

@app.route("/api/stats")
def stats():
    rows = query_db("""
        SELECT COUNT(*)                              AS total_records,
               COUNT(DISTINCT camera)               AS total_cameras,
               SUM(vehicles)                        AS total_vehicles,
               ROUND(AVG(speed_kmh), 1)             AS avg_speed_global,
               ROUND(AVG(congested) * 100, 1)       AS congestion_pct_global,
               MAX(time_s)                          AS last_update
        FROM   traffic_data
    """)
    return jsonify(rows[0] if rows else {})

@app.route("/api/devices")
def devices():
    rows = query_db("""
        SELECT DISTINCT camera,
               MAX(time_s)     AS last_seen,
               MAX(vehicles)   AS max_vehicles
        FROM   traffic_data
        GROUP  BY camera
        ORDER  BY camera
    """)
    return jsonify(rows)

# ─── Dashboard HTML ───────────────────────────────────────────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Smart Traffic — Rabat</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',sans-serif; background:#0f172a; color:#e2e8f0; }
header { background:#1e293b; padding:20px 40px; border-bottom:2px solid #3b82f6; display:flex; justify-content:space-between; align-items:center; }
header h1 { font-size:1.5rem; color:#3b82f6; }
header p  { font-size:.85rem; color:#94a3b8; margin-top:4px; }
.mqtt-status { display:flex; align-items:center; gap:8px; font-size:.8rem; color:#94a3b8; }
.mqtt-dot { width:10px; height:10px; border-radius:50%; background:#22c55e; animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:20px; padding:30px; }
.card { background:#1e293b; border-radius:12px; padding:24px; border:1px solid #334155; }
.card.full { grid-column:1/-1; }
.card h3 { font-size:.85rem; color:#94a3b8; margin-bottom:12px; text-transform:uppercase; letter-spacing:.05em; }
.stat { font-size:2.2rem; font-weight:700; color:#f1f5f9; }
.stat span { font-size:1rem; color:#94a3b8; font-weight:400; margin-left:4px; }
table { width:100%; border-collapse:collapse; }
th { background:#0f172a; color:#64748b; padding:10px 14px; text-align:left; font-size:.8rem; text-transform:uppercase; }
td { padding:11px 14px; border-bottom:1px solid #1e293b; font-size:.9rem; }
tr:last-child td { border-bottom:none; }
.badge { display:inline-block; padding:3px 12px; border-radius:99px; font-size:.75rem; font-weight:600; }
.red    { background:#450a0a; color:#fca5a5; }
.orange { background:#431407; color:#fdba74; }
.green  { background:#052e16; color:#86efac; }
.dot    { width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:6px; }
.dot-r  { background:#ef4444; }
.dot-o  { background:#f97316; }
.dot-g  { background:#22c55e; }
canvas  { max-height:280px; }
#btn-refresh { position:fixed; bottom:24px; right:24px; background:#3b82f6; border:none;
               color:white; padding:12px 22px; border-radius:10px; cursor:pointer;
               font-size:.9rem; font-weight:600; box-shadow:0 4px 14px rgba(59,130,246,.4); }
#btn-refresh:hover { background:#2563eb; }
</style>
</head>
<body>
<header>
  <div>
    <h1>Smart Traffic Monitoring — Rabat</h1>
    <p id="last-update">Chargement des données...</p>
  </div>
  <div class="mqtt-status">
    <div class="mqtt-dot"></div>
    <span>MQTT actif</span>
  </div>
</header>

<div class="grid">
  <div class="card">
    <h3>Total véhicules détectés</h3>
    <div class="stat" id="kpi-vehicles">—</div>
  </div>
  <div class="card">
    <h3>Vitesse moyenne globale</h3>
    <div class="stat" id="kpi-speed">— <span>km/h</span></div>
  </div>
  <div class="card">
    <h3>Caméras en congestion</h3>
    <div class="stat" id="kpi-congested">—</div>
  </div>

  <div class="card full">
    <h3>Flux de véhicules par caméra</h3>
    <canvas id="chart-flux"></canvas>
  </div>

  <div class="card full">
    <h3>Détail par caméra</h3>
    <table>
      <thead><tr>
        <th>Caméra</th><th>Véhicules</th><th>Vitesse moy.</th>
        <th>Congestion %</th><th>Statut</th>
      </tr></thead>
      <tbody id="table-body"></tbody>
    </table>
  </div>
</div>

<button id="btn-refresh" onclick="loadData()">Actualiser</button>

<script>
let fluxChart = null;

async function loadData() {
  document.getElementById("last-update").textContent =
    "Mis à jour : " + new Date().toLocaleTimeString("fr-FR");

  const [summary, latest] = await Promise.all([
    fetch("/api/summary").then(r => r.json()),
    fetch("/api/latest").then(r => r.json())
  ]);

  const active = summary.filter(r => r.total_vehicles > 0);

  // KPIs
  const totalV = summary.reduce((s, r) => s + (r.total_vehicles || 0), 0);
  const speeds = active.map(r => r.avg_speed || 0).filter(s => s > 0);
  const avgSpd = speeds.length ? (speeds.reduce((a,b) => a+b, 0) / speeds.length).toFixed(1) : "0";
  const nCong  = active.filter(r => (r.avg_speed||0) > 0 && (r.avg_speed||0) < 20).length;

  document.getElementById("kpi-vehicles").textContent  = totalV;
  document.getElementById("kpi-speed").innerHTML       = avgSpd + ' <span>km/h</span>';
  document.getElementById("kpi-congested").textContent = nCong + " / " + active.length;

  // Tableau
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = active.map(r => {
    const spd = (r.avg_speed || 0).toFixed(1);
    const pct = (r.congestion_pct || 0).toFixed(0);
    const slow = r.avg_speed > 0 && r.avg_speed < 20;
    const med  = r.avg_speed >= 20 && r.avg_speed < 40;
    const cls  = slow ? "red"   : med ? "orange" : "green";
    const dot  = slow ? "dot-r" : med ? "dot-o"  : "dot-g";
    const lbl  = slow ? "Congestionné" : med ? "Modéré" : "Fluide";
    return `<tr>
      <td><strong>${r.camera}</strong></td>
      <td>${r.total_vehicles}</td>
      <td>${spd} km/h</td>
      <td>${pct}%</td>
      <td><span class="dot ${dot}"></span><span class="badge ${cls}">${lbl}</span></td>
    </tr>`;
  }).join("");

  // Graphique
  const cameras = [...new Set(latest.map(r => r.camera))].filter(c =>
    active.find(a => a.camera === c)
  );
  const times = [...new Set(latest.map(r => r.time_s))].sort((a,b) => a-b);
  const colors = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16"];

  const datasets = cameras.slice(0, 8).map((cam, i) => ({
    label: cam,
    data: times.map(t => {
      const r = latest.find(x => x.camera === cam && x.time_s === t);
      return r ? r.vehicles : 0;
    }),
    borderColor:     colors[i % colors.length],
    backgroundColor: colors[i % colors.length] + "22",
    tension: 0.4,
    fill: false,
    pointRadius: 4
  }));

  if (fluxChart) fluxChart.destroy();
  fluxChart = new Chart(document.getElementById("chart-flux"), {
    type: "line",
    data: {
      labels: times.map(t => Math.round(t / 60) + " min"),
      datasets
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#cbd5e1", font: { size: 12 } } }
      },
      scales: {
        x: { ticks: { color:"#94a3b8" }, grid: { color:"#1e293b" } },
        y: { ticks: { color:"#94a3b8" }, grid: { color:"#334155" },
             title: { display:true, text:"Véhicules / période", color:"#64748b" } }
      }
    }
  });
}

loadData();
setInterval(loadData, 30000);
</script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

# ─── Démarrage ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Lance le subscriber MQTT en arrière-plan
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True, name="mqtt-subscriber")
    mqtt_thread.start()

    app.run(debug=True, port=5000, use_reloader=False)
    # use_reloader=False est OBLIGATOIRE avec le thread MQTT
    # (sinon Flask redémarre le process et lance 2 threads MQTT)