import traci
import pandas as pd
import os

SUMO_CMD = [
    "sumo",
    "-c", os.path.expanduser("~/smart_traffic/sumo/rabat.sumocfg"),
    "--no-step-log",
    "--no-warnings"
]

CAM_IDS = ['cam_01','cam_02','cam_03','cam_04','cam_05',
           'cam_06','cam_07','cam_08','cam_09','cam_10',
           'cam_11','cam_12','cam_13','cam_14','cam_15',
           'cam_16','cam_17','cam_18','cam_19','cam_20']

SNAPSHOT_INTERVAL = 600

def run_simulation():
    traci.start(SUMO_CMD)

    loaded = traci.inductionloop.getIDList()
    print(f"Détecteurs chargés : {len(loaded)}")

    # Accumulateurs
    acc_count = {cam: 0 for cam in CAM_IDS}
    acc_speed  = {cam: [] for cam in CAM_IDS}
    acc_occ    = {cam: [] for cam in CAM_IDS}

    records = []
    step = 0
    print("Simulation démarrée...")

    while traci.simulation.getMinExpectedNumber() > 0 and step < 3600:
        traci.simulationStep()
        step += 1

        for cam in CAM_IDS:
            try:
                n = traci.inductionloop.getLastStepVehicleNumber(cam)
                acc_count[cam] += n

                spd = traci.inductionloop.getLastStepMeanSpeed(cam)
                if spd >= 0:  # -1 = aucun véhicule ce step
                    acc_speed[cam].append(spd)

                occ = traci.inductionloop.getLastStepOccupancy(cam)
                if occ > 0:
                    acc_occ[cam].append(occ)
            except Exception:
                pass

        if step % SNAPSHOT_INTERVAL == 0:
            t = traci.simulation.getTime()
            active = traci.vehicle.getIDCount()
            print(f"  t={t:.0f}s — véhicules actifs: {active}")

            for cam in CAM_IDS:
                count = acc_count[cam]
                avg_speed = round(sum(acc_speed[cam]) / len(acc_speed[cam]) * 3.6, 1) \
                            if acc_speed[cam] else 0.0
                avg_occ   = round(sum(acc_occ[cam]) / len(acc_occ[cam]), 3) \
                            if acc_occ[cam] else 0.0
                congested = avg_speed > 0 and avg_speed < 20 or avg_occ > 0.5

                records.append({
                    "time_s":    t,
                    "camera":    cam,
                    "vehicles":  count,
                    "speed_kmh": avg_speed,
                    "occupancy": avg_occ,
                    "congested": congested
                })

            # Réinitialisation
            acc_count = {cam: 0 for cam in CAM_IDS}
            acc_speed  = {cam: [] for cam in CAM_IDS}
            acc_occ    = {cam: [] for cam in CAM_IDS}

    traci.close()

    df = pd.DataFrame(records)
    out = os.path.expanduser("~/smart_traffic/sumo/traffic_data.csv")
    df.to_csv(out, index=False)
    print(f"\nTerminé — {len(records)} enregistrements sauvegardés")

    # Résumé par caméra
    summary = df.groupby("camera").agg(
        total_vehicules=("vehicles", "sum"),
        vitesse_moy=("speed_kmh", lambda x: round(x[x>0].mean(), 1) if (x>0).any() else 0),
        congestion_pct=("congested", lambda x: f"{100*x.mean():.0f}%")
    ).sort_values("total_vehicules", ascending=False)

    print("\n=== Résumé par caméra ===")
    print(summary.to_string())

if __name__ == "__main__":
    run_simulation()
