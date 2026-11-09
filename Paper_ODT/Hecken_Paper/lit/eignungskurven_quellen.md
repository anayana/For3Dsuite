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

## Fehlt noch — Volltext nötig (nicht frei zugänglich)
1. ~~Graham et al. 2018~~ ✔ erledigt (siehe oben), Biological Conservation 220: 122–131,
   doi:10.1016/j.biocon.2018.02.017 — systematische Übersicht: Höhe, Breite, Holzmasse, Lücken je
   Tiergruppe. **Wichtigste Quelle.**
2. **Hinsley & Bellamy 2000**: „The influence of hedge structure, management and landscape context on the value of hedgerows to birds: a review“, J. Environ. Manage. 60: 33–49, doi:10.1006/jema.2000.0360 —
   Heckenstruktur und Vögel, Übersicht.
3. **Green, Osborne & Sears 1994**: „The distribution of passerine birds in hedgerows during the breeding season in relation to characteristics of the hedgerow and adjacent farmland“ (Titel aus dem Gedächtnis), J. Appl. Ecol. 31: 677–692 — Heckenhöhe/-breite je Art.
4. **Stoate & Szczur 2001**: „Whitethroat Sylvia communis and Yellowhammer Emberiza citrinella nesting success and breeding distribution in relation to field boundary vegetation“ (Titel aus dem Gedächtnis).
5. **Verboom & Huitema 1997**: „The importance of linear landscape elements for the pipistrelle Pipistrellus pipistrellus and the serotine bat Eptesicus serotinus“ (Titel aus dem Gedächtnis), Landscape Ecology 12: 117–125 (Fledermäuse).
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
