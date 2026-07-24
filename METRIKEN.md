# Ableitbare Bestandes- und Baumkennwerte

Katalog der Größen, die sich aus der Fusion von TLS-LiDAR, RGB (optional Red-Edge/NIR)
und dem Wuchsmodell je Einzelbaum und Bestand ableiten lassen. Jede Größe mit Modalität
und ehrlicher Machbarkeitsstufe:

- **✓ belastbar** — heute robust ableitbar
- **~ machbar** — mit Modalitäts-Fusion / Mehrfachscan / Mehraufwand, mit Restfehler
- **✗ schwer** — an der Auflösungs-/Verdeckungsgrenze, Forschungsbedarf, oder nicht aus RS

Grundprinzip: quantitativ aus **LiDAR** (Struktur), qualitativ aus **RGB/NIR** (Zustand),
zeitlich/prognostisch aus dem **Modell** — und Kernaussagen durch **Kreuzvalidierung**
beider Modalitäten am selben Baum abgesichert.

---

## A. Geometrie / Struktur — Einzelbaum
| Kennwert | Modalität | Stufe |
|---|---|---|
| Stammfußposition (x,y) | LiDAR | ✓ |
| BHD (1,3 m) | LiDAR (Zylinderfit) | ✓ |
| Baumhöhe | LiDAR | ✓ |
| Schaftform / Abholzigkeit (Durchmesser über Höhe) | LiDAR (QSM) | ✓ |
| Derbholzvolumen | LiDAR (QSM-Zylinder) | ✓ |
| Schlankheitsgrad h/d | LiDAR | ✓ |
| Kronenansatzhöhe (erster Grünast) | LiDAR + RGB-Greenness | ✓ |
| Kronenlänge / -breite / -projektionsfläche | LiDAR | ✓ |
| Kronenvolumen, Kronenasymmetrie | LiDAR | ~ |
| Schaftneigung / Schiefstand | LiDAR | ✓ |
| Astwerk / Astdichte / Astdurchmesser | LiDAR (QSM) | ~ |
| Stammoberfläche | LiDAR (QSM) | ✓ |

## B. Bestandesebene (aggregiert)
| Kennwert | Modalität | Stufe |
|---|---|---|
| Stammzahl/ha, Grundfläche/ha, Vorrat/ha | LiDAR | ✓ |
| Durchmesser- und Höhenverteilung | LiDAR | ✓ |
| Oberhöhe | LiDAR | ✓ |
| Mischungsanteile (Art) | RGB + LiDAR | ~ |
| Kronenschlussgrad / Überschirmung, Gap Fraction | LiDAR/RGB (hemisph.) | ✓ |
| Blattflächenindex (LAI) | LiDAR (Voxel/Gap) | ~ |
| Vertikale Schichtung / Straten | LiDAR | ✓ |
| Konkurrenz-/Dichteindex je Baum | LiDAR | ✓ |
| Bonität, Alter | extern (nicht aus RS) | ✗ |

## C. Vitalität / Waldschadenszustand
| Kennwert | Modalität | Stufe |
|---|---|---|
| tot / lebend | RGB + LiDAR | ✓ |
| Kronenverlichtung / -transparenz (ICP-Standard) | LiDAR + RGB | ✓ |
| Belaubungs-/Benadelungsgrad | LiDAR (Laubdichte) + RGB | ✓ |
| Verfärbung (chlorotisch/nekrotisch) | RGB | ✓ |
| Greenness-Proxy (ExG/GLI/VARI) | RGB | ✓ |
| NDVI / NDRE (echte Vitalität) | **Red-Edge/NIR** | ~ (Sensor nötig) |
| Totast-Anteil in der Krone | LiDAR-Holz + RGB-Braun | ~ |
| Höhe erster Totast | LiDAR + RGB | ~ |
| Zopftrocknis (Top-Dieback) | LiDAR + RGB | ~ |
| Wasserstress | **Thermal** | ✗ (Sensor nötig) |
| Vitalitätstrend (stärkstes Signal) | **Zeitreihe** | ~ (Wiederholung) |

## D. Schäden
| Kennwert | Modalität | Stufe |
|---|---|---|
| Rindenschäden (Schürf-/Rücke-/Schälschäden) | RGB-Textur/Farbe + LiDAR-Vertiefung | ~ |
| Stammwunden / Harzfluss | RGB | ~ |
| Pilzfruchtkörper (Konsolen) | RGB + LiDAR-Protrusion | ~ |
| Frostrisse / Blitzrinnen | LiDAR + RGB | ~ |
| Beulen / Überwallungen | LiDAR | ~ |

## E. Wertholzfaktoren (Qualität / Sortierung)
| Kennwert | Modalität | Stufe |
|---|---|---|
| Astfreie Schaftlänge (bis erster Ast) | LiDAR + RGB | ✓ |
| Astigkeit / max. Astdurchmesser | LiDAR (QSM) | ~ |
| Schaftgeradheit / Krümmung (Pfeilhöhe) | LiDAR | ✓ |
| Abholzigkeit (Taper) | LiDAR | ✓ |
| Ovalität / Exzentrizität | LiDAR | ✓ |
| Zwiesel / Mehrstämmigkeit | LiDAR | ✓ |
| Drehwuchs (Spiralfaser) | RGB-Rindentextur / LiDAR | ✗ |
| Sortimentsaushaltung + Erlöse | **Modell** (TreeGrOSS) | ✓ |
| Güteklasse (A–D, EN 1316) als Proxy | Fusion + Regeln | ~ |

## F. Habitat / Biodiversität
| Kennwert | Modalität | Stufe |
|---|---|---|
| Stehendes/liegendes Totholz | LiDAR + RGB | ✓ |
| Kronentotholz | LiDAR + RGB | ~ |
| Höhlen / Spechthöhlen | LiDAR + RGB | ~ |
| Mikrohabitate (Rindentaschen, Wunden) | RGB + LiDAR | ~ |
| Epiphyten / Moos / Flechten | RGB | ✗ (grob) |

## G. Standort / Kontext (per Koordinate)
| Kennwert | Modalität | Stufe |
|---|---|---|
| Boden (pH, Textur, C) | SoilGrids | ✓ |
| Relief / Hangneigung / Exposition | DEM | ✓ |
| Klima (Temp/Niederschlag) | WorldClim/DWD | ✓ |
| Landbedeckung / Schutzstatus | OSM/CORINE | ✓ |

---

## Querschnitts-Grenzen
- **Verdeckung** (Einzelscan sieht Rückseite/Kroneninneres nicht) → Mehrfachscan/Fusion.
- **Auflösung** — dünne Zweige, feine Schäden an der Punktdichte-Grenze.
- **Farb-Ambiguität** — totes Holz ↔ lebende Rinde beide braun; Farbe trennt „Laub vs.
  kein Laub", nicht sicher „lebend vs. tot". Erst Fusion mit LiDAR-Struktur trennt sauber.
- **Physiologische** Vitalität und feine Schadstufen brauchen Red-Edge/NIR, Thermal oder
  Zeitreihen — RGB+LiDAR liefern nur den strukturell-visuellen Zustands-Proxy.
- **Bonität/Alter/Standort** kommen nicht aus der Wolke.

Details zum wissenschaftlichen Rahmen: [EXPOSE.md](EXPOSE.md).
