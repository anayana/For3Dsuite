#!/usr/bin/env Rscript
# hvi_metrikraster.R -- Paper D: Kennwerte je 5-m-Zelle als 1-m-Raster fuer die
# Kalibrierung (hvi_kalibrierung.R). Abgeleitet aus hvi_validierung.R; eine
# Rasterlage (kein gleitendes Fenster), damit die Rechnung ~4x schneller ist.
#
# Verfahren UNVERAENDERT (dieselben Schwellen, Kurven, gleitendes 5-m-Fenster)
# auf AHN4-Kacheln am Rand von Rotterdam, wo unabhaengige Fundpunkte liegen:
#   Natural History Museum Rotterdam - Observations 2 (GBIF, CC BY 4.0,
#   Fachoekologen, Koordinatenunsicherheit 5 m), Dorngrasmuecke
#   (Curruca communis), Brutzeit Mai-Juli 2018-2024.
# Test: Ist die Eignung an Fundpunkten hoeher als an zufaelligen Heckenstellen
# derselben Kacheln? (Praesenz vs. Hintergrund, AUC; 0,5 = Zufall)
#
#   Rscript hvi_validierung.R <shrub_div> <workdir> <gbif.json> [arten.csv]
# Ohne arten.csv: alte Startkurven aus shrub_div. Mit data/arten_eignung.csv:
# Literaturkurven + Zusatzkennwerte (Saum, Graben, Wald, Dichte, Verbund), Waldzellen raus.
# Je Kachel: Download (GeoTiles TU Delft, AHN4 = CC0), Rechnung, LAZ wieder
# loeschen (Platz), Eignungsraster 1 m als GeoTIFF behalten. Nur R, nur CPU.

suppressMessages({ library(lidR); library(sf); library(terra); library(jsonlite) })
args <- commandArgs(trailingOnly = TRUE)
shrub <- args[1]; work <- args[2]; gbif <- args[3]
dir.create(work, recursive = TRUE, showWarnings = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))))
for (f in c("hvi_metrics.R", "hvi_index.R", "hvi_pipeline.R")) source(file.path(shrub, "R", f))
source(file.path(here, "hecken_funs.R"))
req_pfad <- if (length(args) >= 4) args[4] else file.path(shrub, "data", "species_requirements.csv")
req <- read.csv(req_pfad, stringsAsFactors = FALSE)
NEU <- TRUE
options(timeout = 1800)

KACHELN <- c("30HZ2_08", "30HZ2_09", "30HZ2_10", "30HZ2_13", "30HZ2_14", "30HZ2_15",
             "31CZ1_06", "31CZ1_07", "31CZ1_08", "31CZ1_11", "31CZ1_12", "31CZ1_13")
OFF <- list(c(0, 0), c(2.5, 0), c(0, 2.5), c(2.5, 2.5))

# Eine Rotterdamer AHN4-Teilkachel (1 x 1,25 km) sprengt mit ~14 GB den RAM.
# Daher je Kachel 4 Viertel, gelesen mit 20 m Rand (TIN, Fenster), Ergebnis
# auf das Viertel ohne Rand zugeschnitten.
METRIKEN <- c("h_p95", "h_mean", "fhd", "n_layers", "understory_openness", "vertical_gap",
              "canopy_sd", "breite", "dichte_02_2m", "baum_anteil", "saum_breite",
              "graben_tiefe", "wald_abstand", "verbund_laenge")
eignung_teil <- function(laz, core, tif, rand = 50) {
  las <- readLAS(laz, select = "xyzc", filter = sprintf(
    "-keep_xy %f %f %f %f -drop_z_below -10 -drop_z_above 200",
    core[1] - rand, core[2] - rand, core[3] + rand, core[4] + rand))
  if (is.empty(las)) return(invisible(NULL))
  st_crs(las) <- 28992
  dtm <- rasterize_terrain(las, res = 1, algorithm = tin())
  las <- normalize_height(las, tin())
  las <- filter_poi(las, Z >= -0.5, Z < 40, !(Classification %in% c(6L, 9L, 26L)))
  chm <- hvi_chm(las, res = 0.5)
  netz <- hedge_net(chm)
  if (nrow(netz) == 0) return(invisible(NULL))
  mk <- gehoelz_masken(chm)
  grid1 <- terra::rast(terra::ext(chm), res = 1, crs = "EPSG:28992")
  s <- cut_segments(netz, 5)
  M <- segment_metrics(las, s, chm)
  s <- s[match(M$hedge_id, s$hedge_id), ]
  X <- extra_metrics(las, s, chm, netz, mk, dtm = dtm)
  M <- cbind(M, X[, setdiff(names(X), "hedge_id")])
  keep <- !M$im_wald; M <- M[keep, ]; s <- s[keep, ]
  r <- terra::rast(lapply(METRIKEN, function(n)
    terra::rasterize(terra::vect(cbind(s, v = as.numeric(M[[n]]))), grid1, field = "v")))
  names(r) <- METRIKEN
  r <- terra::crop(r, terra::ext(core[1], core[3], core[2], core[4]))
  terra::writeRaster(r, tif, overwrite = TRUE)
  cat(sprintf("%s: %d Zellen\n", basename(tif), nrow(M)))
  rm(las, chm); gc(verbose = FALSE)
  invisible(tif)
}
eignung_kachel <- function(k) {
  fertig <- file.path(work, paste0("fertig_", k))
  if (file.exists(fertig)) return(invisible(NULL))
  laz <- file.path(work, paste0(k, ".LAZ"))
  if (!file.exists(laz))
    download.file(sprintf("https://geotiles.citg.tudelft.nl/AHN4_T/%s.LAZ", k), laz,
                  mode = "wb", quiet = TRUE)
  h <- readLASheader(laz)
  # Kachelgrenzen auf volle Meter (GeoTiles-Kacheln haben 20 m Rand)
  x0 <- round(h$`Min X` + 20); y0 <- round(h$`Min Y` + 20)
  xs <- c(x0, x0 + 500, x0 + 1000); ys <- c(y0, y0 + 625, y0 + 1250)
  for (i in 1:2) for (j in 1:2)
    eignung_teil(laz, c(xs[i], ys[j], xs[i + 1], ys[j + 1]),
                 file.path(work, sprintf("metrik_%s_%d%d.tif", k, i, j)))
  file.create(fertig)
  unlink(laz)
}
for (k in KACHELN) try(eignung_kachel(k))

cat("fertig\n")
