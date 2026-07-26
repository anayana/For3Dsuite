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

Das Spektrum der so je Baum und Bestand ableitbaren Größen — Struktur, Vitalität/
Waldschadenszustand, Rindenschäden, Wertholzfaktoren, Habitatstrukturen — ist mit
Modalität und ehrlicher Machbarkeitsstufe in [METRIKEN.md](METRIKEN.md) katalogisiert.

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

**(f) Spektrale funktionelle Traits (konzeptionelle Erweiterung).** Der in (e)
skizzierte Schritt wird zum eigenen Strang: ein co-lokalisierter Multispektral-Sensor
(Red-Edge/NIR, alternativ Multispektralkamera) am **selben Stativ** wie die RGB-/TLS-
Aufnahme, per identischer Registrierung über die Punktwolke je Baum zurückprojiziert.
Damit wird aus dem *visuellen* Zustands-Proxy ein **physiologisch belastbares Signal**:
echte Vegetationsindizes (NDVI/NDRE) und daraus abgeleitete **funktionelle Blatt-/
Kroneneigenschaften** (Chlorophyll-/Stickstoff-Proxy, Wassergehalt) — kreuzvalidiert gegen
die LiDAR-Struktur desselben Baums. Das verbindet die Zustands-/Vitalitätsdiagnose (b)
mit dem Forschungsfeld *funktionelle Pflanzeneigenschaften* und macht die
Biodiversitäts-Proxys (Struktur) um eine **spektrale Trait-Achse** reicher. Ehrlich:
erfordert die Multispektral-Hardware und eine radiometrische Kalibrierung; ohne sie bleibt
es beim Greenness-Proxy.

**(g) Syntheseschleife: vom Zwilling zurück zu synthetischen Sensordaten
(TreeGrOSS → HELIOS++, konzeptionell).** Der über das Wuchsmodell projizierte Zukunfts-
bzw. behandelte Bestand wird nicht nur im Viewer gezeigt, sondern in einen
physikalisch-basierten LiDAR-Simulator (**HELIOS++**, aus demselben offenen Ökosystem wie
die genutzten SYSSIFOSS-Daten) eingespeist, der daraus **synthetische TLS-/ALS-/UAV-
Punktwolken** des projizierten Bestands erzeugt. Das schließt den Kreislauf:
*realer Scan → Inventur → Wuchsprognose → simulierter Scan der Prognose*. Der Nutzen ist
dreifach: (i) **Szenarioanalyse auf synthetischen Fernerkundungsdaten** — Durchforstung,
Artwechsel, Schadensverlauf, Brennstoff-/Bestandesstruktur (Feuerrisiko-Proxy) — ohne auf
Jahrzehnte realer Aufnahmen zu warten; (ii) **Trainings-/Benchmark-Daten mit bekannter
Wahrheit**, da die Parameter des synthetischen Bestands exakt vorliegen (die SYSSIFOSS-
Prämisse); (iii) **Sensor- und Aufnahmedesign-Studien** (welche Scan-Geometrie welche
Kennwerte rekonstruiert). Ehrlich: die simulierten Sensordaten sind gegen reale Scans zu
kalibrieren, nur so belastbar wie die Baumgeometrie des Wuchsmodells, und bergen eine
Zirkularitätsgefahr (das Modell reproduziert seine eigenen Annahmen) — daher zwingend
gegen reale Wiederholungsaufnahmen zu validieren, nicht als Selbstbeleg.

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
7. **Spektrale Traits:** Hebt co-lokalisiertes Red-Edge/NIR die Vitalitäts- und
   Trait-Diagnose vom Greenness-Proxy auf physiologisch belastbare Indizes (NDVI/NDRE,
   Chlorophyll-/Wasser-Proxys), wenn sie gegen die LiDAR-Struktur desselben Baumes
   kreuzvalidiert werden? Welche funktionellen Blatt-/Kroneneigenschaften sind so
   flächig kartierbar?
8. **Synthese:** Wie realistisch lassen sich aus modellprojizierten Beständen synthetische
   LiDAR-/optische Daten erzeugen (HELIOS++), und taugen sie — mit bekannter Wahrheit — als
   Trainings-/Benchmark-Grundlage sowie für Szenarioanalysen (Durchforstung, Artwechsel,
   Brennstoffstruktur/Feuerrisiko) und Sensor-/Aufnahmedesign, ohne der Zirkularität zu
   verfallen (Validierung gegen reale Wiederholungsaufnahmen)?

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
- **Synthetische Fernerkundung für Szenarien und Methodenentwicklung** — simulierte Scans
  (HELIOS++) modellprojizierter Bestände als Benchmark mit bekannter Wahrheit, für
  Szenarioanalysen (Durchforstung, Artwechsel, Brennstoffstruktur/Feuerrisiko) und
  Sensordesign.
- **Funktionelle Traits und spektrale Diagnose** — co-lokalisiertes Multispektral
  (Red-Edge/NIR) je Baum für NDVI/NDRE und funktionelle Blatt-/Kroneneigenschaften.

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
- **Spektrale Traits (f) und Syntheseschleife (g) sind konzeptionelle Erweiterungen**,
  nicht Teil des heutigen Standes. (f) steht und fällt mit Multispektral-Hardware und
  radiometrischer Kalibrierung; ohne sie bleibt es beim Greenness-Proxy. (g) ist nur so
  belastbar wie die Baumgeometrie des Wuchsmodells und die Kalibrierung des simulierten
  Sensors und trägt eine **Zirkularitätsgefahr** (das Modell reproduziert seine eigenen
  Annahmen) — synthetische Daten sind daher stets gegen reale Aufnahmen zu prüfen, nie als
  Selbstbeleg. Beide sind als Anschlussfähigkeit an ein breiteres Vegetationsfernerkundungs-
  Profil (aktiv+passiv optisch, Arten, Schäden, Biodiversitäts-Proxys, synthetische Daten)
  gedacht, nicht als Kern-Promotionsleistung.

## 6. Roter Faden

Aus einem einzelnen Aufnahme-Setup entsteht ein **prognosefähiger, prüfbarer und
kommunizierbarer Bestandeszwilling** — von der Messung über die kreuzvalidierte Vitalität
bis zum begehbaren Zukunftswald, alles mit sauberer Herkunftstrennung. Diese Klammer
verbindet die Bausteine 1–5 zu einem kohärenten wissenschaftlichen Beitrag: nicht ein
weiteres Werkzeug, sondern die integrierte, offene und belastbare Verkettung von Struktur,
Zustand und Prognose.
