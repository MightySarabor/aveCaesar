import json

def create_box(segment, width=8):
    """
    Erzeugt eine kompakte ASCII-Rechteck-Darstellung für ein Segment.
    - Bei blockierten Segmenten wird der Innenraum komplett mit "S" gefüllt.
    - Alle anderen (guten) Segmente zeigen einen leeren Innenraum.
    """
    seg_type = segment.get("type", "normal")
    top = "+" + "-" * (width - 2) + "+"
    bottom = top

    if seg_type == "blocked":
        mid = "|" + "S" * (width - 2) + "|"
    else:
        mid = "|" + " " * (width - 2) + "|"

    return [top, mid, bottom]

def create_arrow(allowed, width=5):
    """
    Erzeugt eine kompakte ASCII-Darstellung eines Übergangs-Pfeils (3 Zeilen).
    - Bei erlaubtem Übergang wird "->" angezeigt.
    - Andernfalls "-X->".
    """
    if allowed:
        arrow_text = "->"
    else:
        arrow_text = "-X->"
    top = " " * width
    mid = arrow_text.center(width)
    bot = " " * width
    return [top, mid, bot]

def draw_track_ascii(track):
    segments = track.get("segments", [])
    if not segments:
        print(f"Track {track.get('trackId', '?')} enthält keine Segmente!")
        return

    # Erzeuge die Boxen für alle Segmente.
    boxes = [create_box(seg) for seg in segments]

    # Erzeuge die Pfeile zwischen den Segmenten anhand des Übergangsstatus.
    arrows = []
    for i in range(len(segments) - 1):
        current_seg = segments[i]
        next_seg = segments[i+1]
        allowed = next_seg.get("segmentId") in current_seg.get("nextSegments", [])
        arrows.append(create_arrow(allowed))

    # Fasse die Boxen und Pfeile zeilenweise zusammen.
    composite_lines = ["", "", ""]
    for i in range(len(boxes)):
        box = boxes[i]
        for j in range(3):
            composite_lines[j] += box[j]
        if i < len(boxes) - 1:
            arrow = arrows[i]
            for j in range(3):
                composite_lines[j] += arrow[j]

    print("Rennstrecke (Track " + track.get("trackId", "?") + "):")
    for line in composite_lines:
        print(line)

    # Überprüfe den Übergang vom letzten Segment zurück zum ersten (Rundschluss).
    last_seg = segments[-1]
    first_seg = segments[0]
    allowed = first_seg.get("segmentId") in last_seg.get("nextSegments", [])
    arrow_symbol = "->" if allowed else "-X->"
    print(f"Circular connection: {last_seg.get('segmentId')} {arrow_symbol} {first_seg.get('segmentId')}")
    print()

def main():
    try:
        with open("track.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("Fehler beim Laden der track.json:", e)
        return

    tracks = data.get("tracks", [])
    if not tracks:
        print("Keine Tracks gefunden!")
        return

    for track in tracks:
        draw_track_ascii(track)

if __name__ == "__main__":
    main()
