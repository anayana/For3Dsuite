<#
  syns_download.ps1 — SYNS-Szenen mit Resume herunterladen (Windows PowerShell)

  ------------------------------------------------------------------
  EINMALIG: Cookie besorgen
  ------------------------------------------------------------------
  1. Bei https://syns.soton.ac.uk einloggen.
  2. Szenenseite oeffnen (Browse by Scene ID -> Scene 19).
  3. F12 -> Reiter "Netzwerk"/"Network".
  4. Einen Download-Link anklicken, Download sofort abbrechen.
  5. In der Netzwerkliste den obersten Eintrag rechtsklicken
     -> "Kopieren" -> "Als cURL kopieren" (Copy as cURL).
  6. Im kopierten Text die Zeile  -H "cookie: ..."  suchen und NUR den
     Teil hinter "cookie: " unten bei $Cookie einsetzen.
     Der sieht ungefaehr so aus:
        wordpress_logged_in_abc123=benutzer%7C1234...; wp-settings-1=...

  ------------------------------------------------------------------
  STARTEN
  ------------------------------------------------------------------
     cd C:\Users\A\Desktop\R\360Pano3D
     powershell -ExecutionPolicy Bypass -File .\scripts\syns_download.ps1

  Bricht ein Download ab: Skript einfach nochmal starten. Dank "-C -"
  setzt curl an der abgebrochenen Stelle fort, statt neu zu beginnen.
#>

# ==================================================================
# HIER EINTRAGEN
# ==================================================================
$Cookie = "HIER_DEN_COOKIE_STRING_EINFUEGEN"

# Welche Szenen? 19 = Bolderwood Sommer, 45 = Bolderwood Winter
$Scenes = @(19, 45)

# Zielordner (relativ zum Repo-Wurzelverzeichnis)
$DestRoot = "data\SYNS-panorama\SYNS-panorama"
# ==================================================================


$ErrorActionPreference = "Stop"
$Base = "https://syns.soton.ac.uk/wp-json/syns-api/record"

# Repo-Wurzel = Elternordner von \scripts
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($Cookie -eq "HIER_DEN_COOKIE_STRING_EINFUEGEN" -or [string]::IsNullOrWhiteSpace($Cookie)) {
    Write-Host ""
    Write-Host "  ABBRUCH: Kein Cookie eingetragen." -ForegroundColor Red
    Write-Host "  Oeffne scripts\syns_download.ps1 und trage bei `$Cookie den Wert ein."
    Write-Host "  Anleitung steht oben in der Datei."
    Write-Host ""
    exit 1
}

# curl.exe (nicht das PowerShell-Alias 'curl' = Invoke-WebRequest!)
$Curl = "$env:SystemRoot\System32\curl.exe"
if (-not (Test-Path $Curl)) {
    Write-Host "  ABBRUCH: curl.exe nicht gefunden unter $Curl" -ForegroundColor Red
    exit 1
}

# Dateien pro Szene. Das grosse Combined-ZIP und StereoNEF sind bewusst
# NICHT dabei: das Combined-ZIP wird serverseitig live erzeugt und laeuft
# regelmaessig in einen Timeout.
function Get-SceneFiles([int]$n) {
    @(
        "clean_cloud${n}_UPDATE.pcd_.zip",      # LiDAR-Punktwolke (~500 MB)
        "scene${n}_small_rgb.csv",              # ausgeduennte Wolke, RGB
        "scene${n}_small_xyz.csv",              # ausgeduennte Wolke, XYZ
        "Scene${n}_Res688_1032_Depth.zip",      # Tiefenkarten zu den Stereopaaren
        "Scene${n}_Res688_1032_StereoIm.zip"    # undistortierte Stereobilder
    )
}

$failed = @()

foreach ($n in $Scenes) {

    $dest = Join-Path $Root "$DestRoot\syns-scene-$n"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    Write-Host ""
    Write-Host "=== Szene $n  ->  $dest" -ForegroundColor Cyan

    # Falls die Dateinamen abweichen: eine Datei scripts\urls_<n>.txt anlegen
    # und dort die echten Links (einer pro Zeile) von der Szenenseite einfuegen.
    $urlFile = Join-Path $PSScriptRoot "urls_$n.txt"
    if (Test-Path $urlFile) {
        Write-Host "    (nutze $urlFile)" -ForegroundColor DarkGray
        $urls = Get-Content $urlFile | Where-Object { $_.Trim() -ne "" }
    } else {
        $urls = Get-SceneFiles $n | ForEach-Object { "$Base/$n/$_" }
    }

    foreach ($url in $urls) {

        $name = Split-Path $url -Leaf
        $out  = Join-Path $dest $name

        Write-Host ""
        Write-Host "  -> $name" -ForegroundColor White

        & $Curl `
            --location `
            --fail `
            --continue-at - `
            --retry 10 `
            --retry-delay 5 `
            --retry-all-errors `
            --connect-timeout 30 `
            --progress-bar `
            --header "Cookie: $Cookie" `
            --header "Referer: https://syns.soton.ac.uk/" `
            --user-agent "Mozilla/5.0" `
            --output $out `
            $url

        # 33 = Server kann kein Resume, 416 = Datei schon vollstaendig
        if ($LASTEXITCODE -eq 33) {
            Write-Host "     Resume nicht moeglich, lade komplett neu..." -ForegroundColor Yellow
            Remove-Item $out -Force -ErrorAction SilentlyContinue
            & $Curl --location --fail --retry 10 --retry-delay 5 --retry-all-errors `
                    --progress-bar --header "Cookie: $Cookie" `
                    --header "Referer: https://syns.soton.ac.uk/" `
                    --user-agent "Mozilla/5.0" --output $out $url
        }

        if ($LASTEXITCODE -eq 0) {
            $mb = [math]::Round((Get-Item $out).Length / 1MB, 1)
            Write-Host "     OK  ($mb MB)" -ForegroundColor Green
        }
        elseif ($LASTEXITCODE -eq 22) {
            Write-Host "     FEHLER: Server lehnt ab (404 oder Login abgelaufen)." -ForegroundColor Red
            Write-Host "     -> Dateiname pruefen oder Cookie erneuern." -ForegroundColor Red
            Remove-Item $out -Force -ErrorAction SilentlyContinue
            $failed += $url
        }
        else {
            Write-Host "     ABBRUCH (curl-Code $LASTEXITCODE) - Skript nochmal starten, setzt fort." -ForegroundColor Yellow
            $failed += $url
        }
    }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
if ($failed.Count -eq 0) {
    Write-Host " Fertig, alles geladen." -ForegroundColor Green
} else {
    Write-Host " Nicht geladen ($($failed.Count)):" -ForegroundColor Yellow
    $failed | ForEach-Object { Write-Host "   $_" }
    Write-Host ""
    Write-Host " Bei 404: auf der Szenenseite den Link rechtsklicken ->" -ForegroundColor DarkGray
    Write-Host " Adresse kopieren, in scripts\urls_<szene>.txt einfuegen," -ForegroundColor DarkGray
    Write-Host " Skript nochmal starten." -ForegroundColor DarkGray
}
Write-Host "==================================================" -ForegroundColor Cyan
