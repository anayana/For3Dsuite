<#
.SYNOPSIS
    Stitcht 6 (oder mehr) Fisheye-/Weitwinkel-Einzelbilder per Hugin-Kommandozeile
    zu einem nahtlosen Equirectangular-360-Panorama.

.DESCRIPTION
    Automatisiert den kompletten Hugin-CLI-Batch-Workflow:
    pto_gen -> cpfind -> cpclean -> linefind -> autooptimiser -> pano_modify -> nona -> enblend

    Voraussetzung: Hugin (https://hugin.sourceforge.io/) ist installiert.
    Die Kommandozeilen-Tools (cpfind, autooptimiser, nona, enblend, pano_modify, pto_gen)
    liegen normalerweise in "C:\Program Files\Hugin\bin".

.PARAMETER SceneDir
    Ordner mit den 6 Einzelbildern einer Szene (z.B. input\scene01)

.PARAMETER OutDir
    Zielordner fuer das fertige Panorama (z.B. output\scene01)

.PARAMETER LensType
    Projektionstyp der Eingabebilder fuer pto_gen -f:
      0 = Normal / rectilinear
      2 = Circular fisheye
      3 = Full-frame fisheye
    Default: 3 (Full-frame Fisheye, der haeufigste Fall bei DSLR + Fisheye-Objektiv)

.PARAMETER Fov
    Horizontales Sichtfeld (Grad) eines Einzelbildes, laut Objektiv-Datenblatt.
    Default: 180 (typisch fuer Fisheye)

.PARAMETER HuginBin
    Pfad zum Hugin "bin"-Ordner, falls nicht im PATH.

.EXAMPLE
    .\stitch.ps1 -SceneDir ..\input\scene01 -OutDir ..\output\scene01
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$SceneDir,

    [Parameter(Mandatory = $true)]
    [string]$OutDir,

    [int]$LensType = 3,
    [double]$Fov = 180,
    [string]$HuginBin = ""
)

$ErrorActionPreference = "Stop"

function Resolve-Tool {
    param([string]$Name)
    if ($HuginBin -and (Test-Path (Join-Path $HuginBin "$Name.exe"))) {
        return Join-Path $HuginBin "$Name.exe"
    }
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $default = "C:\Program Files\Hugin\bin\$Name.exe"
    if (Test-Path $default) { return $default }
    throw "Tool '$Name' nicht gefunden. Hugin installiert? Ggf. -HuginBin 'C:\Program Files\Hugin\bin' angeben."
}

$ptoGen        = Resolve-Tool "pto_gen"
$cpfind        = Resolve-Tool "cpfind"
$cpclean       = Resolve-Tool "cpclean"
$linefind      = Resolve-Tool "linefind"
$autooptimiser = Resolve-Tool "autooptimiser"
$panoModify    = Resolve-Tool "pano_modify"
$nona          = Resolve-Tool "nona"
$enblend       = Resolve-Tool "enblend"

if (-not (Test-Path $SceneDir)) { throw "SceneDir '$SceneDir' existiert nicht." }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path  # absolut machen, da wir spaeter ins _work-Verzeichnis wechseln

$images = Get-ChildItem -Path $SceneDir -Include *.jpg, *.jpeg, *.tif, *.tiff, *.png -File -Recurse |
    Sort-Object Name
if ($images.Count -lt 2) {
    throw "Zu wenige Bilder in '$SceneDir' gefunden (mind. 2 fuer ein Panorama, empfohlen 6)."
}
Write-Host "Gefundene Bilder: $($images.Count)" -ForegroundColor Cyan
$images | ForEach-Object { Write-Host "  - $($_.Name)" }

$work = Join-Path $OutDir "_work"
New-Item -ItemType Directory -Force -Path $work | Out-Null
Push-Location $work

try {
    $imgArgs = $images.FullName

    Write-Host "`n[1/7] pto_gen: Projekt anlegen (Projektion=$LensType, FOV=$Fov) ..." -ForegroundColor Yellow
    # Achtung: -p = Projektionstyp, -f = Sichtfeld (FOV)!
    & $ptoGen -p $LensType -f $Fov -o project.pto @imgArgs

    Write-Host "[3/7] cpfind: Kontrollpunkte suchen ..." -ForegroundColor Yellow
    & $cpfind --multirow -o project_cp.pto project.pto

    Write-Host "[4/7] cpclean: Ausreisser entfernen ..." -ForegroundColor Yellow
    & $cpclean -o project_clean.pto project_cp.pto

    Write-Host "[5/7] linefind: Vertikale Linien korrigieren ..." -ForegroundColor Yellow
    & $linefind -o project_lines.pto project_clean.pto

    Write-Host "[6/7] autooptimiser: Ausrichtung, Belichtung, Horizont optimieren ..." -ForegroundColor Yellow
    & $autooptimiser -a -m -l -s -o project_opt.pto project_lines.pto

    Write-Host "[6b/7] pano_modify: Equirectangular-Projektion, 360x180, Canvas ..." -ForegroundColor Yellow
    & $panoModify --projection=2 --fov=360x180 --canvas=AUTO --crop=AUTO -o project_final.pto project_opt.pto

    # Sicherheitscheck: Wenn die automatische Canvas absurd gross ist, stimmt die
    # Eingabegeometrie nicht (falsches FOV / falsche Projektion) -> abbrechen statt
    # die Festplatte mit einem Gigapixel-Rendering zu fluten.
    $pLine = (Get-Content project_final.pto | Where-Object { $_ -match '^p ' } | Select-Object -First 1)
    if ($pLine -match 'w(\d+)\s+h(\d+)') {
        $cw = [int]$Matches[1]; $ch = [int]$Matches[2]
        Write-Host "  Canvas: ${cw}x${ch}" -ForegroundColor Cyan
        if ($cw -gt 40000) {
            throw "Canvas ${cw}x${ch} ist unplausibel gross - LensType/Fov pruefen (aktuell: -LensType $LensType -Fov $Fov)."
        }
    }

    Write-Host "[7/7] nona: Bilder remappen ..." -ForegroundColor Yellow
    & $nona -m TIFF_m -o stitched project_final.pto

    Write-Host "[7b/7] enblend: Bilder nahtlos verschmelzen ..." -ForegroundColor Yellow
    $finalJpg = Join-Path $OutDir "pano_equirect.jpg"
    $stitchedTifs = Get-ChildItem -Path $work -Filter "stitched*.tif"
    & $enblend -o $finalJpg @($stitchedTifs.FullName)

    Write-Host "`nFertig! Panorama liegt unter: $finalJpg" -ForegroundColor Green
}
finally {
    Pop-Location
}
