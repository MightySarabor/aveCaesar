from confluent_kafka import Producer
import sys

# Konfiguration des Kafka-Producers - beachte die externe Adresse
conf = {
    'bootstrap.servers': 'localhost:9092',  # Externe Verbindung: Host-IP (hier localhost)
}

producer = Producer(conf)

def delivery_report(err, msg):
    """Callback, das den Erfolg bzw. Fehler der Nachrichtenauslieferung meldet."""
    if err is not None:
        sys.stderr.write(f"Fehler beim Senden an {msg.topic()}: {err}\n")
    else:
        print(f"Nachricht erfolgreich an {msg.topic()} in Partition {msg.partition()} gesendet.")

# Ziel-Topic und Message definieren
topic = 'segment-1-1'
message = 'Hello, World!'

try:
    # Nachricht produzieren; beim Callback wird der Status gemeldet.
    producer.produce(topic, value=message, callback=delivery_report)
    # Warten, bis alle Nachrichten ausgeliefert wurden.
    producer.flush()
except Exception as e:
    print(f"Fehler beim Produzieren der Nachricht: {e}")
