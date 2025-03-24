import os
import time
import json
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

# Funktion zum Erstellen eines Kafka-Topics, falls es noch nicht existiert
def create_topic_if_not_exists(topic_name, num_partitions=6, replication_factor=3, kafka_broker='localhost:9092'):
    """
    Erstellt ein Kafka-Topic mit den angegebenen Parametern, falls es noch nicht existiert.
    """
    admin_client = KafkaAdminClient(bootstrap_servers=kafka_broker, client_id='topic_creator')

    topic_list = []
    topic = NewTopic(
        name=topic_name,
        num_partitions=num_partitions,
        replication_factor=replication_factor
    )
    topic_list.append(topic)

    try:
        admin_client.create_topics(new_topics=topic_list, validate_only=False)
        print(f"Topic '{topic_name}' wurde erstellt mit {num_partitions} Partitionen und Replikationsfaktor {replication_factor}.")
    except TopicAlreadyExistsError:
        print(f"Topic '{topic_name}' existiert bereits.")
    except Exception as e:
        print(f"Fehler beim Erstellen des Topics: {e}")
    finally:
        admin_client.close()

# Umgebungsvariablen einlesen
SEGMENT_ID = os.environ.get("SEGMENT_ID", "unknown")
SEGMENT_TYPE = os.environ.get("SEGMENT_TYPE", "normal")  # "start-goal" oder "normal"
TRACK_ID = os.environ.get("TRACK_ID", "unknown")
NEXT_SEGMENT = os.environ.get("NEXT_SEGMENT")  # Erwartet die Segment-ID des nächsten Feldes
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")

# Sicherstellen, dass das Topic existiert
create_topic_if_not_exists(SEGMENT_ID, num_partitions=6, replication_factor=3, kafka_broker=KAFKA_BROKER)

# Kafka-Producer und Consumer initialisieren
producer = KafkaProducer(bootstrap_servers=[KAFKA_BROKER])
consumer = KafkaConsumer(
    SEGMENT_ID,
    bootstrap_servers=[KAFKA_BROKER],
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
