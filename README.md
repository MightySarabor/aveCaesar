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

4. **Race Controller:**  
   - **`controller.py`**: Startet das Rennen, indem der Nutzer einen Track auswählt und einen Token (z. B. den Namen eines Pferdes) initialisiert. Der Token wird in das Kafka-Topic des Startsegments eingespeist und wandert so durch das Spielbrett.

---

## Setup und Ausführung

### Voraussetzungen

- **Docker & Docker Compose:** Für den Containerbetrieb und die Orchestrierung.
- **Python 3.9+**: Zum Ausführen der Skripte.

### Schritte

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

## Zusammenfassung

AveCaesar kombiniert Docker und Kafka, um ein dynamisch generiertes, verteiltes Spielbrett zu erstellen. Jeder Container repräsentiert ein Spielfeldsegment, das als Event-Handler agiert und Nachrichten (Token) entlang festgelegter Pfade weiterleitet. Der Controller ermöglicht es Nutzern, Rennen zu starten, wodurch ein spannendes, interaktives System entsteht, das als Grundlage für weitere Erweiterungen dient.


