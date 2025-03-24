import json
import time
from kafka import KafkaProducer

KAFKA_BROKER = ["localhost:9093", "localhost:9094"]  # Von deinem Host aus

with open("track.json") as f:
    tracks = json.load(f)["tracks"]

print("Verfügbare Tracks:")
for t in tracks:
    print(f"Track {t['trackId']} mit {len(t['segments'])} Segmenten.")

track_id = input("Wähle einen Track (Track ID): ").strip()
selected = None
for t in tracks:
    if t["trackId"] == track_id:
        selected = t
        break

if not selected:
    print("Track nicht gefunden.")
    exit(1)

# Suche das start-goal Segment des ausgewählten Tracks
start_segment = None
for seg in selected["segments"]:
    if seg["type"] == "start-goal":
        start_segment = seg
        break

if not start_segment:
    print("Kein start-goal Segment gefunden.")
    exit(1)

token_name = input("Gib den Namen des Tokens/Pferdes ein: ").strip()

# Erstelle ein Token-Dictionary
token = {
    "token_name": token_name,
    "track_id": track_id,
    "segment_id": start_segment["segmentId"],
    "rounds": 0,
    "start_time": time.time()
}

producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)
# Sende das Token an den Kafka-Topic des start-goal Segments
producer.send(start_segment["segmentId"], json.dumps(token).encode('utf-8'))
producer.flush()
print(f"Token '{token_name}' gestartet auf Track {track_id} im Segment '{start_segment['segmentId']}'.")
