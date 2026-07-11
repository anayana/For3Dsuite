<#
.SYNOPSIS
    Erzeugt aus einem fertigen Equirectangular-Panorama Multiresolution-Tiles
    fuer Pannellum (empfohlen bei Panoramen > ~8000px Breite).

.DESCRIPTION
    Nutzt das offizielle Pannellum-Tool "generate.py" (Python + Pillow).
    Falls noch nicht vorhanden, einmalig besorgen:
        git clone --depth 1 https://github.com/mpetroff/pannellum.git
    (Ordner "pannellum\utils\multires\generate.py" wird benoetigt)

.PARAMETER PanoFile
    Pfad zum equirectangularen Panorama (z.B. output\scene01\pano_equirect.jpg)

.PARAMETER OutDir
    Zielordner fuer die Tiles (z.B. viewer\img\scene01_tiles)

.PARAMETER PannellumRepo
    Pfad zum lokal geklonten pannellum-Repo (enthaelt utils\multires\generate.py)

.EXAMPLE
    .\tile_pano.ps1 -PanoFile ..\output\scene01\pano_equirect.jpg -OutDir ..\viewer\img\scene01_tiles -PannellumRepo C:\tools\pannellum
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$PanoFile,

    [Parameter(Mandatory = $true)]
    [string]$OutDir,

    [Parameter(Mandatory = $true)]
    [string]$PannellumRepo
)

$ErrorActionPreference = "Stop"

$generatePy = Join-Path $PannellumRepo "utils\multires\generate.py"
if (-not (Test-Path $generatePy)) {
    throw "generate.py nicht gefunden unter '$generatePy'. Repo klonen: git clone --depth 1 https://github.com/mpetroff/pannellum.git"
}
if (-not (Test-Path $PanoFile)) {
    throw "Panorama-Datei '$PanoFile' nicht gefunden."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "Python nicht im PATH gefunden. Python 3 + 'pip install Pillow' installieren." }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Erzeuge Multires-Tiles ..." -ForegroundColor Yellow
& python $generatePy -o $OutDir $PanoFile

Write-Host "`nFertig! Tiles liegen unter: $OutDir" -ForegroundColor Green
Write-Host "generate.py gibt oben eine 'multiRes'-Konfiguration aus - die in viewer\index.html einfuegen." -ForegroundColor Cyan
