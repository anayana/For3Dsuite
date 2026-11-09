# Quellen für die Eignungskurven (Stand 08.11.2026)

Status 09.11.2026: Teilweise Volltext gelesen (markiert ✔). Zahlen erst nach Prüfung im
Volltext in `species_requirements.csv` übernehmen. PDFs liegen lokal in `lit/pdf/`
(nicht im Repo, Urheberrecht).

## Im Volltext belegt ✔
| Art | Kennwert | Wert | Quelle |
|---|---|---|---|
| Neuntöter | Nesthöhe bevorzugt | 0,8–1,6 m (n = 842 Nester) | Jakober & Stauber 1983, Ökol. Vögel 3: 223–247 ✔ |
| Neuntöter | Nester über 2,5 m | stärker gefährdet (χ² = 4,4, P < 0,05) | ebd. ✔ |
| Neuntöter | Strauchhöhe | über 2 m Verjüngung empfohlen; offene Flächen als Jagdraum Voraussetzung | ebd. ✔ |
| Bluthänfling | Nesthöhe | 0–2 m in dichten Dornhecken, Brombeere, Gebüsch | GWCT Artblatt (graue Literatur) ✔ |
| Heckenbraunelle | Deckung | erfolgreiche Nester mit mehr Deckung von oben und seitlich | Tuomenpuro 1991, Ornis Fennica ✔ (Waldhabitat, Finnland — nur bedingt übertragbar) |
| Haselmaus | Hecken | Besetzung 25–64 %, dichtere Hecken und Wald in der Nähe ↑, Lücken schließen; >50 % der Nester in Schlehe; keine Höhen-/Breitenschwelle angegeben | Ehlers 2012, Peckiana (nur Zusammenfassung PTES) ✔ |
| Waldpflanzen in Knicks | Breite der Strauchschicht | positiv, aber schwach (GLMM z = 1,70, p = 0,09); Strauchhöhe nicht im Modell; Nähe zu altem Wald und Alter des Knicks wichtiger | Litza & Diekmann 2019, J. Veg. Sci., doi:10.1111/jvs.12744 ✔ (30 Knicks, SO-Schleswig-Holstein) |

→ Folgerung für ALS: **Heckenbreite** (aus der Maske messbar) als eigener Kennwert aufnehmen.
Bisher steckt die Breite nur indirekt im Schmalheitstest.


## Graham, Gaulton, Gerard & Staley 2018 ✔ (Volltext gelesen 09.11.2026)
„The influence of hedgerow structural condition on wildlife habitat provision in farmed
landscapes“, Biological Conservation 220: 122–131. Systematische Übersicht, 64 Studien,
Stimmenzählung (Richtung des Effekts, keine Effektgrößen). Belege überwiegend UK und W-Frankreich.

Werte, die ALS messen kann:

| Thema | Befund | Primärquelle laut Graham |
|---|---|---|
| Mindestmaß „guter Zustand“ (UK) | Höhe ≥ 1 m, Breite ≥ 1,5 m, Querschnitt ≥ 3 m² | Defra 2007 |
| Lücken (UK-Förderprogramm) | < 10 % Lücken | Natural England 2016 |
| Kleinsäuger | meiden Hecken mit Lücken > 3 m; Rötelmausdichte sinkt mit Lückigkeit | Gelling et al. 2007 |
| Haselmaus | große, dichte, artenreiche Hecken; dichte Strauchschicht ↑; Höhe wichtig für Nestwahl | Bright & MacPherson 2002; Dondina et al. 2016; Wolton 2009a |
| Fledermäuse | Große Hufeisennase: Hecken mit Höhe und Breite > 2 m; meiden kurze, stark geschnittene Hecken | Duvergé & Jones 2003; Russ & Montgomery 2002 |
| Fledermäuse | Holzmasse wirkt stärker auf 1000-m-Skala als lokal; Nachlese-Arten (Myotis, Plecotus) auf 100–300 m | Lacoeuilhe et al. 2016 |
| Fledermäuse | stark schwankende Laubhöhe entlang der Linie negativ (Zwergfledermaus u. a.) | Froidevaux et al. 2016 |
| Heckenvögel (7 Spezialisten) | Heckenbraunelle, Dorngrasmücke, Klappergrasmücke, Bluthänfling, Stieglitz, Grünfink, Goldammer | Fuller et al. 2001 |
| hohe Hecken | Heckenbraunelle, Rotkehlchen, Singdrossel, Fitis, Klappergrasmücke | Green et al. 1994 |
| breite Hecken | Grünfink, Stieglitz, Zaunkönig, Rotkehlchen, Amsel | Green et al. 1994 |
| kurze Hecken | Bluthänfling, Goldammer bevorzugen oder tolerieren | Green et al. 1994 |
| Nestprädation | offene Neststandorte → mehr Verluste durch Rabenvögel; dichte Vegetation am Heckenfuß wichtig | Dunn et al. 2016; Hinsley & Bellamy 2000 |
| Igel | dichter Heckenfuß, Dornen, Verbindung | Hof & Bright 2010 |

Zusammenfassung (Tab. 2): Höhe, Breite, Holzmasse/Dichte und Verbindung/Lücken sind die am
häufigsten belegten Strukturgrößen; Breite durchweg positiv für Säuger, Fledermäuse, Vögel. Höhe
für Vögel überwiegend positiv, aber nicht für alle Arten. **Kein Heckenprofil passt für alle
Gruppen → Vielfalt der Heckenstruktur fördern.** Graham et al. stellen fest, dass viele dieser
Größen in Heckenkartierungen bisher nicht erfasst werden → genau die Lücke, die ALS schließen kann.

Folgen für unser Verfahren:
1. **Neue Kennwerte:** Breite (aus Maske), Querschnitt (Breite × Höhe), Lückenanteil und
   Lückenlänge entlang der Linie, Dichte am Heckenfuß (0–1,5 m).
2. **Fledermaus und Haselmaus** als Netzkennwerte: Lücken > 3 m (Kleinsäuger), Höhe/Breite > 2 m
   (Hufeisennase), Holzmasse im 100–300-m- bzw. 1000-m-Umkreis.
3. **Artenliste prüfen:** Klappergrasmücke (hohe Hecken) wäre ein guter Gegenpol zur
   Dorngrasmücke (niedrige Hecken).
4. Primärquellen für Zahlen: Gelling et al. 2007, Duvergé & Jones 2003, Lacoeuilhe et al. 2016,
   Dondina et al. 2016 — im Volltext prüfen.


## Batáry, Kovács-Hostyánszki, Fischer, Tscharntke & Holzschuh 2012 ✔ (Volltext gelesen 09.11.2026)
„Contrasting effect of isolation of hedges from forests on farmland vs. woodland birds“,
Community Ecology 13(2): 155–161, doi:10.1556/ComEc.13.2012.2.4. Raum Göttingen, 18 Abschnitte à
200 m (6 Waldränder, 6 an Wald angebundene Hecken, 6 isolierte Hecken ≥ 300 m vom Wald).

- Agrarvögel: mehr Arten und Individuen in Hecken als an Waldrändern; Waldvögel umgekehrt.
- **Breite und Höhe ohne signifikanten Effekt** auf Artenzahl und Häufigkeit. Einschränkung der
  Autoren: Die Höhe schwankte kaum; nur 18 Abschnitte, alle mit dichter Strauchschicht.
  Breite wirkte tendenziell auf Waldvögel (Barkow 2002: Breite wichtigste von 12 Variablen).
- **Lage zum Wald zählt:** Goldammer vor allem in isolierten Hecken; Amsel und Gartengrasmücke
  in an Wald angebundenen Hecken. Dorngrasmücke in beiden Heckentypen.
- Artengemeinschaft unterscheidet sich zwischen angebundenen und isolierten Hecken.

Folgen für unser Verfahren:
1. Neuer Kennwert **Abstand zum nächsten Wald** (aus derselben ALS-Kachel: große Gehölzflächen,
   die der Schmalheitstest als Waldblock aussortiert). Goldammer: Eignung steigt mit Abstand.
2. Breite/Höhe allein erklären die Artenzahl nicht zwingend → Lage im Netz gehört dazu.
   Spricht für den mehrskaligen Ansatz (Heckenstück + Umgebung).


## Chamberlain, Wilson & Fuller 1999 ✔ (Volltext gelesen 09.11.2026)
„A comparison of bird populations on organic and conventional farm systems in southern
Britain“, Biological Conservation 88: 307–320, doi:10.1016/S0006-3207(98)00124-4.
22 Hofpaare (ökologisch/konventionell), England und Wales, drei Brutzeiten.

- Thema ist die Bewirtschaftung, nicht die Heckenstruktur. Für uns nur zweierlei brauchbar:
- **Klassengrenze 2 m für Höhe und Breite** (Heckendichte > 2 m hoch und breit, ≤ 2 m usw.) —
  dieselbe Grenze wie bei Duvergé & Jones (Hufeisennase). → Als Klassengrenze in den Kennwerten
  übernehmen, damit Ergebnisse vergleichbar sind.
- Ökohöfe hatten mehr Hecken über 2 m Höhe und Breite (p < 0,05 in einzelnen Jahren) und mehr
  Vögel. Bluthänfling, Singdrossel, Goldammer mit Ökobewirtschaftung verbunden; Gimpel mit hohen,
  schmalen Hecken. Ursache (Struktur oder Nahrung) nicht trennbar.
- Keine artbezogenen Schwellenwerte für die Eignungskurven.


## Stoate & Szczur 2001 ✔ (Volltext gelesen 09.11.2026)
„Whitethroat Sylvia communis and Yellowhammer Emberiza citrinella nesting success and breeding
distribution in relation to field boundary vegetation“, Bird Study 48: 229–235,
doi:10.1080/00063650109461222. Leicestershire (UK), 93 Hecken à 100 m (Reviere 1998),
Nester 1995–98 (151 Dorngrasmücke, 276 Goldammer).

Mittelwerte (± SE) an Hecken mit/ohne Revier (Tab. 1), logistische Regression (Tab. 2):

| | Heckenhöhe | Krautsaum-Breite (beide Seiten) | Grabentiefe |
|---|---|---|---|
| Dorngrasmücke ja | **1,83 ± 0,12 m** | **3,17 ± 0,40 m** | – |
| Dorngrasmücke nein | 2,83 ± 0,16 m | 1,23 ± 0,13 m | – |
| Goldammer ja | – | **2,63 ± 0,30 m** | **1,09 ± 0,12 m** |
| Goldammer nein | – | 1,12 ± 0,14 m | 0,26 ± 0,06 m |

Koeffizienten: Dorngrasmücke Heckenhöhe −0,261 (P < 0,01), Krautsaum +0,368 (P < 0,001);
Goldammer Krautsaum +0,221 (P < 0,01), Grabentiefe +0,294 (P < 0,001).

- **95 % der Dorngrasmücken-Nester im Krautsaum**, nicht im Gebüsch.
- Goldammer: 49 % der Nester im Krautsaum; Nester in der Hecke im Mittel 0,78 m hoch, im
  Krautsaum 0,10 m. Nester in der Hecke häufiger ausgeraubt.
- Empfehlung der Autoren: niedrige Hecken und 2 m breite ungemähte Krautstreifen.

Folgen für unser Verfahren:
1. **Dorngrasmücke:** Heckenhöhe als fallende Kurve (gut bei ≤ ~2 m, schlecht ab ~3 m);
   entscheidend ist der **Krautsaum** neben der Hecke (Vegetation ~0,2–1 m, ≥ 2–3 m breit).
2. **Erklärt die schwache Rotterdam-Validierung** (AUC 0,58, nur 38 % der Funde an Hecken): Die
   Art brütet im Krautsaum, den unsere Heckenmaske (1–8 m) gar nicht erfasst.
3. **Goldammer:** Krautsaum und **Graben** — Gräben sind im ALS-Geländemodell messbar (Senke
   neben der Hecke). Neuer Kennwert.
4. Vorbehalt: AHN wird überwiegend ohne Laub geflogen; ein niedriger Krautsaum ist dann schwer
   von Boden zu trennen. Prüfen, wie gut 0,2–1 m in AHN4 erkannt wird.


## Verboom & Huitema 1997 ✔ (Volltext gelesen 09.11.2026)
„The importance of linear landscape elements for the pipistrelle Pipistrellus pipistrellus and
the serotine bat Eptesicus serotinus“, Landscape Ecology 12: 117–125. Agrarlandschaft in den
Niederlanden, 15 Quadrate à 1 × 1 km, 87 Punkte an Linienelementen, 13 im Offenland.

- **Zwergfledermaus fast nur an Linienelementen:** anwesend an 68 % der Punkte an Hecken/
  Baumreihen, nur 9 % im Offenland (P < 0,001).
- **Höhe zählt:** Aktivität steigt mit der Höhe des Elements (R² = 12,5 %, P = 0,005).
  **An Elementen unter 6 m Höhe keine Zwergfledermaus** (nur n = 6 solcher Punkte). Untersuchte
  Elemente 3–25 m hoch.
- **Lücken sind kein starkes Hindernis:** Zwergfledermäuse auch an isolierten Fragmenten mit
  110–150 m Abstand; Querungen bis 200 m beobachtet. Kein Isolationseffekt.
- **Breitflügelfledermaus:** gleich oft im Offenland wie an Elementen, aber Aktivität sinkt mit dem
  Abstand zum Element (25–265 m; R² = 26 %, P = 0,01) und steigt überproportional mit der
  Dichte der Linienelemente in der Landschaft (Quadrat + 8 Nachbarn: R² = 61,5 %).

**Korrektur meiner früheren Annahme:** Ich hatte gesagt, schon wenige Meter Lücke könnten eine
Flugroute unterbrechen. Für Zwerg- und Breitflügelfledermaus stimmt das laut dieser Studie
nicht (Lücken bis 110–150 m überbrückt). Lücken > 3 m zählen für Kleinsäuger (Gelling et al. 2007,
nach Graham et al. 2018); für Langohr/Myotis noch offen.

Folgen für unser Verfahren:
1. **Fledermaus-Kennwert muss Baumreihen einschließen.** Unsere Heckenmaske (1–8 m) schneidet
   hohe Elemente ab; Zwergfledermäuse nutzen Elemente ab etwa 6 m. → Eigene Maske für
   Linienelemente bis 25 m.
2. Kennwerte: Höhe des Elements, Dichte der Linienelemente je km² (Umkreis ~1,5 km, also
   Quadrat + Nachbarn), Abstand zum nächsten Element. Lückenlänge für Fledermäuse nachrangig.

## Fehlt noch — Volltext nötig (nicht frei zugänglich)
1. ~~Graham et al. 2018~~ ✔ erledigt (siehe oben), Biological Conservation 220: 122–131,
   doi:10.1016/j.biocon.2018.02.017 — systematische Übersicht: Höhe, Breite, Holzmasse, Lücken je
   Tiergruppe. **Wichtigste Quelle.**
2. **Hinsley & Bellamy 2000**: „The influence of hedge structure, management and landscape context on the value of hedgerows to birds: a review“, J. Environ. Manage. 60: 33–49, doi:10.1006/jema.2000.0360 —
   Heckenstruktur und Vögel, Übersicht.
3. **Green, Osborne & Sears 1994**: „The distribution of passerine birds in hedgerows during the breeding season in relation to characteristics of the hedgerow and adjacent farmland“ (Titel aus dem Gedächtnis), J. Appl. Ecol. 31: 677–692 — Heckenhöhe/-breite je Art.
4. ~~Stoate & Szczur 2001~~ ✔ erledigt (siehe oben).
5. ~~Verboom & Huitema 1997~~ ✔ erledigt (siehe oben), Landscape Ecology 12: 117–125 (Fledermäuse).
6. **Boughey, Lake, Haysom & Dolman 2011**: „Improving the biodiversity benefits of hedgerows: How physical characteristics and the proximity of foraging habitat affect the use of linear features by bats“ (Titel aus dem Gedächtnis).
7. Steinkauz: Génot & Van Nieuwenhuyse 2002 (Brutplatzwahl) bzw. Van Nieuwenhuyse et al. 2008,
   „The Little Owl“ (Buch).

## Neuntöter (Lanius collurio)
Nesthöhe in Dornsträuchern ~0,8–1,7 m, Sträucher 1,7–4 m, offener Boden zur Jagd nötig.
- Nesthöhe 80–160 cm bevorzugt, dornige Unterlage, freie Jagdflächen (Baden-Württemberg):
  Ökologie der Vögel 3, 223–247. https://www.zobodat.at/pdf/Oekologie-Voegel_3_0223-0247.pdf
- Nest im Mittel 1,39 m, Sträucher 1,7–4 m (Marche, Italien): Avocetta 35(1).
  https://avocetta.org/articles/vol-35-1-e-2-kc-breeding-habitat-and-nesting-site-of-the-red-backed-shrikeilanius-collurioi-in-farmland-of-the-marche-region-italy
- Nest im Mittel 113 cm (0–250 cm), steigt mit der Strauchhöhe (Norwegen, Kahlschläge):
  Ornis Norvegica. https://boap.uib.no/index.php/ornis/article/view/242

## Dorngrasmücke, Bluthänfling, Goldammer, Heckenbraunelle
- Green, Osborne & Sears (1994), J. Appl. Ecol. 31: Brutvögel in Hecken auf 46 Höfen in
  England. Dorngrasmücke, Bluthänfling, Goldammer: niedrige Hecken mit wenigen Bäumen.
  Heckenbraunelle: hohe Hecken mit wenigen Bäumen. → Volltext für Schwellen (Höhe, Breite).
- Stoate & Szczur (2001): Heckenhöhe wirkt negativ auf brütende Dorngrasmücken; krautiger
  Saum positiv für Dorngrasmücke und Goldammer.
  https://gwct.org.uk/research/scientific-publications/2000-09/2001/stoate2001a/

## Haselmaus (Muscardinus avellanarius)
- Ehlers (2012), Peckiana: Hecken in Norddeutschland. Besetzung 25–64 %, dichte Hecken und
  waldreiche Landschaft erhöhen sie, > 12 Gehölzarten positiv (Gehölzarten sieht ALS nicht).
  https://ptes.org/wp-content/uploads/2014/06/Ehlers-2012-The-importance-of-hedgerows-for-hazel-dormice-in-Northern-Germany-Peckiana.pdf
- LiDAR + Telemetrie (UK, Wald, nicht Hecke): Bevorzugung 5–10 m hoher Vegetation.
  https://ore.exeter.ac.uk/repository/handle/10871/33405

## Steinkauz (Athene noctua)
- offen: Literatur zu Kopfbäumen/Überhältern als Brutplatz in Hecken suchen.

## Fledermäuse (Netz-Kennwert)
- Verboom & Huitema (1997), Landscape Ecology 12: lineare Landschaftselemente für Zwerg- und
  Breitflügelfledermaus. — Volltext prüfen
- Boughey et al. (2011), Biological Conservation: Fledermausaktivität entlang von Hecken. — Volltext prüfen
