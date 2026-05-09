import sumolib, os
net = sumolib.net.readNet(os.path.expanduser("~/smart_traffic/sumo/rabat.net.xml"))
candidates = []
for edge in net.getEdges():
    if edge.getSpeed() >= 11.1 and edge.getLaneNumber() >= 1:
        candidates.append(edge)
candidates.sort(key=lambda e: -e.getSpeed() * e.getLaneNumber())
selected = candidates[:20]
with open(os.path.expanduser("~/smart_traffic/sumo/detectors.add.xml"), "w") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<additionals>\n')
    for i, edge in enumerate(selected):
        lane_id = edge.getLanes()[0].getID()
        name = edge.getName() or edge.getID()
        f.write(f'  <e1Detector id="cam_{i+1:02d}" lane="{lane_id}" pos="50" freq="60" file="cam_{i+1:02d}.xml" friendlyPos="true"/>\n')
    f.write('</additionals>\n')
print(f"OK: {len(selected)} cameras generees")
cam_ids = [f"cam_{i+1:02d}" for i in range(len(selected))]
print("CAM_IDS =", cam_ids)
