#!/usr/bin/env python3
import os
import time
import json
import random
import threading
from kafka import KafkaConsumer, KafkaProducer

# Globales Dictionary für den Status von Segmenten
field_status = {}  # {segment_id: "free" / "occupied" / "waiting"}

def update_field_status():
    """
    Liest kontinuierlich das Kafka-Topic "segment_status" und aktualisiert
    den lokalen Cache (field_status). So kann jeder Segment-Prozess den Belegungszustand der anderen Felder erkennen.
    """
    consumer = KafkaConsumer(
        "segment_status",
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='earliest',
        group_id=f"status_listener_{SEGMENT_ID}"
    )
    for msg in consumer:
        try:
            data = json.loads(msg.value.decode("utf-8"))
            seg = data.get("segment_id")
            status = data.get("status")
            if seg:
                field_status[seg] = status
                print(f"[Status Update] Segment '{seg}' ist jetzt '{status}'")
        except Exception as e:
            print("Fehler beim Aktualisieren des Feldstatus:", e)

# Starte einen Thread, der den Status-Topic kontinuierlich abruft.
status_thread = threading.Thread(target=update_field_status, daemon=True)

def extract_track(segment_id):
    """
    Extrahiert aus einer Segment-ID (z. B. "segment-2-3" oder "start-and-goal-3")
    die Track-Nummer als Integer.
    """
    if segment_id.startswith("segment-"):
        parts = segment_id.split("-")
        try:
            return int(parts[1])
        except:
            return float('inf')
    elif segment_id.startswith("start-and-goal-"):
        parts = segment_id.split("-")
        try:
            return int(parts[2])
        except:
            return float('inf')
    return float('inf')

def select_next_segment(default_next, visible_str):
    """
    Wählt aus dem Standardziel (default_next) und den alternativen Kandidaten (VISIBLE_SEGMENTS)
    den ersten Kandidaten aus, der im field_status als "free" markiert ist.
    Gibt None zurück, wenn keiner frei ist.
    """
    candidates = []
    if default_next:
        candidates.append(default_next)
    if visible_str:
        for seg in visible_str.split(","):
            seg = seg.strip()
            if seg:
                candidates.append(seg)
    # Duplikate entfernen und nach Track-Nummer sortieren
    candidates = list(dict.fromkeys(candidates))
    candidates.sort(key=lambda x: extract_track(x))
    for candidate in candidates:
        if field_status.get(candidate, "free") == "free":
            return candidate
    return None

def publish_segment_status(status):
    """
    Sendet eine Statusnachricht (zum Beispiel "free", "occupied" oder "waiting")
    an das Kafka-Topic "segment_status". Damit wissen alle Prozesse, ob ein Feld belegt, frei oder in Wartestellung ist.
    """
    msg = {
        "segment_id": SEGMENT_ID,
        "status": status,
        "timestamp": time.time()
    }
    producer.send("segment_status", json.dumps(msg).encode("utf-8"), key=SEGMENT_ID.encode("utf-8"))
    producer.flush()

# ------------------ Umgebungsvariablen einlesen ------------------
SEGMENT_ID = os.environ.get("SEGMENT_ID", "unknown")
SEGMENT_TYPE = os.environ.get("SEGMENT_TYPE", "normal")  # z. B. "start-goal", "normal", "avecaeser"
TRACK_ID = os.environ.get("TRACK_ID", "unknown")
NEXT_SEGMENT = os.environ.get("NEXT_SEGMENT")
VISIBLE_SEGMENTS = os.environ.get("VISIBLE_SEGMENTS")
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")

# ------------------ Kafka Producer und Consumer initialisieren ------------------
# Es wird angenommen, dass Topics automatisch erstellt werden
producer = KafkaProducer(bootstrap_servers=[KAFKA_BROKER])
consumer = KafkaConsumer(
    SEGMENT_ID,
    bootstrap_servers=[KAFKA_BROKER],
    auto_offset_reset="earliest",
    group_id=SEGMENT_ID
)

print(f"Segment {SEGMENT_ID} ({SEGMENT_TYPE}) auf Track {TRACK_ID} gestartet. Lausche auf Topic '{SEGMENT_ID}'.")
status_thread.start()

# Initial wird der Status "free" gesendet.
publish_segment_status("free")

# ------------------ Hauptschleife: Verarbeitung hereinkommender Tokens ------------------
for message in consumer:
    try:
        token = json.loads(message.value.decode("utf-8"))
    except Exception as e:
        print("Fehler beim Dekodieren des Tokens:", e)
        continue

    print(f"\nSegment {SEGMENT_ID} hat Token erhalten: {token}")
    # Beim Start der Verarbeitung wird der Status als "occupied" gesendet.
    publish_segment_status("occupied")
    
    # Simuliere Bearbeitungszeit (2-3 Sekunden)
    delay = random.uniform(2, 3)
    print(f"Verarbeite Token für {delay:.2f} Sekunden...")
    time.sleep(delay)
    
    # Sonderlogik für Start-/Ziel-Segmente (Runden erhöhen, evtl. Rennen beenden)
    if SEGMENT_TYPE == "start-goal":
        token["rounds"] = token.get("rounds", 0) + 1
        print(f"Token-Runden erhöht: {token['rounds']}")
        if token["rounds"] >= 3:
            token["finish_time"] = time.time()
            finish_topic = "times"
            producer.send(finish_topic, json.dumps(token).encode("utf-8"))
            producer.flush()
            print(f"Token abgeschlossen. Zeitpublikation an Topic '{finish_topic}'.")
            publish_segment_status("free")
            continue

    # ------------------ Kollisions- & Weiterleitungslogik ------------------
    # Falls NEXT_SEGMENT oder VISIBLE_SEGMENTS definiert sind, wird ein Kandidat gesucht.
    if NEXT_SEGMENT or VISIBLE_SEGMENTS:
        candidate = None
        while candidate is None:
            candidate = select_next_segment(NEXT_SEGMENT, VISIBLE_SEGMENTS)
            if candidate is None:
                print(f"Alle Kandidaten in Segment {SEGMENT_ID} sind besetzt. Token muss warten.")
                publish_segment_status("waiting")
                time.sleep(1)
        print(f"Segment {SEGMENT_ID} leitet Token an '{candidate}' weiter.")
        # Das Token (das "Pferd") wird an das nächste Segment-Topic versendet.
        producer.send(candidate, json.dumps(token).encode("utf-8"))
        producer.flush()
    else:
        print(f"Segment {SEGMENT_ID} hat weder NEXT_SEGMENT noch VISIBLE_SEGMENTS definiert. Token-Verarbeitung endet hier.")
    
    # Nach Abschluss der Verarbeitung wird der Status wieder auf "free" gesetzt.
    publish_segment_status("free")
