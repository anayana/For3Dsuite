#!/usr/bin/env Rscript
# hvi_validierung.R -- Paper D: externe Validierung mit unabhaengigen Daten.
#
# Verfahren UNVERAENDERT (dieselben Schwellen, Kurven, gleitendes 5-m-Fenster)
# auf AHN4-Kacheln am Rand von Rotterdam, wo unabhaengige Fundpunkte liegen:
#   Natural History Museum Rotterdam - Observations 2 (GBIF, CC BY 4.0,
#   Fachoekologen, Koordinatenunsicherheit 5 m), Dorngrasmuecke
#   (Curruca communis), Brutzeit Mai-Juli 2018-2024.
# Test: Ist die Eignung an Fundpunkten hoeher als an zufaelligen Heckenstellen
# derselben Kacheln? (Praesenz vs. Hintergrund, AUC; 0,5 = Zufall)
#
#   Rscript hvi_validierung.R <shrub_div> <workdir> <gbif.json>
# Je Kachel: Download (GeoTiles TU Delft, AHN4 = CC0), Rechnung, LAZ wieder
# loeschen (Platz), Eignungsraster 1 m als GeoTIFF behalten. Nur R, nur CPU.

suppressMessages({ library(lidR); library(sf); library(terra); library(jsonlite) })
args <- commandArgs(trailingOnly = TRUE)
shrub <- args[1]; work <- args[2]; gbif <- args[3]
dir.create(work, recursive = TRUE, showWarnings = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))))
for (f in c("hvi_metrics.R", "hvi_index.R", "hvi_pipeline.R")) source(file.path(shrub, "R", f))
source(file.path(here, "hecken_funs.R"))
req <- read.csv(file.path(shrub, "data", "species_requirements.csv"), stringsAsFactors = FALSE)
options(timeout = 1800)

KACHELN <- c("30HZ2_08", "30HZ2_09", "30HZ2_10", "30HZ2_13", "30HZ2_14", "30HZ2_15",
             "31CZ1_06", "31CZ1_07", "31CZ1_08", "31CZ1_11", "31CZ1_12", "31CZ1_13")
OFF <- list(c(0, 0), c(2.5, 0), c(0, 2.5), c(2.5, 2.5))

eignung_kachel <- function(k) {
  tif <- file.path(work, paste0("eignung_", k, ".tif"))
  if (file.exists(tif)) return(invisible(tif))
  laz <- file.path(work, paste0(k, ".LAZ"))
  if (!file.exists(laz))
    download.file(sprintf("https://geotiles.citg.tudelft.nl/AHN4_T/%s.LAZ", k), laz,
                  mode = "wb", quiet = TRUE)
  las <- readLAS(laz, select = "xyzc", filter = "-drop_z_below -10 -drop_z_above 200")
  st_crs(las) <- 28992
  las <- normalize_height(las, tin())
  las <- filter_poi(las, Z >= -0.5, Z < 40, !(Classification %in% c(6L, 9L, 26L)))
  chm <- hvi_chm(las, res = 0.5)
  netz <- hedge_net(chm)
  grid1 <- terra::rast(terra::ext(chm), res = 1, crs = "EPSG:28992")
  if (nrow(netz) == 0) { unlink(laz); return(invisible(NULL)) }
  ras <- lapply(OFF, function(sh) {
    s <- cut_segments(netz, 5, shift = sh)
    M <- segment_metrics(las, s, chm)
    s <- s[match(M$hedge_id, s$hedge_id), ]
    S <- suitability_two(M, req)
    r <- terra::rast(lapply(names(S), function(n)
      terra::rasterize(terra::vect(cbind(s, v = S[[n]])), grid1, field = "v")))
    names(r) <- names(S); r
  })
  # gleitendes Fenster: je Ebene Mittel ueber die 4 Rasterlagen
  r <- terra::rast(lapply(names(ras[[1]]), function(n)
    terra::app(terra::rast(lapply(ras, `[[`, n)), mean, na.rm = TRUE)))
  names(r) <- names(ras[[1]])
  terra::writeRaster(r, tif, overwrite = TRUE)
  cat(sprintf("%s: %d Netzteile, %.0f m2 Hecke\n", k, nrow(netz), sum(as.numeric(st_area(netz)))))
  unlink(laz)
  invisible(tif)
}
for (k in KACHELN) try(eignung_kachel(k))

# ---- Auswertung ------------------------------------------------------------
tifs <- list.files(work, "^eignung_.*\\.tif$", full.names = TRUE)
E <- terra::merge(terra::sprc(lapply(tifs, terra::rast)))
names(E) <- names(terra::rast(tifs[1]))

d <- fromJSON(gbif)
d <- d[grepl("^6ef0121b", d$datasetKey), ]
p <- st_transform(st_as_sf(d, coords = c("decimalLongitude", "decimalLatitude"), crs = 4326), 28992)
inside <- terra::relate(terra::vect(p), terra::as.polygons(terra::ext(E)), "intersects")[, 1]
p <- p[inside, ]
# Wert je Fundpunkt: Maximum im 5-m-Umkreis (Koordinatenfehler 5 m; Saenger
# sitzen auf der Hecke, nicht zwingend auf der Mittellinie)
pv <- terra::extract(E, terra::vect(st_buffer(p, 5)), fun = max, na.rm = TRUE, ID = FALSE)
auf_hecke <- is.finite(pv[[1]])
cat(sprintf("Fundpunkte im Gebiet: %d, davon an Hecke (5 m): %d (%.0f %%)\n",
            nrow(p), sum(auf_hecke), 100 * mean(auf_hecke)))
# Hintergrund: 5000 Zufallspunkte auf Heckenzellen, gleich ausgewertet
set.seed(1)
bg <- terra::spatSample(E[[1]], 5000, method = "random", na.rm = TRUE, as.points = TRUE)
bgv <- terra::extract(E, terra::buffer(bg, 5), fun = max, na.rm = TRUE, ID = FALSE)

auc <- function(pos, neg) { pos <- pos[is.finite(pos)]; neg <- neg[is.finite(neg)]
  r <- rank(c(pos, neg)); (sum(r[seq_along(pos)]) - length(pos) * (length(pos) + 1) / 2) /
    (length(pos) * length(neg)) }
res <- do.call(rbind, lapply(names(E), function(n) {
  a <- pv[[n]][auf_hecke]; b <- bgv[[n]]
  w <- suppressWarnings(wilcox.test(a, b))
  data.frame(spalte = n, n_fund = sum(is.finite(a)),
             median_fund = round(median(a, na.rm = TRUE), 3),
             median_hintergrund = round(median(b, na.rm = TRUE), 3),
             auc = round(auc(a, b), 3), p_wert = signif(w$p.value, 3))
}))
write.csv(res, file.path(work, "validierung_dorngrasmuecke_rotterdam.csv"), row.names = FALSE)
print(res, row.names = FALSE)
