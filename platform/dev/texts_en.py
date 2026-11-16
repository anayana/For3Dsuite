#!/usr/bin/env python3
"""texts_en.py -- Szenendaten ins Englische (Titel, Beschreibung, Legenden, Marker).

Quelle der Titel/Beschreibungen: scene_texts_en.json. Alle uebrigen Textwerte
(Legenden, Stufen, Marker-Bezeichnungen und -Werte, Story-Texte) ueber die
Tabellen unten: exakte Saetze, dann Muster. Schluessel bleiben unveraendert.

  python platform/dev/texts_en.py           # docs/data/ sofort umstellen
export_static.export_scene() ruft translate_scene() fuer jede Szene auf.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OVERLAY = json.loads((HERE / "scene_texts_en.json").read_text(encoding="utf-8"))
SKIP_KEYS = {"id", "url", "paper", "license", "bin", "bin_url", "bin_gt", "bin_gt_url",
             "bin_itcd", "bin_itcd_url", "bin_strata", "bin_strata_url", "bin_light",
             "bin_light_url", "thumb", "thumb_url", "pano", "pano_url", "src", "file",
             "video", "video_url", "created", "type", "kind", "dataset"}

SPECIES = {"Erle": "Alder", "Birke": "Birch", "Traubeneiche": "Sessile oak",
           "Roteiche": "Red oak", "Rotbuche": "European beech", "Buche": "Beech",
           "Fichte": "Norway spruce", "Waldkiefer": "Scots pine", "Bergahorn": "Sycamore maple",
           "Douglasie": "Douglas fir", "Lärche": "Larch", "Tanne": "Silver fir"}

EXACT = {
    # Stufen, Umschalter
    "Ausgedünnt": "Thinned", "Voll": "Full", "Höhe": "Height",
    "Nur Bodenscan": "Ground scan only", "Boden + Kronenscan": "Ground + canopy scan",
    "Nur vom Kronenscan": "Canopy scan only", "Boden- vs. Kronenscan": "Ground vs. canopy scan",
    "Einzelbaum-Ground-Truth": "Single-tree ground truth",
    # Marker-Werte
    "gut": "good", "schwach": "weak", "maessig": "moderate", "kraeftig": "strong",
    "Kräftig": "Strong", "unauffaellig": "inconspicuous", "auffaellig": "conspicuous",
    "gefunden": "found", "nicht gefunden": "not found", "stehend": "standing",
    "Zurück": "Back", "Weiter": "Next", "Boden": "Ground", "Struktur": "Structure",
    "Art": "Species", "Verjüngung": "Regeneration", "verjuengung": "regeneration",
    "untere Schicht": "lower layer", "mittlere Schicht": "middle layer",
    "ITCD-Segmentierung (eigene Kronenpunkte)": "ITCD segmentation (own crown points)",
    "Datenlage schwach (wenig Punkte oder kurzer Bogen) -- die Werte stehen trotzdem da, die Spanne der Verfahren zeigt, was sie taugen":
        "Weak data (few points or short arc) — the values are shown anyway; the spread of the methods shows what they are worth",
    "Baumart nach Erscheinungsbild bestimmt; Maße für den sichtbaren Baum geschätzt (keine Feldmessung).":
        "Species identified from appearance; dimensions estimated for the visible tree (no field measurement).",
    "direkt aus dem Bild (qualitativ)": "directly from the image (qualitative)",
    "algorithmisch aus dem Bild (heuristisch, RGB-only)": "algorithmically from the image (heuristic, RGB only)",
    "per Koordinate aus freien Fremdquellen": "by coordinate from open third-party sources",
    "ICOS-Station IT-Ren (Stationskoordinate, nicht Setup-genau)": "ICOS station IT-Ren (station coordinate, not setup-specific)",
    # Legenden
    "Einfärbungen": "Colourings",
    "Höhe über Boden — der Datensatz hat keine Kamerafarbe": "Height above ground — the dataset has no camera colour",
    "Ground Truth — eine Farbe je Baum, von Hand segmentiert": "Ground truth — one colour per tree, segmented by hand",
    "Schicht: Boden": "Stratum: ground", "Schicht: Unterwuchs 0,5–2 m": "Stratum: understorey 0.5–2 m",
    "Schicht: untere Schicht": "Stratum: lower layer", "Schicht: mittlere Schicht": "Stratum: middle layer",
    "Schicht: Kronendach": "Stratum: canopy",
    "Licht am Boden (Tagesmittel, Tag-und-Nacht-Gleiche): dunkelblau 0,1 % … gelb 100 %":
        "Light at the ground (daily mean, equinox): dark blue 0.1 % … yellow 100 %",
    "Schichten relativ zur Kronendachhöhe; Licht = Schätzung aus der Punktwolke ohne Verdeckungskorrektur.":
        "Strata relative to canopy height; light = estimate from the point cloud without occlusion correction.",
    "Einzelbäume = eigene Segmentierung (itcd_cloud.py). Gleiche Farbe wie in der Ground Truth = Baum richtig getrennt; grau = nicht zugeordnet.":
        "Single trees = own segmentation (itcd_cloud.py). Same colour as in the ground truth = tree correctly separated; grey = not assigned.",
    "nur vom Kronenscan erfasst (kein Bodenscan-Punkt im Umkreis von 5 cm)":
        "captured by the canopy scan only (no ground-scan point within 5 cm)",
    "auch vom Boden erfasst": "also captured from the ground",
    "Stufen unten: Nur Bodenscan / Boden + Kronenscan. QSM-Modell: TreeQSM aus Boden + Kronenscan.":
        "Levels below: ground scan only / ground + canopy scan. QSM model: TreeQSM from ground + canopy scan.",
    "Semantische Ground Truth": "Semantic ground truth",
    "manuell annotiert, Feld 'Class' im LAZ": "manually annotated, field 'Class' in the LAZ",
    "Die Zuordnung Zahl -> Klassenname ist ABGELEITET: der Datensatz liefert nur Zahlen, der Aufsatz nur eine Abbildung. Herleitung und Sicherheit je Klasse in data/segforests/classes.json.":
        "The mapping number → class name is DERIVED: the dataset only provides numbers, the paper only a figure. Derivation and confidence per class in data/segforests/classes.json.",
    "Strauch / Bodenvegetation (abgeleitet)": "Shrub / ground vegetation (derived)",
    "Boden (abgeleitet, sicher)": "Ground (derived, certain)",
    "Aeste + Blaetter (abgeleitet, sicher)": "Branches + leaves (derived, certain)",
    "Stamm (abgeleitet, sicher)": "Stem (derived, certain)",
    "niedrige Vegetation / liegendes Totholz (abgeleitet, unsicher)": "Low vegetation / lying deadwood (derived, uncertain)",
    "Vegetation, Nebenklasse (abgeleitet, unsicher)": "Vegetation, minor class (derived, uncertain)",
    "Nicht-Vegetation (laut Aufsatz Label 6-9)": "Non-vegetation (labels 6–9 according to the paper)",
    "Nicht-Vegetation, aufrecht in Brusthoehe -- Pfahl oder Person (laut Aufsatz Label 6-9)":
        "Non-vegetation, upright at breast height — pole or person (labels 6–9 according to the paper)",
    "Unterstand / niedriger Kronenraum (abgeleitet, unsicher)": "Understorey / low crown space (derived, uncertain)",
    "duenner Baum / Zweig (abgeleitet, unsicher)": "Thin tree / twig (derived, uncertain)",
    "Sichtbarkeit / Verdeckung": "Visibility / occlusion",
    "aus wie vielen der 6 TLS-Standpunkte ein Punkt gesehen wird": "from how many of the 6 TLS positions a point is seen",
    "1 Standpunkt — einseitig, verdeckungsgefährdet": "1 position — one-sided, prone to occlusion",
    "2 Standpunkte": "2 positions", "6 — rundum frei sichtbar": "6 — visible from all sides",
    "Struktur (HVI)": "Structure (HVI)",
    "Neuntöter": "Red-backed shrike", "Dorngrasmücke": "Common whitethroat",
    "Goldammer": "Yellowhammer", "Fledermaus-Leitlinie": "Bat commuting route",
    "Wildbienen-Saum": "Wild-bee margin",
    "Dornsträucher 1,5–3 m mit offenem Krautsaum zur Bodenjagd": "Thorny shrubs 1.5–3 m with an open herb margin for ground hunting",
    "Lärche": "Larch",
    "niedrige bis mittlere dichte Sträucher, halboffener Saum": "low to medium dense shrubs, semi-open margin",
    "Hecke mit einzelnen hohen Singwarten und Krautsaum": "hedge with single tall song posts and a herb margin",
    "hohe, durchgehende Hecke ohne Lücken als Leitlinie": "tall, continuous hedge without gaps as a commuting line",
    "besonnter offener Krautsaum, niedrige Struktur": "sunny open herb margin, low structure",
    "hemispheR (Lueckenanteil aus Zenit-Fisheye)": "hemispheR (gap fraction from zenith fisheye)",
    "lidR LAD (MacArthur-Horn) ueber normalisierte Hoehe": "lidR LAD (MacArthur-Horn) over normalised height",
    "Kein Validierungspaar: der optische Weg stammt aus einem Panorama, das aus Scanner-Pinhole-Bildern reprojiziert wurde (nicht aus einer Fisheye-Optik), und ueberschaetzt den Lueckenanteil bei ueberstrahltem Himmel. Der strukturelle Weg wendet MacArthur-Horn auf einen EINZELNEN terrestrischen Standpunkt an -- die Formel unterstellt jedoch senkrechte Durchdringung wie bei ALS, weshalb Verdeckung hinter Staemmen und in der oberen Krone den Wert nach unten zieht. Beide Zahlen sind Groessenordnungen, keine Messwerte.":
        "Not a validation pair: the optical route comes from a panorama reprojected from scanner pinhole images (not from fisheye optics) and overestimates the gap fraction under an overexposed sky. The structural route applies MacArthur-Horn to a SINGLE terrestrial position — but the formula assumes vertical penetration as in ALS, so occlusion behind stems and in the upper crown pulls the value down. Both numbers are orders of magnitude, not measurements.",
    "Einzelbaum-Wolke, kein Plot; lokale Koordinaten ohne CRS. Panorama und Punktwolke des Datensatzes sind NICHT ko-registriert.":
        "Single-tree cloud, not a plot; local coordinates without CRS. Panorama and point cloud of the dataset are NOT co-registered.",
    "Alter je Baum aus der Hoehe ueber die Bonitaetsfunktion der eingesetzten TreeGrOSS-Parameterdatei (Fichte, NAGEL 1999), verankert am dokumentierten Oberschicht-Alter von 200 Jahren. Die Funktion ist fuer Nordwestdeutschland kalibriert und wird hier auf einen subalpinen Standort (~1730 m) extrapoliert.":
        "Age per tree from height via the site-index function of the TreeGrOSS parameter file used (Norway spruce, NAGEL 1999), anchored to the documented upper-layer age of 200 years. The function is calibrated for north-western Germany and is extrapolated here to a subalpine site (~1730 m).",
    "Stamm in der Testflaeche und BHD >= 10 cm; ohne messbaren BHD (Brettwurzel, Schraeglage) zaehlt der Baum ab 10 m Hoehe mit. Randbaeume zaehlen weder als Referenz noch als Fehlalarm.":
        "Stem inside the test area and DBH ≥ 10 cm; without measurable DBH (buttress, lean) the tree counts from 10 m height. Edge trees count neither as reference nor as false alarm.",
    "keine Scannerstandorte, keine Verdeckungskorrektur; oberes Kronendach unterschaetzt -> Luecken eher ueberschaetzt; Ergebnis haengt von der Voxelkante ab; Werte relativ deuten":
        "no scanner positions, no occlusion correction; upper canopy underestimated → gaps rather overestimated; result depends on voxel size; interpret values relatively",
    # Wilder-Kaiser-Story
    "Nördliche Kalkalpen · Wilder Kaiser · Tirol": "Northern Limestone Alps · Wilder Kaiser · Tyrol",
    "Großlandschaft": "Landscape", "Nördliche Kalkalpen (Kaisergebirge)": "Northern Limestone Alps (Kaisergebirge)",
    "Tirol, Österreich": "Tyrol, Austria", "Höhenstufe": "Altitudinal zone",
    "Seehöhe (Bestand)": "Elevation (stand)", "Waldfläche Tirol": "Forest area Tyrol",
    "Gründigkeit": "Soil depth", "flach- bis mittelgründig": "shallow to medium deep",
    "sauer / neutral–basisch": "acidic / neutral–basic",
    "durchlässig, karstig (Trockenstress möglich)": "permeable, karstic (drought stress possible)",
    "Bergahorn, Lärche, sonst.": "Sycamore maple, larch, other",
    "Natürliche Waldgesellschaft": "Natural forest community",
    "Bäume je ha über BHD-Klassen": "Trees per ha by DBH class", "Bäume/ha": "trees/ha",
    "Kennzahlen (dieser Bestand, illustrativ)": "Key figures (this stand, illustrative)",
    "Häufigste Klasse": "Most frequent class", "Realer ÖWI-Bezug (Österreich)": "Real Austrian NFI reference",
    "Bestandeskennwerte je Hektar": "Stand metrics per hectare",
    "Reale Regionaldaten (ÖWI 2016/21)": "Real regional data (Austrian NFI 2016/21)",
    "Vorrat Tirol (Ø Waldfläche)": "Growing stock Tyrol (mean forest area)",
    "Vorrat Österreich gesamt": "Growing stock Austria total",
    "Dieser Bestand – standorttypisch (illustrativ)": "This stand — typical for the site (illustrative)",
    "Grundfläche G": "Basal area G", "Mittelhöhe Hg": "Mean height Hg",
    "Naturverjüngung im Bestandesschatten": "Natural regeneration in the stand's shade",
    "Verjüngung (standorttypisch)": "Regeneration (typical for the site)",
    "Naturverjüngung (keine Pflanzung)": "Natural regeneration (no planting)",
    "Führende Arten": "Leading species", "Reale ÖWI-Befunde (Österreich)": "Real Austrian NFI findings",
    "Verjüngungsdefizit": "Regeneration deficit", "Verjüngung durch Verbiss geschädigt": "Regeneration damaged by browsing",
    "Schälschäden im Schutzwald": "Bark-stripping damage in protection forest",
    "ein- bis zweischichtig, annähernd gleichaltrig": "one- to two-layered, approximately even-aged",
    "Tirol gesamt (ÖWI, gemessen)": "Tyrol total (Austrian NFI, measured)", "LK Tirol / ÖWI": "LK Tirol / Austrian NFI",
    "Baumarten": "Tree species", "Durchmesserverteilung": "Diameter distribution",
    "Bestandeswerte": "Stand values", "Region": "Region",
    "Klima-/Reliefangaben standorttypisch; Tirol-Kennzahlen gemessen (ÖWI). Standorttypische Referenzwerte für einen Bergmischwald der Nördlichen Kalkalpen – keine Feldaufnahme an diesem Panorama.":
        "Climate/relief values typical for the site; Tyrol figures measured (Austrian NFI). Site-typical reference values for a mixed mountain forest of the Northern Limestone Alps — no field survey at this panorama.",
    "Standorttypische Referenzwerte für einen Bergmischwald der Nördlichen Kalkalpen – keine Feldaufnahme an diesem Panorama.":
        "Site-typical reference values for a mixed mountain forest of the Northern Limestone Alps — no field survey at this panorama.",
    "Tirol-Anteile und Waldgesellschaft gemessen/kartiert (ÖWI, BFW). Die standorttypische Mischung dieses Bestandes ist illustrativ.":
        "Tyrol shares and forest community measured/mapped (Austrian NFI, BFW). The site-typical mixture of this stand is illustrative.",
    "Verteilung standorttypisch modelliert (keine Ortsaufnahme); der Starkholz-Anteil ist ein realer ÖWI-Befund für Österreich.":
        "Distribution modelled for the site (no local survey); the share of large timber is a real Austrian NFI finding.",
    "Reale Regionaldaten sind als solche gekennzeichnet und quellenbelegt; die bestandsbezogenen Werte dieses Panoramas sind standorttypisch gerechnet (keine Ortsaufnahme).":
        "Real regional data are marked as such and referenced; the stand values of this panorama are calculated for the site type (no local survey).",
    "Verbiss-/Schälschäden gemessen (ÖWI, österreichweit). Verjüngungsbild dieses Bestandes standorttypisch.":
        "Browsing/bark-stripping damage measured (Austrian NFI, Austria-wide). Regeneration picture of this stand typical for the site.",
    "<p>Der <b>Wilde Kaiser</b> ist ein schroffer Kalkstock des Kaisergebirges in Tirol (Österreich). Das Panorama zeigt einen <b>montanen Bergmischwald</b> an seinem bewaldeten Fuß – die typische Höhenstufe zwischen Tal und Latschengürtel.</p><p>Das Klima ist <b>kühl-humid</b>: viel Niederschlag, kurze Vegetationszeit, lange Schneelage. Solche Bestände erfüllen oft eine <b>Schutzwaldfunktion</b> gegen Steinschlag, Lawinen und Erosion am Steilhang.</p>":
        "<p>The <b>Wilder Kaiser</b> is a rugged limestone massif of the Kaisergebirge in Tyrol (Austria). The panorama shows a <b>montane mixed mountain forest</b> at its wooded foot — the typical altitudinal zone between valley and dwarf-pine belt.</p><p>The climate is <b>cool and humid</b>: much precipitation, a short growing season, long snow cover. Such stands often serve as <b>protection forest</b> against rockfall, avalanches and erosion on steep slopes.</p>",
    "<p>Auf dem <b>Wetterstein-Kalk und Dolomit</b> der Kalkalpen bilden sich flachgründige, <b>skelettreiche</b> Böden. Der Mineralboden ist <b>basenreich</b> (viel Kalzium), die Humusauflage dagegen sauer.</p><p>Das Gestein ist stark <b>durchlässig und verkarstet</b> – Wasser versickert rasch, sodass es trotz hoher Niederschläge sommerliche Trockenphasen geben kann. Die im Vordergrund sichtbaren <b>hellen Kalksteine</b> am Weg verraten den Untergrund.</p>":
        "<p>On the <b>Wetterstein limestone and dolomite</b> of the Limestone Alps, shallow, <b>stony</b> soils develop. The mineral soil is <b>base-rich</b> (much calcium), the humus layer acidic.</p><p>The rock is highly <b>permeable and karstified</b> — water seeps away quickly, so summer dry spells can occur despite high precipitation. The <b>pale limestones</b> visible along the path in the foreground reveal the bedrock.</p>",
    "<p>Die natürliche Waldgesellschaft der montanen Kalkalpen ist der <b>Fichten-Tannen-Buchenwald</b> (Abieti-Fagetum). Alle drei Arten ergänzen sich ökologisch: die <b>Fichte</b> dominiert wirtschaftlich, die schattentolerante <b>Tanne</b> wurzelt tief und stabilisiert, die <b>Buche</b> verbessert Humus und Bodenleben.</p><p>Im Bild deutlich: die dunklen, säulenförmigen <b>Fichten</b> rechts, dazwischen das hellere Laub der <b>Buche</b>. Edellaubhölzer wie Bergahorn und einzelne Lärchen mischen sich bei.</p>":
        "<p>The natural forest community of the montane Limestone Alps is the <b>spruce–fir–beech forest</b> (Abieti-Fagetum). The three species complement each other ecologically: <b>Norway spruce</b> dominates economically, the shade-tolerant <b>silver fir</b> roots deeply and stabilises, <b>beech</b> improves humus and soil life.</p><p>Clearly visible: the dark, columnar <b>spruces</b> on the right, with the lighter foliage of <b>beech</b> in between. Valuable broadleaves such as sycamore maple and single larches are mixed in.</p>",
    "<p>Die Verteilung hat <b>einen Gipfel</b> in der Mitte (glockenförmig) und ist um den Mitteldurchmesser gruppiert. Das ist typisch für einen <b>annähernd gleichaltrigen Bestand in der Reifephase</b> – die meisten Bäume sind gemeinsam aufgewachsen und heute ähnlich dick.</p><p>Der kleine Fuß in den dünnen Klassen ist die einsetzende <b>Verjüngung</b> und untergeordnete Bäume.</p>":
        "<p>The distribution has <b>one peak</b> in the middle (bell-shaped) and is grouped around the mean diameter. This is typical of an <b>approximately even-aged stand in the mature phase</b> — most trees grew up together and are of similar thickness today.</p><p>The small foot in the thin classes is beginning <b>regeneration</b> and suppressed trees.</p>",
    "<p>Oben die real erhobenen <b>Regionaldaten</b> der Österreichischen Waldinventur (Tirol / Österreich). Darunter die Werte <b>dieses Bestandes</b>: standorttypisch für einen Reifebestand gerechnet, Grundfläche und Mitteldurchmesser aus der <b>Durchmesserverteilung</b>.</p>":
        "<p>Above, the actually surveyed <b>regional data</b> of the Austrian National Forest Inventory (Tyrol / Austria). Below, the values of <b>this stand</b>: calculated for a mature stand typical of the site, basal area and mean diameter from the <b>diameter distribution</b>.</p>",
    "<p>Unter dem geschlossenen Kronendach keimen im Halbschatten schattentolerante <b>Tanne, Buche</b> und <b>Fichte</b> nach. Diese <b>Naturverjüngung</b> bildet die nächste Waldgeneration heran, sobald das Kronendach durch Ernte oder Störung auflichtet.</p><p>Der Engpass ist meist der <b>Wildverbiss</b>: v. a. die Tanne wird von Reh- und Rotwild stark verbissen und fällt ohne Bejagung oder Schutz aus dem Mischwald heraus.</p>":
        "<p>Under the closed canopy, shade-tolerant <b>silver fir, beech</b> and <b>Norway spruce</b> germinate in half-shade. This <b>natural regeneration</b> builds the next forest generation as soon as the canopy opens through harvest or disturbance.</p><p>The bottleneck is usually <b>browsing by deer</b>: silver fir in particular is heavily browsed by roe and red deer and drops out of the mixed forest without hunting or protection.</p>",
}

PATTERNS = [
    (r"^([\d.]+) streng · ([\d.]+) tolerant$", r"\1 strict · \2 tolerant"),
    (r"^Referenzbaum (\d+)$", r"Reference tree \1"),
    (r"^Baum (\S+)$", r"Tree \1"),
    (r"^Baum (\S+): Bodenscan vs\. Kronenscan$", r"Tree \1: ground scan vs. canopy scan"),
    (r"^Datenlage gut \(Bogen >= (\d+) Grad, >= (\d+) Punkte in der Scheibe\)$",
     r"Good data (arc ≥ \1°, ≥ \2 points in the slice)"),
    (r"^Kreisfit verworfen \(Bogen (\d+) Grad, RMS ([\d.]+) cm\) -- Brettwurzel, Schraeglage oder Aeste in Brusthoehe$",
     r"Circle fit rejected (arc \1°, RMS \2 cm) — buttress, lean or branches at breast height"),
    (r"^Schaftkontrolle verworfen: in 2,0 m kein passender Stammquerschnitt \(Laub/Aeste in Brusthoehe\?\)$",
     "Stem check rejected: no matching stem cross-section at 2.0 m (leaves/branches at breast height?)"),
    (r"^Stamm ausserhalb/am Rand der Testflaeche$", "Stem outside/at the edge of the test area"),
    (r"^zu wenige Punkte in 1,2-1,4 m$", "too few points at 1.2–1.4 m"),
    (r"^gefunden \(BHD ([\d.]+) cm\)$", r"found (DBH \1 cm)"),
    (r"^(Neuntöter|Dorngrasmücke|Goldammer|Fledermaus-Leitlinie|Wildbienen-Saum) \(([\d.]+)\)$", None),
    (r"^(Erle|Birke|Traubeneiche|Roteiche|Rotbuche|Buche|Fichte|Waldkiefer|Bergahorn|Douglasie) (.+)$", None),
    (r"^(\d)_(\w+): 3DGS gegen photogrammetrische Referenz \(Paper B\)\. Daten CC BY 4\.0, Pellis et al\. 2025\.$",
     r"\1_\2: 3DGS against photogrammetric reference (Paper B). Data CC BY 4.0, Pellis et al. 2025."),
    (r"^(\d+)% aller Punkte nur von EINEM Standpunkt gesehen — dort ist eine Einzelscan-Inventur blind\.$",
     r"\1 % of all points seen from only ONE position — a single-scan inventory is blind there."),
    (r"^Detektor 3DFin; Referenz = manuell segmentierte Bäume im Testgebiet ab 10 cm BHD \(ohne messbaren BHD: ab 10 m Höhe\)\.(?: Einzelbaum-Segmentierung: mittlere IoU ([\d.]+)\.)?$",
     None),
    (r"^Transmission = Produkt \(1 - Deckung\) der durchquerten Voxel; Deckung = 2-cm-Punkte / \(v/0,02\)\^2$",
     "Transmission = product (1 − cover) of the traversed voxels; cover = 2 cm points / (v/0.02)²"),
    (r"^≈ (.+) Bäume/ha$", r"≈ \1 trees/ha"),
    (r"^≈ (.+) % der Waldfläche$", r"≈ \1 % of the forest area"),
    (r"^≈ (.+) m ü\. A\.$", r"≈ \1 m a.s.l."),
    (r"^Vorrat in Stämmen &gt; (\d+) cm$", r"Growing stock in stems &gt; \1 cm"),
    (r"^Anteil Stämme &gt; (\d+) cm$", r"Share of stems &gt; \1 cm"),
    (r"^Oberhöhe h(\d+)$", r"Top height h\1"),
    (r"^\+(\S+) % \((\S+) Mio Stämme\)$", r"+\1 % (\2 million stems)"),
    (r"^BFW – Österr\. Waldinventur (.+)$", r"BFW – Austrian National Forest Inventory \1"),
]
BIRDS = {"Neuntöter": "Red-backed shrike", "Dorngrasmücke": "Common whitethroat",
         "Goldammer": "Yellowhammer", "Fledermaus-Leitlinie": "Bat commuting route",
         "Wildbienen-Saum": "Wild-bee margin"}
_PAT = [(re.compile(p), r) for p, r in PATTERNS]
TAGS = {"RGB-Panorama": "RGB panorama", "Video-Rundgang": "Video tour",
        "LiDAR-Punktwolke": "LiDAR point cloud", "RGB-Bildanalyse": "RGB image analysis",
        "Semantik-Ground-Truth": "Semantic ground truth", "Kronenanalyse (LAI)": "Canopy analysis (LAI)",
        "Wachstumsprognose": "Growth projection", "Arteignung": "Species suitability",
        "Inventur-Marker": "Inventory markers"}


def tr(s):
    if s in EXACT:
        return EXACT[s]
    for p, r in _PAT:
        m = p.match(s)
        if not m:
            continue
        if r is not None:
            return p.sub(r, s)
        g = m.groups()
        if g[0] in BIRDS:
            return f"{BIRDS[g[0]]} ({g[1]})"
        if g[0] in SPECIES:
            return f"{SPECIES[g[0]]} {g[1]}"
        if s.startswith("Detektor 3DFin"):
            out = ("Detector 3DFin; reference = manually segmented trees in the test area "
                   "≥ 10 cm DBH (without measurable DBH: ≥ 10 m height).")
            return out + (f" Single-tree segmentation: mean IoU {g[0]}." if g[0] else "")
    return s


def _walk(o):
    if isinstance(o, dict):
        return {k: (v if k in SKIP_KEYS else _walk(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [_walk(v) for v in o]
    if isinstance(o, str):
        return tr(o)
    return o


def overlay_for(sid, s):
    if sid in OVERLAY:
        return OVERLAY[sid]
    m = re.match(r"barberini-(\d+)$", sid)
    if m:
        n = int(m.group(1))
        k = re.search(r"(?:Kugelpanorama|spherical panorama) (\d+)", s.get("description", ""))
        b = OVERLAY["_barberini"]
        return {"title": b["title"].format(n=n),
                "description": b["description"].format(n=n, k=k.group(1) if k else "")}
    return None


def translate_scene(s):
    """Szene (dict) -> englische Fassung. Titel/Beschreibung aus der Overlay-Datei."""
    ov = overlay_for(s.get("id", ""), s)
    out = _walk(s)
    if ov:
        out["title"], out["description"] = ov["title"], ov["description"]
    pc = out.get("pointcloud") or {}
    if pc.get("coloring_labels"):
        pc["coloring_labels"] = {k: tr(v) for k, v in pc["coloring_labels"].items()}
    return out


def main():
    docs = HERE.parents[1] / "docs" / "data"
    n = 0
    for f in sorted(docs.glob("scene-*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        f.write_text(json.dumps(translate_scene(s), ensure_ascii=False), encoding="utf-8")
        n += 1
    lst = docs / "scenes.json"
    L = json.loads(lst.read_text(encoding="utf-8"))
    for e in L:
        e["datasets"] = [TAGS.get(t, tr(t)) for t in e.get("datasets") or []]
        ov = overlay_for(e["id"], e)
        if ov:
            e["title"], e["description"] = ov["title"], ov["description"]
    lst.write_text(json.dumps(L, ensure_ascii=False), encoding="utf-8")
    print(f"-> {n} Szenen + scenes.json auf Englisch")


if __name__ == "__main__":
    main()
