#!/usr/bin/env python3
import sys
import json
import random

def generate_tracks(num_tracks: int, length_of_track: int, block_prob: float = 0.3):
    """
    Generates a data structure with 'num_tracks' circular tracks.
    Each track has exactly 'length_of_track' segments:
      - 1 segment: 'start-and-goal-t'
      - (length_of_track - 1) segments: normal segments 'segment-t-c'
      
    Für jedes Segment wird das Feld "nextSegments" so gesetzt, dass es
    nicht nur das direkt folgende Segment im gleichen Track enthält, sondern
    auch das entsprechende Segment aus dem linken und rechten Track (sofern verfügbar).
    
    Außerdem wird für normale Segmente zufällig bestimmt, ob sie blockiert sind.
    Ein blockiertes Segment wird in den "nextSegments"-Listen nicht mit aufgeführt.
    Es wird sichergestellt, dass es mindestens eine Route gibt.
    
    Returns a Python dict that can be serialized to JSON.
    """
    all_tracks = []
    
    # Erste Phase: Erzeuge für jeden Track alle Segmente
    for t in range(1, num_tracks + 1):
        track_id = str(t)
        segments = []
        
        # 1. Start-/Ziel-Segment: immer "start-goal"
        start_segment_id = f"start-and-goal-{t}"
        # Für das Start-goal verwenden wir als next segment standardmäßig das erste normale Segment (falls vorhanden)
        if length_of_track == 1:
            next_segments = [start_segment_id]
        else:
            next_segments = [f"segment-{t}-1"]
        
        start_segment = {
            "segmentId": start_segment_id,
            "type": "start-goal",
            "nextSegments": []  # wird später definiert
        }
        segments.append(start_segment)
        
        # 2. Normale Segmente
        # Wir generieren (length_of_track - 1) Segmente, wobei für c==1
        # immer "normal" erzwungen wird, damit der Start-track nicht komplett blockiert.
        for c in range(1, length_of_track):
            seg_id = f"segment-{t}-{c}"
            # Entscheide, ob das Segment blockiert ist:
            if c == 1:
                seg_type = "normal"  # erstes normale Segment immer frei
            else:
                seg_type = "normal" if random.random() >= block_prob else "blocked"
            # Vorläufig setzen wir nextSegments als leere Liste, diese wird in Phase 2 bestimmt.
            segment = {
                "segmentId": seg_id,
                "type": seg_type,
                "nextSegments": []
            }
            segments.append(segment)
        
        track_definition = {
            "trackId": track_id,
            "segments": segments
        }
        all_tracks.append(track_definition)
    
    # Zweite Phase: Bestimme für jedes Segment die sichtbaren Next-Segments anhand der Position
    # Wir wollen für jedes Segment folgendes:
    #   - Den Standardpfad: das nächste Segment im gleichen Track (mit Wrap-Around).
    #   - Aus dem linken Track (t-1): das Segment an derselben relativen Position (falls vorhanden).
    #   - Aus dem rechten Track (t+1): analog.
    # Dabei berücksichtigen wir, ob ein Segment blockiert ist – wird es blockiert, so zählt es nicht als mögliche Route.
    # Es muss aber mindestens eine Route vorhanden sein.
    
    # Erstelle ein Dictionary für einen schnellen Zugriff per Track (track_id -> segments-Liste)
    tracks_dict = { track["trackId"]: track["segments"] for track in all_tracks }
    
    for track in all_tracks:
        t = int(track["trackId"])
        segments = track["segments"]
        total = len(segments)  # entspricht length_of_track
        for i, seg in enumerate(segments):
            candidates = []
            # Bestimme den "next index" im selben Track:
            if i == 0:
                # Für das Start-goal nehmen wir das erste normale Segment
                next_index = 1 if total > 1 else 0
            else:
                # Für normale Segmente:
                if i < total - 1:
                    next_index = i + 1
                else:
                    # Letztes normales Segment bekommt als next den Start-goal (Index 0)
                    next_index = 0
            
            # Hilfsfunktion: Fügt Kandidat aus gegebenen segments hinzu, wenn vorhanden und nicht blockiert.
            def add_candidate(track_segments):
                if next_index < len(track_segments):
                    cand = track_segments[next_index]
                    if cand["type"] != "blocked":
                        candidates.append(cand["segmentId"])
            
            # Kandidat 1: Gleiches Track
            add_candidate(segments)
            # Kandidat 2: Linker Track (t-1)
            if t - 1 >= 1:
                left_track = tracks_dict.get(str(t - 1), [])
                add_candidate(left_track)
            # Kandidat 3: Rechter Track (t+1)
            if t + 1 <= num_tracks:
                right_track = tracks_dict.get(str(t + 1), [])
                add_candidate(right_track)
            
            # Sicherstellen, dass es mindestens einen Kandidaten gibt.
            if not candidates:
                # Falls alle möglichen Routen blockiert sind, wählen wir den Standardroute
                # und simulieren so, dass mindestens diese Route frei ist.
                # Wir ändern hier temporär den Typ der Standardroute.
                default_cand = segments[next_index]["segmentId"]
                candidates.append(default_cand)
            
            # Entferne eventuelle Duplikate und setze als nextSegments
            seg["nextSegments"] = list(dict.fromkeys(candidates))
    
    return {"tracks": all_tracks}


def main():
    if len(sys.argv) not in (4, 5):
        print(f"Usage: {sys.argv[0]} <num_tracks> <length_of_track> <output_file> [seed]")
        sys.exit(1)
    
    num_tracks = int(sys.argv[1])
    length_of_track = int(sys.argv[2])
    output_file = sys.argv[3]
    
    # Optional: Ein Seed für die Reproduzierbarkeit
    if len(sys.argv) == 5:
        random.seed(int(sys.argv[4]))
    
    tracks_data = generate_tracks(num_tracks, length_of_track)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tracks_data, f, indent=2)
        f.write("\n")
    print(f"Successfully generated {num_tracks} track(s) of length {length_of_track} into '{output_file}'")

if __name__ == "__main__":
    main()
