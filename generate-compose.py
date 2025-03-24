import json
import yaml

with open("track.json") as f:
    tracks = json.load(f)["tracks"]

compose = {
    "version": "3",
    "services": {}
}

# Für jeden Track und jedes Segment einen Service hinzufügen
for track in tracks:
    track_id = track["trackId"]
    for seg in track["segments"]:
        service_name = f"track{track_id}_{seg['segmentId']}"
        env = {
            "SEGMENT_ID": seg["segmentId"],
            "SEGMENT_TYPE": seg["type"],
            "TRACK_ID": track_id,
            "KAFKA_BROKER": "kafka:9092"
        }
        # Wenn NEXT_SEGMENT definiert ist, den ersten Eintrag verwenden
        if seg.get("nextSegments"):
            env["NEXT_SEGMENT"] = seg["nextSegments"][0]
        compose["services"][service_name] = {
            "image": "segment-image",  # Unser zuvor gebuildetes Image
            "environment": env,
            "restart": "always"
        }

with open("docker-compose.generated.yml", "w") as f:
    yaml.dump(compose, f, default_flow_style=False)

print("docker-compose.generated.yml wurde generiert.")
