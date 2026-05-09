import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

df = pd.read_csv(os.path.expanduser("~/smart_traffic/sumo/traffic_data.csv"))

# Seulement les caméras actives
active_cams = df.groupby("camera")["vehicles"].sum()
active_cams = active_cams[active_cams > 0].index.tolist()
df_active = df[df["camera"].isin(active_cams)]

fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle("Smart Traffic Monitoring — Rabat", fontsize=18, fontweight="bold")

# --- Graphe 1 : Véhicules par caméra au fil du temps ---
ax1 = axes[0, 0]
for cam in active_cams:
    sub = df[df["camera"] == cam]
    ax1.plot(sub["time_s"] / 60, sub["vehicles"], marker="o", label=cam)
ax1.set_title("Flux de véhicules par caméra")
ax1.set_xlabel("Temps (min)")
ax1.set_ylabel("Véhicules / période")
ax1.legend(fontsize=7, ncol=2)
ax1.grid(True, alpha=0.3)

# --- Graphe 2 : Vitesse moyenne par caméra ---
ax2 = axes[0, 1]
summary = df.groupby("camera").agg(
    vehicles=("vehicles","sum"),
    speed=("speed_kmh", lambda x: x[x>0].mean() if (x>0).any() else 0)
).reset_index()
summary = summary[summary["vehicles"] > 0].sort_values("speed")
colors = ["red" if s < 20 else "orange" if s < 40 else "green" for s in summary["speed"]]
bars = ax2.barh(summary["camera"], summary["speed"], color=colors)
ax2.set_title("Vitesse moyenne par caméra")
ax2.set_xlabel("Vitesse (km/h)")
ax2.axvline(20, color="red", linestyle="--", alpha=0.5, label="Seuil congestion")
ax2.axvline(50, color="green", linestyle="--", alpha=0.5, label="Fluide")
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3, axis="x")

# --- Graphe 3 : Total véhicules par caméra (bar chart) ---
ax3 = axes[1, 0]
summary2 = df.groupby("camera")["vehicles"].sum().sort_values(ascending=False)
summary2 = summary2[summary2 > 0]
ax3.bar(summary2.index, summary2.values, color="steelblue")
ax3.set_title("Total véhicules détectés par caméra")
ax3.set_xlabel("Caméra")
ax3.set_ylabel("Total véhicules")
ax3.tick_params(axis="x", rotation=45)
ax3.grid(True, alpha=0.3, axis="y")

# --- Graphe 4 : Heatmap congestion ---
ax4 = axes[1, 1]
pivot = df_active.pivot_table(index="camera", columns="time_s", values="speed_kmh", aggfunc="mean")
im = ax4.imshow(pivot.values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=80)
ax4.set_title("Heatmap vitesse (Rouge=lent, Vert=fluide)")
ax4.set_xticks(range(len(pivot.columns)))
ax4.set_xticklabels([f"{int(t/60)}min" for t in pivot.columns], rotation=45, fontsize=7)
ax4.set_yticks(range(len(pivot.index)))
ax4.set_yticklabels(pivot.index, fontsize=8)
plt.colorbar(im, ax=ax4, label="km/h")

plt.tight_layout()
out = os.path.expanduser("~/smart_traffic/sumo/traffic_dashboard.png")
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Dashboard sauvegardé : {out}")
