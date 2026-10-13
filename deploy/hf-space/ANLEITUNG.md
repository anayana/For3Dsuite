# Öffentliches Studio auf Hugging Face (einmalig einrichten, geht vom Handy)

Danach können Nutzer unter einem festen Link eigene 360°-Aufnahmen hochladen,
verarbeiten lassen und Marker setzen. GitHub aktualisiert den Space bei jeder
Änderung am Code automatisch (`.github/workflows/deploy-hf-space.yml`).

## 1. Space anlegen (Hugging Face)
1. https://huggingface.co/new-space öffnen
2. **Space name:** `for3dsuite`
3. **License:** gpl-3.0
4. **SDK:** Docker → *Blank*
5. **Hardware:** CPU basic (kostenlos)
6. **Public** lassen → *Create Space*

## 2. Passwort für das Studio setzen (Hugging Face)
Im Space: *Settings → Variables and secrets → New secret*
- Name: `STUDIO_PASSWORD`, Wert: ein Passwort, das du deinen Nutzern gibst
- Benutzername beim Login ist `admin` (änderbar mit dem Secret `STUDIO_USER`)

Ohne Passwort kann jeder Besucher hochladen und löschen. Für eine öffentliche
Demo deshalb immer ein Passwort setzen.

## 3. Token anlegen (Hugging Face)
https://huggingface.co/settings/tokens → *Create new token* → Typ **Write** → kopieren

## 4. Token bei GitHub hinterlegen
https://github.com/anayana/For3Dsuite/settings/secrets/actions → *New repository secret*
- Name: `HF_TOKEN`, Wert: der kopierte Token

Heißt dein Space anders als `anayananaya/for3dsuite`, zusätzlich unter
*Variables* eine Variable `HF_SPACE` mit `nutzername/spacename` anlegen.

## 5. Starten
https://github.com/anayana/For3Dsuite/actions/workflows/deploy-hf-space.yml →
*Run workflow*. Der Space baut danach einige Minuten.

**Links für Nutzer**
- Studio: `https://anayananaya-for3dsuite.hf.space/admin/`
- Galerie: `https://anayananaya-for3dsuite.hf.space/`

## Grenzen der kostenlosen Stufe
- Der Space schläft nach etwa 48 h ohne Besuch ein; der nächste Aufruf weckt ihn
  (rund eine Minute).
- Speicher ist flüchtig: Nach einem Neustart sind hochgeladene Szenen weg.
  Dauerhaft wird es mit *Settings → Persistent storage* (kostenpflichtig, kleinste
  Stufe reicht) oder mit eigenem Server (`platform/README.md`).
- Alle Nutzer teilen sich eine Galerie und sehen gegenseitig ihre Szenen.
