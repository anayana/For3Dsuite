# Software-/Methoden-Paper — Gliederung

Enabling-Infrastruktur-Veröffentlichung zur kumulativen Dissertation
([DISSERTATION.md](DISSERTATION.md)): die offene, reproduzierbare Pipeline, auf der die
Domänen-Paper P1–P3 aufbauen.

**Kernbotschaft (der Reviewer-Test):** Nicht die Einzelbausteine sind neu, sondern die
**integrierte, provenienz-getrennte, cross-modal validierte Pipeline** von terrestrischer
Aufnahme bis zum begehbaren, prognosefähigen Zwilling — offen, selbst hostbar, reproduzierbar.

---

## Statement of need
Getrennte Werkzeugketten für TLS-Struktur, RGB-Zustand und Einzelbaum-Wuchsmodellierung
werden selten am selben georeferenzierten Objekt zusammengeführt und wechselseitig
abgesichert. Es fehlt eine offene, reproduzierbare Plattform, die Messung, qualitativen
Zustand, Prognose und immersive Vermittlung mit sauberer Herkunftstrennung verbindet.

## Architektur & Design
- Verarbeitungsschichten (Layer 1–5): Aufnahme → Inventur → RGB-Analyse → Wuchsmodell →
  Zwilling (Panorama/3DGS).
- **Provenienz-Datenmodell**: beobachtet / algorithmisch abgeleitet / kartenbasiert
  angereichert / gemessen — jeder Wert mit Quelle, Lizenz, Konfidenz.
- Service-Trennung: Verarbeitung (Python), Wuchs-Engine (Java/TreeGrOSS, GPL isoliert),
  Viewer (JS), Self-Hosting-Stack (Caddy/Garage/FastAPI).
- Abgrenzung CPU-Pipeline vs. GPU-3DGS.

## Methoden (Kurzbeschreibung + Referenz auf die Skripte)
- Einzelbaum-Inventur aus der Wolke (`inventory_from_cloud.py`); Detektions-Validierung
  gegen Ground-Truth (`validate_treescope.py`).
- Qualitative RGB-Auswertung je Baum (`qualitative_rgb.py`); **cross-modale Validierung**
  RGB↔LiDAR (`crossvalidate_rgb_lidar.py`) — der methodische Kern.
- Geodaten-Anreicherung per Koordinate (`geo_enrich.py`), lokale Bildanalyse
  (`image_analyze.py`).
- Wuchsmodell-Kopplung (`treegross_export.py`, `growth-service/` = echte TreeGrOSS-Engine).
- Immersiver Zwilling: Panorama (Pannellum), Punktwolke (Three.js), 3D Gaussian Splatting
  (`splat.html`, `points_to_splat.py`, `clean_splat.py`, `seed_splat.py`).
- Der Kennwert-Umfang: [METRIKEN.md](METRIKEN.md).

## Reproduzierbarkeit
- **Docker**: CPU-Stack (Suite + Offline-Reproduktion) per einem Befehl; GPU-3DGS als
  separates CUDA-Image **oder** RunPod-Skript (siehe [docker/README.md](docker/README.md)).
- Offene Beispieldaten (Renon E57, CC-BY; TreeScope; Poly-Haven CC0) + committete
  Eingangsdaten für den reproduzierbaren Prognose-Lauf.
- Lizenzklarheit (GPLv3 für die TreeGrOSS-Komponente, isoliert als Dienst).

## Fallstudie / Demonstration
ICOS-Renon (Rekonstruktion aus E57, 87 Inventurmarker, TreeGrOSS-Prognose 2044,
begehbarer Zwilling) + Benchmark-Validierung an TreeScope; Hecken/Waldrand als weitere
Anwendungen.

## Grenzen
Einzelscan-Verdeckung, TLS-BHD-Kalibrierung, Artansprache aus Panoramen begrenzt, 3DGS
braucht dichte Aufnahme, Bonität/Alter extern. (Details: [EXPOSE.md](EXPOSE.md) §5.)

## Vor der Einreichung noch zu erledigen
- ~~Automatisierte **Tests + CI** (GitHub Actions)~~ ✓ [tests/test_core.py](tests/test_core.py)
  (6 Unit-Tests der Kernfunktionen) + [.github/workflows/tests.yml](.github/workflows/tests.yml)
  (pytest auf Python 3.10/3.11 bei jedem Push).
- ~~`CITATION.cff`~~ ✓ ([CITATION.cff](CITATION.cff)); **Zenodo-Release → DOI** noch offen.
- Lizenz festlegen + LICENSE-Datei (in CITATION.cff als TODO markiert; TreeGrOSS ist GPL).
- GPU-Image auf einer CUDA-Maschine bauen/verifizieren.
- Ein kompaktes Architektur-Diagramm.

## Zieljournale
SoftwareX · Environmental Modelling & Software · Journal of Open Source Software (leicht) ·
Methods in Ecology and Evolution (Applications) · Ecological Informatics · Remote Sensing.
