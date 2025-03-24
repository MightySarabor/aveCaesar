#!/usr/bin/env python3
import json
import time
from kafka import KafkaProducer, KafkaConsumer

# Konfiguration für den Kafka-Cluster (anpassen falls nötig)
KAFKA_BROKER = ["localhost:9093", "localhost:9094"]

# Hilfsfunktion: Extrahiere die Tracknummer aus einer Segment-ID.
def extract_track(seg_id):
    if seg_id.startswith("start-and-goal-"):
        parts = seg_id.split("-")
        try:
            return int(parts[-1])
        except:
            return None
    elif seg_id.startswith("segment-"):
        parts = seg_id.split("-")
        try:
            return int(parts[1])
        except:
            return None
    else:
        return None

# Lade den Track aus der JSON-Datei
with open("track.json") as f:
    tracks = json.load(f)["tracks"]

print("Verfügbare Tracks:")
for t in tracks:
    print(f"Track {t['trackId']} mit {len(t['segments'])} Segmenten.")

# Für jeden Track einen Token (Pferd) starten:
tokens = {}  # key: token_name, value: token-Dict (enthält auch track_id)
for track in tracks:
    track_id = track["trackId"]
    token_name = input(f"Gib den Namen des Tokens/Pferdes für Track {track_id} ein: ").strip()
    # Suche das start-goal-Segment in diesem Track
    start_segment = None
    for seg in track["segments"]:
        # Bei normalen Segmenten fehlt "type" oft, also standardmäßig "normal"
        if seg.get("type", "normal") == "start-goal":
            start_segment = seg
            break
    if not start_segment:
        print(f"Kein start-goal Segment für Track {track_id} gefunden!")
        continue
    token = {
        "token_name": token_name,
        "track_id": track_id,
        "segment_id": start_segment["segmentId"],
        "rounds": 0,
        "start_time": time.time()
    }
    tokens[token_name] = token

# Kafka Producer initialisieren
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)
# Sende für jeden Token die Startmeldung an das jeweilige Start-goal-Segment
for track in tracks:
    track_id = track["trackId"]
    token = None
    for tname, tok in tokens.items():
        if tok["track_id"] == track_id:
            token = tok
            break
    if token:
        start_segment = None
        for seg in track["segments"]:
            if seg.get("type", "normal") == "start-goal":
                start_segment = seg
                break
        if start_segment:
            producer.send(start_segment["segmentId"], json.dumps(token).encode("utf-8"))
            producer.flush()
            print(f"Token '{token['token_name']}' gestartet auf Track {track_id} im Segment '{start_segment['segmentId']}'.")

print("\nAlle Tokens gestartet. Rennen beginnt...\n")

# Wir möchten alle 3 Sekunden den aktuellen Status anzeigen.
# Darin soll nur bei Trackwechsel eine zusätzliche Meldung erscheinen.
# Dazu speichern wir den aktuellen Status jedes Tokens:
# token_status = { token_name: {"segment": <Segment-ID>, "track": <Track-Nummer>, "last_update": <Timestamp>} }
token_status = {}

# Kafka-Consumer initialisieren; wir abonnieren ALLE Topics.
consumer = KafkaConsumer(
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset="latest",  # nur zukünftige Nachrichten
    group_id=f"controller_{list(tokens.keys())[0]}",
    enable_auto_commit=True
)
consumer.subscribe(pattern=".*")

# Umrechnungsfaktor: 1 Sekunde entspricht 42 Sandkörnern (zum Augenzwinkern)
SAND_KOERNER_FACTOR = 42
last_print = time.time()
PRINT_INTERVAL = 3  # Ausgabe alle 3 Sekunden

winner = None

while True:
    msg_pack = consumer.poll(timeout_ms=500)
    for tp, messages in msg_pack.items():
        for message in messages:
            try:
                updated_token = json.loads(message.value.decode("utf-8"))
            except Exception as e:
                continue
            tname = updated_token.get("token_name")
            if tname not in tokens:
                continue
            # Bestimme das aktuelle Segment anhand des Topics
            new_segment = message.topic
            new_track = extract_track(new_segment)
            current_time = time.time()
            # Prüfe, ob wir bereits einen Status für diesen Token haben.
            if tname in token_status:
                prev = token_status[tname]
                prev_track = prev.get("track")
                if new_track is not None and prev_track is not None and new_track != prev_track:
                    # Spezielle Ausgabe bei Trackwechsel:
                    print(f"*** Reiter '{tname}' wechselt Track: Von Track {prev_track} (Segment '{prev['segment']}') nach Track {new_track} (Segment '{new_segment}'). ***")
            else:
                # Erste Statusmeldung für diesen Token
                print(f"Reiter '{tname}' ist gestartet in Segment '{new_segment}'.")
            # Aktualisiere den Status
            token_status[tname] = {"segment": new_segment, "track": new_track, "last_update": current_time}
            # Überprüfe, ob dieser Token fertig ist:
            if "finish_time" in updated_token:
                winner = updated_token
                break
        if winner:
            break
    if winner:
        break
    # Alle 3 Sekunden: Normale Statusausgabe (ohne Trackwechsel-Hervorhebung)
    if time.time() - last_print >= PRINT_INTERVAL:
        print("\n--- Aktueller Gesamtstatus ---")
        for tname, status in token_status.items():
            print(f"Reiter '{tname}' in Segment '{status['segment']}' (Track {status['track']})")
        print("------------------------------\n")
        last_print = time.time()

# Sobald ein Token fertig ist, wird das Rennen beendet.
finish_time = winner["finish_time"]
start_time = winner["start_time"]
elapsed = finish_time - start_time
sandkoerner = int(elapsed * SAND_KOERNER_FACTOR)
print(f"\nRennen beendet! Sieger: '{winner['token_name']}' hat das Rennen in ca. {sandkoerner} Sandkörnern "
      f"(entspricht {elapsed:.2f} Sekunden) beendet.")
