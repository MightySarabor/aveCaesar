import os
import time
import json
from kafka import KafkaConsumer, KafkaProducer

# Umgebungsvariablen einlesen
SEGMENT_ID = os.environ.get("SEGMENT_ID", "unknown")
SEGMENT_TYPE = os.environ.get("SEGMENT_TYPE", "normal")  # "start-goal" oder "normal"
TRACK_ID = os.environ.get("TRACK_ID", "unknown")
NEXT_SEGMENT = os.environ.get("NEXT_SEGMENT")  # Erwartet die Segment-ID des nächsten Feldes
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka-1:19092")

# Kafka-Producer und Consumer initialisieren
producer = KafkaProducer(bootstrap_servers=[KAFKA_BROKER])
consumer = KafkaConsumer(
    SEGMENT_ID,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='earliest',
    group_id=SEGMENT_ID
)

print(f"Segment {SEGMENT_ID} ({SEGMENT_TYPE}) von Track {TRACK_ID} gestartet, lauscht auf Topic '{SEGMENT_ID}'.")

for message in consumer:
    token = json.loads(message.value.decode('utf-8'))
    print(f"Segment {SEGMENT_ID} hat Token erhalten: {token}")
    
    # Simuliere kurze Bearbeitungszeit
    time.sleep(1)
    
    # Wenn ein NEXT_SEGMENT definiert ist, leite das Token weiter
    if NEXT_SEGMENT:
        # Falls das Token noch keinen Rundenzähler hat, initialisieren
        if 'rounds' not in token:
            token['rounds'] = 0

        # Bei einem start-goal Segment: Runde erhöhen
        if SEGMENT_TYPE == "start-goal":
            token['rounds'] += 1
            print(f"Token-Runden: {token['rounds']}")
            # Nach 3 Runden wird das Token abgeschlossen: Zeitstempel erfassen und an Zeittopic senden
            if token['rounds'] >= 3:
                token['finish_time'] = time.time()
                finish_topic = "times"
                producer.send(finish_topic, json.dumps(token).encode('utf-8'))
                producer.flush()
                print(f"Token fertig, Zeitpublikation an Topic '{finish_topic}'.")
                continue  # Token wird hier nicht weitergeleitet

        print(f"Segment {SEGMENT_ID} leitet Token an {NEXT_SEGMENT} weiter.")
        producer.send(NEXT_SEGMENT, json.dumps(token).encode('utf-8'))
        producer.flush()
    else:
        print(f"Segment {SEGMENT_ID} hat kein NEXT_SEGMENT. Token-Verarbeitung endet hier.")
