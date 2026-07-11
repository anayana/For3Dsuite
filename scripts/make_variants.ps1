<#
.SYNOPSIS
    Erzeugt mit GIMP (Batch/Script-Fu) drei abgestufte Filter-Versionen
    eines Panoramas, zwischen denen User im Viewer waehlen koennen:

      v1_natural : dezente Optimierung (leichter Kontrast, etwas Saettigung)
      v2_vivid   : kraeftige Farben, mehr Kontrast ("knackig")
      v3_warm    : warmer Look Richtung goldene Stunde

.PARAMETER PanoFile
    Quell-Panorama (JPG/TIF)

.PARAMETER OutDir
    Zielordner; Dateien heissen pano_v1_natural.jpg usw.

.EXAMPLE
    .\make_variants.ps1 -PanoFile ..\output\scene01\pano_retouched.jpg -OutDir ..\output\scene01
#>

param(
    [Parameter(Mandatory = $true)][string]$PanoFile,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string]$GimpConsole = "C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $GimpConsole)) { throw "GIMP-Konsole nicht gefunden: $GimpConsole" }
if (-not (Test-Path $PanoFile)) { throw "Panorama nicht gefunden: $PanoFile" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Pfade fuer Script-Fu mit Vorwaertsschraegstrichen
$src = (Resolve-Path $PanoFile).Path -replace '\\', '/'
$out = (Resolve-Path $OutDir).Path -replace '\\', '/'

# Ein Script-Fu-Block pro Variante: laden -> Anpassungen -> als JPG speichern.
# Werte: brightness/contrast -0.5..0.5, Saettigung -100..100, Farbbalance -100..100
$scriptFu = @"
(let* ((load-src (lambda () (car (gimp-file-load RUN-NONINTERACTIVE "$src" "src"))))
       (save-jpg (lambda (image name)
                   (gimp-image-flatten image)
                   (file-jpeg-save RUN-NONINTERACTIVE image
                                   (car (gimp-image-get-active-drawable image))
                                   (string-append "$out/" name)
                                   name 0.92 0 1 1 "" 0 1 0 0)
                   (gimp-image-delete image))))

  ; --- v1 natural: dezent ---
  (let* ((img (load-src)) (d (car (gimp-image-get-active-drawable img))))
    (gimp-drawable-brightness-contrast d 0.02 0.06)
    (gimp-drawable-hue-saturation d HUE-RANGE-ALL 0 0 12 0)
    (save-jpg img "pano_v1_natural.jpg"))

  ; --- v2 vivid: kraeftig ---
  (let* ((img (load-src)) (d (car (gimp-image-get-active-drawable img))))
    (gimp-drawable-brightness-contrast d 0.0 0.15)
    (gimp-drawable-hue-saturation d HUE-RANGE-ALL 0 0 38 0)
    (save-jpg img "pano_v2_vivid.jpg"))

  ; --- v3 warm: goldene Stunde ---
  (let* ((img (load-src)) (d (car (gimp-image-get-active-drawable img))))
    (gimp-drawable-color-balance d TRANSFER-MIDTONES TRUE 14 2 -20)
    (gimp-drawable-color-balance d TRANSFER-HIGHLIGHTS TRUE 8 0 -12)
    (gimp-drawable-brightness-contrast d 0.04 0.05)
    (gimp-drawable-hue-saturation d HUE-RANGE-ALL 0 0 10 0)
    (save-jpg img "pano_v3_warm.jpg")))
"@

# Script-Fu ueber eine Datei laden - mehrzeilige -b-Argumente verwirren die
# Argument-Verarbeitung der GIMP-Konsole unter Windows.
$scmFile = Join-Path $env:TEMP "gimp_make_variants.scm"
$scriptFu | Out-File -FilePath $scmFile -Encoding ascii
$scmForFu = $scmFile -replace '\\', '/'

Write-Host "GIMP-Batch laeuft (3 Varianten, kann bei grossen Panoramen einige Minuten dauern) ..." -ForegroundColor Yellow
& $GimpConsole -i -d -f -b "(load \`"$scmForFu\`")" -b "(gimp-quit 0)"

Write-Host "`nFertig:" -ForegroundColor Green
Get-ChildItem $OutDir -Filter "pano_v*.jpg" | ForEach-Object { Write-Host "  $($_.FullName)  ($([math]::Round($_.Length/1MB,1)) MB)" }
