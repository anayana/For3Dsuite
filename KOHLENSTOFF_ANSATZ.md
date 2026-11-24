# Kohlenstoff im Nationalpark Hainich: Ansatz

Stand 24.11.2026. Ergänzt `scripts/KOHLENSTOFF_BEISPIEL.md` (Rechenbeispiel) und
`scripts/allometrie_stichprobe_sim.py` (Stichprobenumfang für gefällte Buchen).

## Ziel
Kohlenstoffvorrat und -bilanz des ganzen Nationalparks für alle Speicher, als Karte und Parksumme
mit Unsicherheit, für 2000 bis heute. Abgeglichen mit dem Messturm. Danach Projektion.

## Was die Forschung sagt (Stand 2026)
**Hainich**
- **Gesamtvorrat:** ca. 337 t C/ha (Knohl et al., CarboEurope, ca. 2003).
  - Bäume oberirdisch 178 t C/ha
  - Wurzeln 34 t C/ha
  - Totholz 13,5 t C/ha
  - Mineralboden 110 t C/ha

  Daraus folgt eine Nettoprimärproduktion von ca. 9 t C/ha/Jahr.
- **Messturm DE-Hai** (seit 2000):
  - Im 15-jährigen Mittel bis 2017 eine Senke von ca. 535 g C/m²/Jahr.
  - Nach der Dürre 2018 sank sie auf 333–395 g C/m²/Jahr (2019–2021), 2019 um ca. 40 %.
  - Der Wald bleibt eine Senke.
  - Der Rückgang 2018–2022 kommt vor allem vom schwächeren Wachstum alter, starker Bäume, meist Eschen. Unterdrückte, vitale Buchen wachsen eher besser. Diese Angaben stammen aus EGU-Tagungsbeiträgen 2020–2026.
- **Boden:** Bei der Wiederbeprobung 2004/2009 hat der Kohlenstoff im Boden zugenommen (Schrumpf et al. 2014, PLOS ONE).
- **Feinwurzeln:** 440–480 g/m² in 0–40 cm Tiefe (Meinen, Hertel & Leuschner 2009, Oecologia).
- **Kohlenstoffspeicher im alten Buchenwald:** Mund 2004 (Dissertation Göttingen). Schönstedter Holz: ca. 153 t C/ha im Holz ober- und unterirdisch.
- **Inventuren:**
  - Permanente Stichprobeninventur 2000, 2010, 2020 (NW-FVA): im LIFE+-PROGNOSES-Datensatz 393 Probekreise zu je 500 m², BHD ab 7 cm, liegendes Totholz ab 20 cm. Die Baumdaten sind auf Zenodo bis 31.12.2030 gesperrt, also intern über NW-FVA bzw. Nationalparkverwaltung nutzen.
  - 28-ha-Dauerfläche mit Aufnahmen 1999, 2007, 2013, 2023, seit 1965 ungenutzt, offen unter CC BY 4.0 (Schorn, Bauhus, Wirth & Rüger 2026, Scientific Data, doi:10.1038/s41597-026-08215-x).

**Methoden**
- **TLS gegen gefällte Bäume:**
  - Demol et al. 2022 (MEE): 10 Studien, Übereinstimmung 98 %, schwächer bei Bäumen unter 1 t und bei Nadelholz.
  - Demol et al. 2021 (Annals of Botany): 65 Bäume, darunter Buche und Esche. Der Stamm ist zuverlässig, das Gesamtvolumen aus dem Roh-QSM liegt 21 % zu hoch.
  - Bei Esche entstehen 80 % der Überschätzung in Ästen unter 5 cm (Demol et al. 2022, Silva Fennica). Bessere Registrierung halbiert den Fehler.
- **Allometrie gegen TLS:** In Wytham Woods ergab unbelaubtes TLS 77 % mehr Biomasse als die Allometrie (Calders et al. 2022).
- **Buchen-Allometrien:**
  - Wutzler et al. 2008: 443 Bäume aus 13 Studien, alle Kompartimente. Die Unterschiede zwischen Studien sind groß.
  - Alter erklärt einen großen Teil dieser Unterschiede (Genet et al. 2011).
  - Thünen-Funktionen der Treibhausgasberichterstattung: Riedel & Kändler 2017, Forstarchiv.
- **Stichprobenumfang:**
  - Für eine neue artspezifische Funktion mehr als 50 Bäume (Roxburgh et al. 2015, laut zitierenden Arbeiten).
  - Mindestens 30 Bäume über die ganze Größenspanne (FAO-Handbuch, Picard et al. 2012).
  - Zur Prüfung einer vorhandenen Funktion mehr als 5 Bäume je Klasse.
  - Mit Literatur als Vorinformation (bayessch) reichen deutlich weniger, z. B. 25 Bäume (Zapata-Cuartas et al. 2012).
- **Wurzeln:**
  - Wurzel/Spross bei Buche ca. 0,23 (Le Goff & Ottorini 2001), über die Baumgröße fast konstant (Bolte et al. 2004).
  - Hainich: 34/178 = 0,19.
  - Wurzelfunktionen der Treibhausgasberichterstattung kommen vom Thünen-Institut.
- **Dichte:** Sie ändert sich innerhalb des Stamms mit der Höhe (U-förmig). Astholz hat eine andere Dichte als Stammholz.
- **Totholz:** Die Dichte fällt stark mit der Zersetzung. Der C-Gehalt bleibt bei ca. 44–48 %.
- **Turm gegen Inventur:** Beide Wege stimmen bei Photosynthese und Atmung überein, bei der Nettobilanz weniger. Die Biometrie unterschätzt eher die Nettoprimärproduktion (Campioli et al. 2016, Nat. Commun.).
- **Box-Dimension (Seidel 2018):** Sie hängt bei Buche mit dem Zuwachs zusammen. Eine Biomassefunktion daraus gibt es nicht, und der Wert hängt von der Lage im Koordinatensystem ab (Trees 2026). Sie bleibt deshalb ein optionaler Prädiktor für den Astanteil.

**Folgerung:** Zufallsfehler mitteln sich über viele Bäume und Probekreise weg, der systematische
Fehler der Allometrie nicht. Er ist der größte Hebel. Deshalb braucht es eine lokale Kalibrierung.

## Ansatz in fünf Bausteinen

### 1. Lokale Allometrie: gefällte Buchen plus TLS
- 20–30 gefällte Buchen aus angrenzenden Revieren von ThüringenForst werden vor der Fällung unbelaubt gescannt und danach vermessen und gewogen (Studienarbeit, siehe unten).
- Daraus entstehen zwei Ergebnisse:
  - **(a)** eine lokale Allometrie je Kompartiment (Stamm, Äste, Rinde) mit Literatur als Vorinformation
  - **(b)** eine Kalibrierung des TLS-QSM gegen die Waage, vor allem für den Astanteil
- **Übertrag in den Nationalpark:** Bäume im Wirtschaftswald haben andere Kronen als Bäume im Nationalpark. Deshalb wird die Allometrie nicht einfach übernommen. Stattdessen wird das kalibrierte TLS im Nationalpark auf unbelaubte Probebäume angewendet. So entsteht ein Astanteil für den Nationalpark, ohne dort zu fällen.

### 2. Vom Baum zum Probekreis
- Je Inventur (2000, 2010, 2020; 28-ha-Fläche 1999–2023) und je Baum:
  - oberirdische Biomasse aus BHD und Höhe über die lokale Allometrie
  - Wurzeln über die Wurzelfunktion
  - Kohlenstoff mit dem Faktor 0,48
- **Totholz:** Volumen × Dichte je Zersetzungsstufe (an Bohrkernen lokal gemessen) × C-Gehalt.
- Bäume behalten ihre ID über alle Aufnahmen. Damit trennt die Bilanz Zuwachs, Absterben und Einwuchs.

### 3. Vom Probekreis zur Fläche
- ALS-Metriken je Probekreis (Höhenperzentile, Kronendeckung, Volumen) gegen die Biomasse der Probekreise. Das Modell ist nichtlinear und heteroskedastisch.
- Daraus entsteht eine 20-m-Karte.
- Ein modellgestützter Schätzer (Probekreise plus ALS) liefert eine unverzerrte Parksumme mit Konfidenzintervall, auch für Teilflächen.
- Für Buche sind je Probefläche ca. 13 % Fehler aus ALS berichtet. Die Parksumme ist deutlich genauer.
- Laut TLBG sind die Thüringer ALS-Daten offen über das Geoportal zu haben. Ob die Punktwolken für die Befliegungsjahre verfügbar sind, ist noch zu prüfen.

### 4. Zeitreihe und Abgleich mit dem Turm
| Quelle | Auflösung | Liefert |
|---|---|---|
| Inventuren 2000/2010/2020, 28 ha 1999–2023 | Jahrzehnt | Vorratsänderung je Speicher |
| Jahrringe (Scheiben der gefällten Bäume, Bohrkerne) | Jahr, rückwärts > 30 Jahre | Stammzuwachs, Dürrejahre 2003 und 2018–2020 |
| Dendrometer, Saftfluss | Stunde bis Tag | Zuwachs im Jahresverlauf, Trockenstress |
| Turm DE-Hai | halbstündlich, seit 2000 | Netto-Austausch, Photosynthese, Atmung |
| Streufallen, Bodenatmung | Monat | Streufall, Abgabe aus dem Boden |
| ALS-Befliegungen | je Befliegung | Höhenänderung, Lücken |
| Landsat (ab 1984), Sentinel-2 (ab 2015) | Tage bis Jahre | Störungen, Vitalität, Eschentriebsterben |

**Abgleich:** Die Änderung von Bäumen, Totholz und Boden zusammen muss ungefähr dem
Turm-Nettoaustausch entsprechen. Abweichungen zeigen Fehler in der Allometrie oder fehlende
Speicher. Beide Wege werden in einem bayesschen Zustandsmodell zusammengeführt, ohne einen der
beiden zur Übereinstimmung zu zwingen.

### 5. Projektion
1. Mit 2000–2010 kalibrieren, 2010–2023 einschließlich der Dürre als Test vorhersagen.
2. Erst wenn der Test trifft, nach vorn rechnen.

Modelle:
- **TreeGrOSS** (in For3Dsuite), mit den Inventuren neu kalibriert, vor allem das Absterben.
- **3-PGmix** mit bayesscher Kalibrierung für Klimaszenarien.

Szenarien: Klima und Eschenausfall (Esche ca. 25 % des Bestands).

### Speicher im Überblick
| Speicher | Hainich (Knohl) | Methode | Messbedarf |
|---|---|---|---|
| Bäume oberirdisch | 178 t C/ha | lokale Allometrie bzw. TLS × Dichte × 0,48 | gefällte Buchen, TLS unbelaubt |
| Wurzeln | 34 t C/ha | Wurzelfunktion, an 3–4 gezogenen Stubben prüfen | eigene Arbeit oder mit dem Thünen-Institut |
| Totholz | 13,5 t C/ha | Volumen × Dichte je Zersetzungsstufe | Bohrkerne je Stufe |
| Mineralboden | 110 t C/ha | Wiederbeprobung alle 10 Jahre | an Schrumpf et al. anschließen |
| Streu, Feinwurzeln | klein, aber schneller Umsatz | Streufallen, Bohrungen | Daten am Turm vorhanden |

**Unsicherheit:** Monte Carlo über Messung, Allometrie (Parameter und Reststreuung), Dichte,
ALS-Modell und Stichprobe.

## Studienarbeit: gefällte Buchen für eine Standort-Allometrie

### Wie viele Buchen?
Simulation (`scripts/allometrie_stichprobe_sim.py`):
- **Bestand:** synthetischer alter Buchenbestand mit 329 Bäumen/ha. 82 % der Biomasse stecken in Bäumen ab 50 cm BHD.
- **Annahme:** Der Standort weicht von der Literatur um ±20 % im Niveau und ±0,1 im Exponenten ab.
- **Gemessen:** Fehler der Bestandessumme (RMSE).
- **Spannen:** gelten für eine Reststreuung je Baum von 15–25 %, Schätzung mit Literatur als Vorinformation.

| Gefällte Buchen | nur Literatur | zufällig ausgewählt | nach BHD-Klassen geschichtet |
|---|---|---|---|
| 5 | 21 % | 10–13 % | 7–11 % |
| 10 | 21 % | 7–10 % | 5–8 % |
| 20 | 21 % | 5–8 % | 3,5–6 % |
| 30 | 21 % | 4–7 % | 3–5 % |
| 50 | 21 % | 3–5 % | 2,5–4 % |

**Ergebnis:** Die Schichtung mit übervertretenen starken Bäumen ist wichtiger als die Anzahl.
Ab ca. 20–25 Bäumen flacht der Gewinn ab. **Empfehlung: 24 Buchen, also 8 BHD-Klassen von 10 bis
über 90 cm mit je 3 Bäumen.** Wenn möglich kommen 4–6 Eschen aus Fällungen zur Verkehrssicherung
dazu.

### Ablauf je Baum
1. **Vor der Fällung, stehend und unbelaubt (November bis März):**
   - Position, BHD (Maßband und zwei Kluppungen über Kreuz), Höhe, Kronenansatz, 8 Kronenradien
   - soziale Stellung, Abstand zu den Nachbarn
   - TLS-Scan von 4–6 Standpunkten bei Windstille
2. **Fällung durch Profis:**
   - Die Fallrichtung so wählen, dass die Krone frei liegt.
   - Die Stockhöhe notieren.
   - Abgebrochene Kronenteile einsammeln.
3. **Stamm:**
   - echte Länge messen
   - Durchmesser über Kreuz alle 1 m bis 7 cm Zopf, Rindenstärke messen. Das ergibt das Sektionsvolumen mit und ohne Rinde.
   - Scheiben am Stammfuß, an Zopf und Kronenansatz. Im Wertholz stattdessen Bohrkerne in mehreren Höhen.
4. **Krone:**
   - Äste nach Durchmesserklassen trennen: über 7 cm, 3–7 cm, 1–3 cm, unter 1 cm.
   - Bei großen Kronen alle Äste erster Ordnung frisch wiegen (Kranwaage am Rückezug) und 3–5 davon fein sortieren. Hochrechnen über ein Verhältnis oder die Zufallsast-Stichprobe.
5. **Labor:**
   - Teilproben je Kompartiment luftdicht verpacken.
   - Frisch- und Trockengewicht bei 105 °C bis zur Gewichtskonstanz bestimmen.
   - Dichte als Trockenmasse durch Frischvolumen (Wasserverdrängung).
   - C-Gehalt optional an einer Teilprobe messen.
6. **Bonus:** Die Jahrringe der Stammfußscheibe liefern Alter und Zuwachsgeschichte für die Rückrechnung.

Aufwand: Ein starker Baum braucht ca. 1 Feldtag mit 3–4 Personen und Maschine, dazu ca. 1 Labortag.
24 Bäume ergeben ca. 25–30 Feldtage in einer Fällsaison.

### Worauf achten
- **Starke Bäume übervertreten**, denn sie tragen die Biomasse und dort extrapolieren die Literaturfunktionen.
- **Ähnlicher Standort** wie im Hainich: Muschelkalk-Plateau, Höhenlage, Wasserhaushalt.
- **Konkurrenz aufnehmen**, weil Kronen im Wirtschaftswald anders sind. Für den Übertrag in den Nationalpark dient das TLS (Baustein 1).
- **Winterfällung:** Sie passt zur Holzernte und zum unbelaubten Scan. Die Blattmasse kommt aus den Streufallen.
- **Wertholz nicht beschädigen:** Scheiben nur aus Stammfuß-Abschnitt, Zopf und Kronenholz, sonst Bohrkerne. Das vorher mit Revier und Holzkäufer absprechen.
- **Sofort frisch wiegen**, denn das Holz trocknet aus. Proben luftdicht verpacken.
- **Dichte getrennt** für Stamm, Äste und Rinde und in mehreren Höhen messen.
- **Fäule und Höhlen** an jeder Schnittfläche fotografieren und ihre Fläche messen. Das ergibt einen Abzug für hohle Altbäume je BHD-Klasse.
- **Sicherheit:** Fällung nur durch Profis, Studierende bleiben außerhalb des Gefahrenbereichs, Wiegen mit Kran.
- **Auswertung:**
  - Kompartimente additiv anpassen, so dass die Summe der Teile die Gesamtmasse ergibt (NSUR).
  - Heteroskedastische Varianz berücksichtigen, Literatur als Vorinformation nutzen.
  - Die Daten offen auf Zenodo ablegen.

### Bachelor oder Master?
- **Masterarbeit**: 24 Buchen, alle Kompartimente, TLS vor der Fällung, lokale Allometrie und
  Kalibrierung des TLS-QSM. Das ist publizierbar.
- **Bachelor** nur als Teilstück, z. B. 8–10 Buchen zur Prüfung von Wutzler- und Thünen-Funktionen
  am Standort, oder Dichte und Fäule aus den Scheiben, oder Jahrringe.
- **Wurzeln** (3–4 Stubben mit Bagger ziehen und wiegen) als eigene Arbeit oder mit dem
  Thünen-Institut.

### Partner
- **ThüringenForst:** Bäume, Fällung, Maschine
- **NW-FVA:** Inventurdaten
- **Uni Göttingen:** TLS, Betreuung. Studierende von Uni Göttingen, HAWK Göttingen, FH Erfurt.
- **MPI für Biogeochemie Jena:** Turm DE-Hai
- **Thünen-Institut:** Wurzeln, Funktionen der Treibhausgasberichterstattung

Ausrüstung:
- Kranwaage (bis 2–5 t), Plattform- und Hängewaage, Feinwaage
- Trockenschrank (Uni)
- Zuwachsbohrer, Maßband, Kluppe, Rindenmesser
- GNSS, TLS
