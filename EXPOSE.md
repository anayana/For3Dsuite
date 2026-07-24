# Exposé — Wissenschaftlicher Beitrag und Anwendung

*Der prüfbare, prognosefähige und begehbare Bestandeszwilling: Fusion von
terrestrischem LiDAR, RGB-Bildanalyse und Waldwachstumsmodell zu einer offenen,
georeferenzierten Plattform mit sauberer Herkunftstrennung.*

---

## 1. Ausgangslage und Forschungslücke

Terrestrische Fernerkundung (TLS, 360°-RGB) und einzelbaumbasierte Wachstumsmodelle
existieren als getrennte Werkzeugketten. LiDAR beschreibt die **Struktur** eines
Bestandes quantitativ (Position, BHD, Höhe, Kronen), RGB trägt die davon unabhängige
**qualitative** Information (Vitalität, Verfärbung, Schäden, Artmerkmale), und
Wuchsmodelle wie BWINPro/TreeGrOSS prognostizieren die **Entwicklung** — doch die drei
Ebenen werden selten am selben, georeferenzierten Objekt zusammengeführt und, vor allem,
selten wechselseitig abgesichert.

Die Lücke ist damit nicht ein weiteres Messverfahren, sondern die **integrierte,
prüfbare Verkettung**: aus einem einzelnen Aufnahme-Setup einen Bestandeszwilling zu
erzeugen, der Messung, qualitativen Zustand und Prognose vereint, jede Aussage mit ihrer
Herkunft ausweist und für Fachpublikum wie Laien **begehbar** wird.

## 2. Wissenschaftlicher Beitrag

**(a) Durchgängige, offene Verarbeitungskette (Layer 1–5).** Von den Rohaufnahmen
(Fisheye-Stitching bzw. E57-Reprojektion) über die geometrische Einzelbaum-Inventur aus
der Punktwolke, die qualitative RGB-Auswertung je segmentiertem Baum, bis zur
Wachstumsprognose über einen legal hostbaren, quelloffenen Modellkern (TreeGrOSS, GPLv3).
Alle Schritte sind reproduzierbar, abhängigkeitsarm und selbst hostbar.

**(b) Der Validierungshebel — der methodische Kern.** Qualitative (RGB) und quantitative
(LiDAR/QSM) Merkmale werden am **selben Objekt kreuzvalidiert**: Eine bildseitig gemeldete
Kronenverlichtung muss sich in geringerer QSM-Astdichte und Punktdichte der Oberkrone
spiegeln. Übereinstimmung ist ein starkes Signal, Widerspruch entlarvt Fehler und
Modell-Halluzinationen. Zusätzlich werden abgeleitete Kennwerte gegen Referenz-Ground-Truth
geprüft (Recall/Precision/Lagefehler der Einzelbaum-Detektion). Diese wechselseitige
Absicherung macht die Bestandesbeschreibung erst belastbar.

**(c) Provenienz-Trennung als Datenmodell.** Jeder Wert trägt seine Ebene: *direkt
beobachtet* (qualitativ aus dem Bild), *algorithmisch abgeleitet* (Bildanalyse),
*kartenbasiert angereichert* (per Koordinate aus freien Geodaten, mit Quelle und
Genauigkeit) und *gemessene Inventur* (LiDAR/Feld). Diese Trennung macht transparent,
worauf eine Aussage beruht, und ist die Voraussetzung für FAIRe, zitierbare Daten.

**(d) Prognose- und Kommunikationsschicht.** Der gemessene Bestand wird über TreeGrOSS in
Zukunftsbestände überführt und zurück in den Viewer gespielt; die immersive Darstellung
(360°-Panorama, begehbares 3D Gaussian Splatting) macht heutigen wie prognostizierten
Bestand erfahrbar. Aus einer Messung wird ein Vorhersage- und Vermittlungswerkzeug.

**(e) Fernerkundungs-informierte, zustandsgetriebene Behandlungssteuerung.** TreeGrOSS
enthält bereits Behandlungsregeln (Z-Baum-Auswahl, Durchforstung, Zielstärkennutzung,
Habitat-/Totholz-Kennzeichnung). Der Beitrag ist die **Kopplung**: statt der üblichen
Feldeinschätzung fließt eine **objektive, fernerkundete Zustands- und Qualitätsgröße je
Baum** (aus (b)/(c)) in die Auswahl- und Entnahmeregeln. Das Modell bevorzugt vitale,
gut geformte Z-Bäume und terminiert den Abbau geschädigter Bäume risiko- und wertbasiert;
zu weit geschädigte, aber habitatwertvolle Bäume werden als Habitat-/Totholzbäume belassen.
Aus „Zustand von heute" wird so ein zeitlich aufgelöster, begründeter Behandlungsplan
(Auszeichnung heute, Entnahme in *x* Jahren oder Verbleib). Eine mögliche Sensor-Erweiterung
— co-lokalisierte Multispektral-Panoramen (Red-Edge/NIR) am selben Standort, per
Rückprojektion über die TLS-Wolke fusioniert — hebt die Vitalitätsdiagnose vom sichtbaren
Greenness-Proxy auf echte Vegetationsindizes (NDVI/NDRE).

## 3. Forschungsfragen

1. **Genauigkeit:** Wie belastbar sind TLS-abgeleitete Einzelbaumkennwerte (BHD, Höhe,
   Position) gegenüber Feldmessung, und welche systematischen Fehler (Verdeckung,
   Rindenrauigkeit, Zylinderfit-Bias, Hanglage, Teilbogen-Sicht) sind zu kalibrieren?
2. **Struktur ↔ Zustand:** Lässt sich Vitalität/Stress aus RGB robust bestimmen, wenn sie
   gegen die LiDAR-Struktur desselben Baumes kreuzvalidiert wird? Wie stark verbessert
   Multi-View-Aggregation die Klassifikationsgüte?
3. **Prognose:** Wie wirken sich die spezifischen Fehlerstrukturen der TLS-Eingangsdaten
   auf einzelbaumbasierte Wuchsprognosen aus, und wie verändert die (aus RGB bestimmte)
   Baumart das Ergebnis gegenüber pauschalen Annahmen?
4. **Übergangszonen:** Wie lassen sich ökologisch bedeutsame Randstrukturen (Waldränder,
   Hecken, Totholz, Kronenschluss/vertikale Schichtung) quantifizieren, und übertragen
   sich Waldinventur-Methoden ungeprüft auf sie (Befund: nicht ohne Weiteres)?
5. **Monitoring:** Was leisten Wiederholungsaufnahmen für die Detektion von Zuwachs,
   Mortalität und Störungen?
6. **Behandlungssteuerung:** Wie lässt sich eine fernerkundete Zustandsgröße objektiv in
   die Z-Baum-Auswahl und Entnahmeplanung eines Einzelbaum-Wuchsmodells einkoppeln, und
   wie gut deckt sich die automatische, zustandsgetriebene Auszeichnung mit der
   Experten-Auszeichnung? Ab wann ist ein geschädigter Baum zu entnehmen (Wert-/Risiko-
   Trajektorie) und ab wann als Habitatbaum zu belassen (Mehrziel-Abwägung)?

## 4. Anwendungsbereiche

- **Forstinventur und Kohlenstoffbilanzierung** — non-destruktive Vorrats-, Biomasse- und
  C-Schätzung; MRV für Kohlenstoffmärkte; Ergänzung von ICOS-/Flux-Standorten.
- **Waldgesundheits-Monitoring** — Früherkennung von Dürre-/Klimastress durch
  bild-/strukturbasierte Vitalitätsdiagnose.
- **Waldbauliche Entscheidungsunterstützung** — Durchforstungs- und Behandlungsszenarien
  vor dem Eingriff durchspielen und den Zukunftsbestand begehen.
- **Naturschutz und Agroforst** — Habitatstrukturen, Totholz, Hecken und Landschafts-
  elemente erfassen; Waldrand-Ökotone als Randeffekt-Gradient.
- **Präzisionsforstwirtschaft** — operative Planung und Ernte auf Einzelbaumebene.
- **Lehre und Wissenschaftskommunikation** — begehbare digitale Zwillinge für virtuelle
  Exkursionen, Stakeholder-Beteiligung und partizipative Planung.
- **Offene Dateninfrastruktur** — das Provenienz-Schema und der Self-Hosting-Stack als
  zitierbare, FAIRe Plattform (Ziel: Software-/Methoden-Paper).

## 5. Abgrenzung und ehrliche Grenzen

- **Einzelscan-Verdeckung** und die von der Feldmessung abweichende Fehlerstruktur des
  TLS-BHD erfordern Kalibrierung gegen Referenzinventur — ein eigener, publikationswürdiger
  Schritt, kein Formatierungsproblem.
- **Artansprache aus Weitwinkel-Panoramen** bleibt grob; verlässlich sind Textur/Habitus
  und kartenbasierte Ableitung, nicht Organ-Nahaufnahmen.
- **3D Gaussian Splatting** ist bild-basiert und maßstabsfrei: hervorragend zur
  fotorealistischen Begehung, aber **keine Messgrundlage**. Metrik kommt aus dem
  LiDAR-Zweig; beides lässt sich im gemeinsamen Koordinatenrahmen koppeln (Messung +
  Begehung in einer Szene). Belastbares Splatting braucht dichte Mehransichts-Aufnahme.
- **Bonität, Alter, Standort** sind nicht aus der Punktwolke ableitbar und extern
  beizubringen — die Hauptlücke bei beliebigen Flächen.
- **Vitalität** ist aus RGB+LiDAR nur als **struktureller/visueller Zustands-Proxy** (Kronen-
  verlichtung, Verfärbung, Totäste) belastbar, grob bis mittel und nur mit Kreuzvalidierung;
  die **physiologische** Vitalität (Wasserstress, Reserven) erfordert Red-Edge/NIR, Thermal
  oder Zeitreihen. Feine Schadstufen bleiben unsicher (auch für menschliche Gutachter).
- **Die Behandlungssteuerung (e) ist Entscheidungsunterstützung, kein Autopilot.** Die
  Kopplungsgewichte (Einfluss der Vitalität auf die Z-Baum-Wahl, Schwellen für Entnahme
  vs. Habitat) sind silvikulturelle Design-Entscheidungen und gegen Experten-Auszeichnung
  zu validieren — genau darin liegt der Forschungsanteil, nicht in einem Knopfdruck.

## 6. Roter Faden

Aus einem einzelnen Aufnahme-Setup entsteht ein **prognosefähiger, prüfbarer und
kommunizierbarer Bestandeszwilling** — von der Messung über die kreuzvalidierte Vitalität
bis zum begehbaren Zukunftswald, alles mit sauberer Herkunftstrennung. Diese Klammer
verbindet die Bausteine 1–5 zu einem kohärenten wissenschaftlichen Beitrag: nicht ein
weiteres Werkzeug, sondern die integrierte, offene und belastbare Verkettung von Struktur,
Zustand und Prognose.
