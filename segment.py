#!/usr/bin/env python3
import os
import time
import json
import random
import threading
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

# ---------------------------------------------------------------------------
# Funktion: Kafka-Topic erstellen (falls noch nicht vorhanden)
# ---------------------------------------------------------------------------
def create_topic_if_not_exists(topic_name, num_partitions=6, replication_factor=3, kafka_broker='localhost:9092'):
    """
    Erstellt ein Kafka-Topic mit den angegebenen Parametern,
    falls dieses noch nicht existiert.
    """
    admin_client = KafkaAdminClient(bootstrap_servers=kafka_broker, client_id='topic_creator')
    topic_list = []
    topic = NewTopic(name=topic_name, num_partitions=num_partitions, replication_factor=replication_factor)
    topic_list.append(topic)
    try:
        admin_client.create_topics(new_topics=topic_list, validate_only=False)
        print(f"Topic '{topic_name}' wurde erstellt mit {num_partitions} Partitionen und Replikationsfaktor {replication_factor}.")
    except TopicAlreadyExistsError:
        print(f"Topic '{topic_name}' existiert bereits.")
    except Exception as e:
        print(f"Fehler beim Erstellen des Topics '{topic_name}': {e}")
    finally:
        admin_client.close()

# ---------------------------------------------------------------------------
# Statusverwaltung: Aktualisieren des Status aller Felder
# ---------------------------------------------------------------------------
field_status = {}  # globales Dictionary: {segment_id: "free" oder "occupied"}

def update_field_status():
    """
    Liest kontinuierlich den Kafka-Topic "segment_status" aus und aktualisiert
    den lokalen Cache (dictionary) des Feldstatus.
    """
    consumer_status = KafkaConsumer(
        "segment_status",
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='earliest',  # oder 'latest', je nach Verwendung
        group_id=f"status_listener_{SEGMENT_ID}"
    )
    for msg in consumer_status:
        try:
            status_update = json.loads(msg.value.decode("utf-8"))
            seg_id = status_update.get("segment_id")
            status = status_update.get("status")
            if seg_id:
                field_status[seg_id] = status
                # Debug-Ausgabe (optional):
                # print(f"Status update: {seg_id} ist jetzt {status}")
        except Exception as e:
            print("Fehler beim Aktualisieren des Feldstatus:", e)

# Starte den Status-Aktualisierungs-Thread
status_thread = None

# ---------------------------------------------------------------------------
# Funktionen zur Auswahl des richtigen Feldes
# ---------------------------------------------------------------------------
def choose_lane(lanes):
    """
    Wählt die bevorzugte Spur aus der konfigurierten Lane-Liste.
    
    Parameter:
      lanes: Eine Liste von Dictionaries, z. B.:
             [ {"lane": 1, "type": "blocked"},
               {"lane": 2, "type": "normal"},
               {"lane": 3, "type": "normal"} ]
    
    Vorgehen:
      - Filtert alle Lanes heraus, die NICHT als "blocked" markiert sind.
      - Falls die innere Spur (Lane 1) in dieser Liste vorkommt, wird diese gewählt.
      - Andernfalls wird die Lane mit der niedrigsten Nummer aus den verfügbaren gewählt.
      - Falls alle Lanes blockiert sind, wird als Fallback zumindest die innere Spur freigeschaltet.
    
    Rückgabe:
      Ein Tupel (chosen_lane, lane_status), z. B. (1, "normal") oder (2, "normal").
    """
    available_lanes = [lane for lane in lanes if lane["type"] != "blocked"]
    if not available_lanes:
        return lanes[0]["lane"], lanes[0]["type"]
    for lane in available_lanes:
        if lane["lane"] == 1:
            return 1, "normal"
    chosen = min(lane["lane"] for lane in available_lanes)
    for lane in lanes:
        if lane["lane"] == chosen:
            return chosen, lane["type"]
    return chosen, "normal"

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
    else:
        return float('inf')

def select_next_segment(default_next, visible_str, field_status):
    """
    Bestimmt das nächste Segment, an das der Token weitergereicht wird,
    indem alle Kandidaten (default_next und jene aus visible_str) anhand
    der Track-Nummer (niedrigste zuerst) ausgewählt werden und geprüft wird,
    ob sie aktuell frei sind.
    
    Parameter:
      - default_next: Standardziel des Tokens (aus NEXT_SEGMENT)
      - visible_str: Kommaseparierter String mit alternativen Segment-IDs
      - field_status: Lokales Dictionary, das den Status der Felder enthält.
    
    Rückgabe:
      Die ausgewählte Segment-ID, falls ein freies Feld existiert, sonst None.
    """
    candidates = []
    if default_next:
        candidates.append(default_next)
    if visible_str:
        for seg in visible_str.split(","):
            seg = seg.strip()
            if seg:
                candidates.append(seg)
    # Entferne Duplikate
    candidates = list(dict.fromkeys(candidates))
    # Sortiere Kandidaten nach extrahierter Track-Nummer (niedrigste zuerst)
    candidates.sort(key=lambda x: extract_track(x))
    # Prüfe, ob der Kandidat frei ist (wenn nicht im Cache, gehen wir von "free" aus)
    for candidate in candidates:
        if field_status.get(candidate, "free") == "free":
            return candidate
    return None

# ---------------------------------------------------------------------------
# Hilfsfunktion: Publiziere den Status eines Feldes
# ---------------------------------------------------------------------------
def publish_segment_status(status):
    """
    Publiziert den aktuellen Status (z. B. "free" oder "occupied") für dieses Segment
    an das Kafka-Topic "segment_status". Dies ermöglicht anderen Prozessen, den aktuellen Status
    eines Feldes zu ermitteln.
    """
    msg = {
        "segment_id": SEGMENT_ID,
        "status": status,
        "timestamp": time.time()
    }
    producer.send("segment_status", json.dumps(msg).encode('utf-8'), key=SEGMENT_ID.encode('utf-8'))
    producer.flush()

# ---------------------------------------------------------------------------
# Umgebungsvariablen einlesen
# ---------------------------------------------------------------------------
SEGMENT_ID = os.environ.get("SEGMENT_ID", "unknown")
SEGMENT_TYPE = os.environ.get("SEGMENT_TYPE", "normal")  # "start-goal", "normal", "avecaeser"
TRACK_ID = os.environ.get("TRACK_ID", "unknown")
# NEXT_SEGMENT: Standardpfad (aus dem gleichen Track)
NEXT_SEGMENT = os.environ.get("NEXT_SEGMENT")
# VISIBLE_SEGMENTS: Kommaseparierter String mit alternativen, sichtbaren Segmenten, z. B. "segment-3-2, segment-2-2"
VISIBLE_SEGMENTS = os.environ.get("VISIBLE_SEGMENTS")
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")

# Optionale LANES-Konfiguration als JSON-String, z. B.:
# '[{"lane":1, "type": "blocked"}, {"lane":2, "type": "normal"}, {"lane":3, "type": "normal"}]'
LANES_JSON = os.environ.get("LANES")
lanes_config = None
if LANES_JSON:
    try:
        lanes_config = json.loads(LANES_JSON)
        print(f"Lanes-Konfiguration für Segment {SEGMENT_ID}: {lanes_config}")
    except Exception as e:
        print(f"Fehler beim Parsen der LANES-Umgebungsvariable: {e}")

# ---------------------------------------------------------------------------
# Kafka-Topic erstellen und Producer/Consumer initialisieren
# ---------------------------------------------------------------------------
create_topic_if_not_exists(SEGMENT_ID, num_partitions=6, replication_factor=3, kafka_broker=KAFKA_BROKER)
producer = KafkaProducer(bootstrap_servers=[KAFKA_BROKER])
consumer = KafkaConsumer(
    SEGMENT_ID,
    bootstrap_servers=[KAFKA_BROKER],
    auto_offset_reset='earliest',
    group_id=SEGMENT_ID
)

print(f"Segment {SEGMENT_ID} ({SEGMENT_TYPE}) von Track {TRACK_ID} gestartet, lauscht auf Topic '{SEGMENT_ID}'.")

# Starte den Status-Listener-Thread
status_thread = threading.Thread(target=update_field_status, daemon=True)
status_thread.start()

# Publiziere anfangs den Status "free"
publish_segment_status("free")

# ---------------------------------------------------------------------------
# Hauptschleife: Verarbeitung hereinkommender Token
# ---------------------------------------------------------------------------
for message in consumer:
    try:
        token = json.loads(message.value.decode('utf-8'))
    except Exception as e:
        print(f"Fehler beim Dekodieren des Tokens: {e}")
        continue

    print(f"\nSegment {SEGMENT_ID} hat Token erhalten: {token}")
    # Setze den Status dieses Segments als besetzt
    publish_segment_status("occupied")
    
    # Simuliere Bearbeitungszeit: zufällige Pause zwischen 2 und 3 Sekunden
    processing_delay = random.uniform(2, 3)
    print(f"Verarbeite Token für {processing_delay:.2f} Sekunden...")
    time.sleep(processing_delay)
    
    # Sonderlogik für Avecaeser-Segmente (zusätzliches Winken, falls benötigt)
    if SEGMENT_TYPE == "avecaeser":
        if token.get("rounds", 0) < 2 and not token.get("visited_avecaeser", False):
            token["visited_avecaeser"] = True
            print("Token betritt ein Avecaeser-Feld: Zusätzliche 3 Sekunden zum Winken.")
            time.sleep(3)
    
    # Sonderlogik für Start-/Ziel-Segmente: Runde erhöhen und ggf. Rennen beenden
    if SEGMENT_TYPE == "start-goal":
        token["rounds"] = token.get("rounds", 0) + 1
        print(f"Token-Runden erhöht: {token['rounds']}")
        if token["rounds"] >= 3:
            token["finish_time"] = time.time()
            finish_topic = "times"
            producer.send(finish_topic, json.dumps(token).encode('utf-8'))
            producer.flush()
            print(f"Token abgeschlossen. Zeitpublikation an Topic '{finish_topic}'.")
            publish_segment_status("free")
            continue

    # -----------------------------------------------------------------------
    # Sichtbarkeits- & Trackwechsellogik:
    # Es werden zwei Quellen betrachtet:
    #   - NEXT_SEGMENT: Standardziel im gleichen Track.
    #   - VISIBLE_SEGMENTS: Alternative Segmente aus benachbarten Tracks.
    # Mithilfe des lokal gepflegten field_status prüfen wir, welches Feld aktuell frei ist.
    # Der Reiter wählt immer das Feld mit dem niedrigsten Track (also der geringsten Track-Nummer),
    # sofern frei; wenn alle Kandidaten besetzt sind, wartet er.
    # -----------------------------------------------------------------------
    if NEXT_SEGMENT or VISIBLE_SEGMENTS:
        selected_candidate = None
        while selected_candidate is None:
            selected_candidate = select_next_segment(NEXT_SEGMENT, VISIBLE_SEGMENTS, field_status)
            if selected_candidate is None:
                print(f"Alle Kandidaten sind besetzt. Reiter wartet...")
                time.sleep(1)
        print(f"Segment {SEGMENT_ID} leitet Token an '{selected_candidate}' weiter.")
        producer.send(selected_candidate, json.dumps(token).encode('utf-8'))
        producer.flush()
    else:
        print(f"Segment {SEGMENT_ID} hat weder NEXT_SEGMENT noch VISIBLE_SEGMENTS definiert. Token-Verarbeitung endet hier.")
    
    # Nach Abschluss: Setze den Status dieses Segments auf "free"
    publish_segment_status("free")
