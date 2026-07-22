#!/usr/bin/env Rscript
# canopy_lai.R -- Kronenanalyse auf zwei Wegen, aufgerufen aus canopy_lai.py.
#
#   Rscript canopy_lai.R <hemi.png> <cloud.las> <out.json> [maxVZA]
#
# Weg 1 (optisch, hemispheR): das aus dem Panorama erzeugte Zenit-Fisheye wird
#   binarisiert (Otsu), der Lueckenanteil ringweise ueber den Zenitwinkel
#   bestimmt und daraus LAI/Kronenoeffnung abgeleitet. lens='equidistant',
#   weil hemi_from_pano.py genau so projiziert.
#
# Weg 2 (strukturell, lidR): Boden klassifizieren (CSF), Hoehe normalisieren
#   (TIN), dann LAD() = MacArthur-Horn ueber 1-m-Schichten; LAI ist das
#   Integral des Profils.
#
# Beide Zahlen sind Schaetzungen mit eigener Verzerrung -- LIMITS unten und in
# der JSON-Ausgabe, damit sie nicht als gemessene Wahrheit weitergereicht werden.

suppressMessages({
  library(hemispheR)
  library(lidR)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) stop("Aufruf: canopy_lai.R <hemi.png> <cloud.las> <out.json> [maxVZA]")
hemi_png <- args[1]; las_path <- args[2]; out_json <- args[3]
maxVZA <- if (length(args) >= 4) as.numeric(args[4]) else 90

# ---- Weg 1: optisch ---------------------------------------------------------
# Das Fisheye ist synthetisch und exakt zentriert, die Kreismaske ist daher
# bekannt (Bildmitte, Radius = halbe Kantenlaenge) und muss nicht geraten werden.
info <- png::readPNG(hemi_png)
side <- dim(info)[1]
rc <- side / 2

# gamma = 2.2 linearisiert das sRGB-kodierte JPG. Mit gamma = 1 setzt Otsu die
# Schwelle bei 138 statt 107 und zaehlt helles Nadelwerk als Himmel -- LAI faellt
# dann von 1.56 auf 1.04, also um ein Drittel. Der Wert ist keine Stellschraube,
# sondern folgt aus der Kodierung der Quelldatei.
img <- import_fisheye(hemi_png, circ.mask = list(xc = rc, yc = rc, rc = rc),
                      circular = TRUE, gamma = 2.2, message = FALSE)
bw <- binarize_fisheye(img, method = "Otsu")

# endVZA = 70 Grad ist der uebliche Auswertebereich: jenseits davon wird der
# Weg durch die Krone so lang (und die Stammverdeckung so gross), dass der
# Lueckenanteil kaum noch Information ueber die Blattdichte traegt.
gf <- gapfrac_fisheye(bw, maxVZA = maxVZA, lens = "equidistant",
                      startVZA = 0, endVZA = 70, nrings = 7, nseg = 8,
                      message = FALSE)
can <- canopy_fisheye(gf)

num <- function(x) round(as.numeric(x[1]), 3)
lai_opt  <- num(can$L)      # LAI mit Clumping-Korrektur (Lang & Xiang)
lai_eff  <- num(can$Le)     # effektiver LAI, ohne Clumping
clumping <- num(can$LX)     # Clumping-Index; < 1 = Nadeln buendelweise
openness <- num(can$DIFN)   # diffuse non-interceptance, bereits in %

# ---- Weg 2: strukturell -----------------------------------------------------
las <- readLAS(las_path)
if (is.empty(las)) stop("LAS leer oder nicht lesbar")

las <- classify_ground(las, csf(sloop_smooth = TRUE))
las <- normalize_height(las, tin())
z <- las$Z
z <- z[is.finite(z) & z > 0 & z < 60]          # Ausreisser/Untergrund kappen

# LAD: MacArthur-Horn ueber 1-m-Schichten ab 2 m (darunter dominiert Unterwuchs
# und der Scanner selbst). k = 0.5 ist die uebliche Annahme fuer zufaellig
# orientierte Blattflaechen.
lad <- lidR::LAD(z, dz = 1, k = 0.5, z0 = 2)
lad <- lad[is.finite(lad$lad), ]
lai_str <- sum(lad$lad, na.rm = TRUE)          # Integral des Profils

profil <- lapply(seq_len(nrow(lad)), function(i)
  list(hoehe_m = as.numeric(lad$z[i]), lad = round(as.numeric(lad$lad[i]), 4)))

res <- list(
  optisch = list(
    methode = "hemispheR (Lueckenanteil aus Zenit-Fisheye)",
    paket = paste("hemispheR", as.character(packageVersion("hemispheR"))),
    lai = lai_opt,
    lai_effektiv = lai_eff,
    clumping_index = clumping,
    openness_pct = openness,
    linse = "equidistant",
    gamma = 2.2,
    vza_bereich_grad = c(0, 70),
    ringe = 7, segmente = 8
  ),
  strukturell = list(
    methode = "lidR LAD (MacArthur-Horn) ueber normalisierte Hoehe",
    paket = paste("lidR", as.character(packageVersion("lidR"))),
    lai = round(lai_str, 3),
    hoehe_p95_m = round(as.numeric(quantile(z, 0.95)), 2),
    schichtdicke_m = 1, k = 0.5, ab_hoehe_m = 2,
    profil = profil
  ),
  limits = paste(
    "Kein Validierungspaar: der optische Weg stammt aus einem Panorama, das aus",
    "Scanner-Pinhole-Bildern reprojiziert wurde (nicht aus einer Fisheye-Optik),",
    "und ueberschaetzt den Lueckenanteil bei ueberstrahltem Himmel. Der",
    "strukturelle Weg wendet MacArthur-Horn auf einen EINZELNEN terrestrischen",
    "Standpunkt an -- die Formel unterstellt jedoch senkrechte Durchdringung wie",
    "bei ALS, weshalb Verdeckung hinter Staemmen und in der oberen Krone den Wert",
    "nach unten zieht. Beide Zahlen sind Groessenordnungen, keine Messwerte."
  )
)

write(toJSON(res, auto_unbox = TRUE, pretty = TRUE, digits = 6, na = "null"), out_json)
cat(sprintf("   hemispheR: LAI %.2f (effektiv %.2f, Clumping %.2f), DIFN %.1f %%\n",
            lai_opt, lai_eff, clumping, openness))
cat(sprintf("   lidR     : LAI %.2f aus %d Schichten, P95 %.1f m\n",
            lai_str, nrow(lad), quantile(z, 0.95)))
