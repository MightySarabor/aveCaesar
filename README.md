# AveCaesar

AveCaesar ist ein dynamisches System, das ein spielbrettartiges Rennevent mithilfe von Docker-Containern und Kafka realisiert. Jedes Spielfeld entspricht dabei einem Segment – einem eigenständigen Container, der als Event-Handler agiert. Sobald ein Reiter (Token) ein Segment betritt, wird dies als Event in Kafka publiziert. Das Segment empfängt das Event, verarbeitet es und leitet den Reiter an das nächste Segment weiter.

---

## Grundidee

- **Dynamische Spielbrett-Erzeugung:**  
  Mithilfe des Skripts `circular_course.py` wird eine JSON-Datei (`track.json`) generiert, welche die Struktur des Spielbretts definiert. Jeder Track besteht aus mehreren Segmenten – dem Start-/Zielsegment und den folgenden normalen Segmenten, die in einer Schleife verbunden sind.

- **Containerisierte Segmente:**  
  Jedes Segment wird als Docker-Container ausgeführt. Der Container enthält den Code (`segment.py`), der:
  - Sein eigenes Kafka-Topic abonniert (das Topic trägt den gleichen Namen wie das Segment).
  - Eingehende Events verarbeitet (z. B. das Betreten des Segments durch ein Pferd).
  - Das Reiter-Token an das nächste Segment weiterleitet oder, bei speziellen Segmenten wie „start-goal“, zusätzliche Logik ausführt (z. B. Zählen der Runden).

- **Verteilte Event-Verarbeitung mit Kafka:**  
  Kafka dient als zentrales Nachrichtensystem. Die Segmente kommunizieren über Kafka:
  - Ein Token wird vom Controller in das Kafka-Topic des Startsegments gesendet.
  - Jedes Segment bekommt das Token und leitet es an das nächste Segment weiter, wodurch das Rennen vorangetrieben wird.
  - Nach definierten Runden wird das Rennen abgeschlossen und die Ergebnisse (zum Beispiel die Renndauer) über ein spezielles Kafka-Topic publiziert.

---

## Architekturübersicht

1. **Track-Generierung:**  
   - **`circular_course.py`**: Erzeugt die `track.json`, die jedes Segment eines Tracks definiert.
  
2. **Container Deployment:**  
   - **`generate-compose.py`**: Liest die `track.json` und generiert daraus dynamisch ein `docker-compose.generated.yml`. Jeder Service in dieser Datei repräsentiert ein Segment des Tracks, konfiguriert mit den entsprechenden Umgebungsvariablen.
   - **`Dockerfile`**: Baut das Container-Image, das den Segment-Code (`segment.py`) enthält. Dieses Image wird für alle Segment-Container verwendet.

3. **Event-Handling mit Kafka:**  
   - Alle Segment-Container kommunizieren über Kafka. Jeder Container abonniert ein Topic, das seiner Segment-ID entspricht.
   - Die Infrastruktur wird mittels Docker Compose gestartet, wobei zusätzlich Kafka und Zookeeper als zentrale Services laufen.
   - Hier war der kniffligste Teil die Ports richtig zu setzen. Es muss unterschieden werden zwischen Host Mascheine zu Container und Container zu Container (im gleichen Netzwerk) bei mir mit Inside und Outside gekennzeichnet. Um mit der Hostmaschine auf Kafka zuzugreifen ist Portforwarding wichtig.
```bash
services:
  zookeeper:
    image: wurstmeister/zookeeper
    container_name: zookeeper
    ports:
      - "2181:2181"

  kafka:
    image: wurstmeister/kafka
    container_name: kafka
    ports:
      - "9093:9093"
    environment:
      KAFKA_LISTENERS: INSIDE://0.0.0.0:9092,OUTSIDE://0.0.0.0:9093
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: INSIDE://kafka:9092,OUTSIDE://localhost:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: INSIDE:PLAINTEXT,OUTSIDE:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: INSIDE
      KAFKA_BROKER_ID: 1
    depends_on:
      - zookeeper
```

4. **Race Controller:**  
   - **`controller.py`**: Startet das Rennen, indem der Nutzer einen Track auswählt und einen Token (z. B. den Namen eines Pferdes) initialisiert. Der Token wird in das Kafka-Topic des Startsegments eingespeist und wandert so durch das Spielbrett.

---

## Setup und Ausführung

### Schritte

0. **Docker-Image bauen (wichtig!):**  
   **Achtung:** Falls Änderungen an `segment.py` vorgenommen wurden, ist es notwendig, das Docker-Image neu zu bauen. Andernfalls werden alte Versionen des Codes genutzt – wie ich selbst schmerzlich erfahren habe.  
   
   ```bash
   docker build -t segment-image .
   ```
   
1. **Track generieren:**  
   Erstelle mit `circular_course.py` die JSON-Beschreibung des Spielbretts.  
   Beispiel:
   
   ```bash
   python circular_course.py <num_tracks> <length_of_track> <output_file>
   ```
   
   Dadurch entsteht die Datei `track.json`.

2. **Docker Compose Datei generieren:**  
   Mit `generate-compose.py` wird basierend auf der `track.json` ein Docker Compose File erstellt:
   
   ```bash
   python generate-compose.py
   ```
   
   Dadurch entsteht die Datei `docker-compose.generated.yml`, die alle Segment-Services definiert.

3. **Container starten:**  
   Starte die gesamte Infrastruktur inklusive Kafka und Zookeeper:
   
   ```bash
   docker-compose -f docker-compose.generated.yml up -d
   docker-compose up -d kafka zookeeper
   ```
   
   Dadurch werden die Segment-Container sowie Kafka/Zookeeper im Hintergrund ausgeführt.

4. **Rennen starten:**  
   Nutze den Controller, um das Rennen zu initiieren:
   
   ```bash
   python controller.py
   ```
   
   Folge der Anweisung, wähle einen Track und starte deinen Reiter.

---

# Aufgabe 2: Erweiterung zum Kafka-Cluster

Um den einzelnen Kafka-Broker in einen Cluster zu verwandeln, wurden der Docker Compose-Konfiguration zwei weitere Broker hinzugefügt. Der ursprüngliche Broker bleibt unverändert, um den bestehenden Code nicht anzupassen. Die zusätzlichen Broker (kafka-broker-2 und kafka-broker-3) sind analog zum ersten konfiguriert – mit jeweils eigener Broker-ID, separaten Ports und individuellen Listener-Einstellungen. Dadurch entsteht ein einfacher Kafka-Cluster, der über Zookeeper koordiniert wird und für höhere Verfügbarkeit sowie bessere Lastverteilung sorgt.

Folgender Code kann als weiterer Service hinzugefügt werden in der docker-compose.yml. Es muss ID, die Ports und der Name des Containers geändert werden. 

```
  kafka-broker-2:
    image: wurstmeister/kafka
    container_name: kafka-broker-2
    ports:
      - "9094:9094"
    environment:
      KAFKA_LISTENERS: INSIDE://0.0.0.0:19092,OUTSIDE://0.0.0.0:9094
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: INSIDE://kafka-broker-2:19092,OUTSIDE://localhost:9094
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: INSIDE:PLAINTEXT,OUTSIDE:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: INSIDE
      KAFKA_BROKER_ID: 2
    depends_on:
      - zookeeper
```
# AveCaesar – Aufgabe 3: Schikanen & Hindernisse

**Überblick:**  
AveCaesar realisiert ein spielbrettartiges Rennevent mit Docker-Containern, wobei jedes Spielfeld (Segment) einen eigenen Event-Handler darstellt. Die Kommunikation zwischen den Segmenten und dem zentralen Controller erfolgt über Kafka.

**Neue Logik – Hindernisse und Schikanen:**  
- **Hindernisse:**  
  Wenn ein Reiter (Token) in einem Segment ankommt, prüft der Container, ob das Zielsegment (z. B. NEXT_SEGMENT oder ein alternatives, sichtbar definiertes Segment) frei ist.  
  - Ist das Ziel bereits belegt (Engpass voll), wird der Status des aktuellen Segments auf **GGGwaitingGGG** gesetzt.  
  - Das Token „schindet“ sich im aktuellen Segment ab, bis der Engpass gelöst ist und ein Ziel wieder frei ist.

- **Versuch, nach innen zu reiten:**  
  Die Reiter versuchen auch, in den inneren Teil des Kurses zu wechseln, was aktuell aber noch keinen echten Vorteil bietet.  
  - Dieser Versuch wird klar als Regel implementiert, wobei der Container – sollte der innere Bereich bereits belegt sein – das Token ebenfalls warten lässt.

- **Weiterleitung und Statusänderungen:**  
  - Erreicht ein Token ein freies Zielsegment, wird es dorthin weitergeleitet und der Status des abgebenden Segments wechselt von **GGGwaitingGGG** bzw. **GGGoccupiedGGG** zu **GGGfreeGGG**.  
  - Alle Statusänderungen (occupied, waiting, free) werden zentral im Kafka-Topic veröffentlicht, sodass der Controller jederzeit den aktuellen Zustand verfolgen kann.

**Controller:**  
Der Controller abonniert alle Kafka-Topics und gibt alle 2 Sekunden eine kompakte Statuszeile aus – er meldet:
- **Spurwechsel:** Sobald ein Token seinen Track wechselt, wird dies kurz angezeigt.
- **Warten:** Wenn ein Segment meldet, dass ein Token aufgrund eines Engpasses warten muss, wird diese Nachricht als Hinweis ausgegeben.

Diese vereinfachte Logik sorgt dafür, dass du während des Rennens stets einen schnellen Überblick darüber hast, ob Reiter blockiert sind oder ihren Kurs (Spur) ändern – und wie sich das Rennen dynamisch entwickelt.





