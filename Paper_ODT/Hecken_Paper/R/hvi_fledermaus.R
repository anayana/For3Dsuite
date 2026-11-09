#!/usr/bin/env Rscript
# hvi_fledermaus.R -- Paper D: Fledermaus-Kennwert (Leitstruktur) gegen Funde der
# Zwergfledermaus pruefen (Leiden, NHM Rotterdam Observations 2, GBIF, CC BY 4.0).
#
# Hypothesen aus Verboom & Huitema 1997 (NL): Zwergfledermaus fast nur nahe an
# Gehoelzlinien; Aktivitaet steigt mit der Hoehe; unter 6 m kaum. Daher Kennwerte
# je 1-m-Zelle (Gehoelz = AHN-Punkte ohne Gebaeude/Wasser, Hoehe >= 3 m):
#   abst_gehoelz    Abstand zum naechsten Gehoelz >= 3 m
#   abst_hoch       Abstand zum naechsten Gehoelz >= 6 m
#   abst_linie      Abstand zur naechsten Gehoelz-LINIE (Breite <= 20 m) >= 3 m
#   hoehe_umkreis   max. Gehoelzhoehe im 10-m-Umkreis
#   linien_300      Flaechenanteil Gehoelzlinien im 300-m-Umkreis
#   gehoelz_300     Flaechenanteil Gehoelz (alle) im 300-m-Umkreis
# Test: Fundorte gegen Zufallspunkte im selben Gebiet (gleiche Landflaeche, ohne
# Gebaeude/Wasser), AUC je Kennwert; raeumlich getrennt West/Ost.
#
#   Rscript hvi_fledermaus.R <workdir> <funde.json> <kachel1> [kachel2 ...]
# Kacheln = GeoTiles-AHN4-Teilkacheln (z. B. 30HN1_07). Nur R, nur CPU.

suppressMessages({ library(lidR); library(sf); library(terra); library(jsonlite) })
args <- commandArgs(trailingOnly = TRUE)
work <- args[1]; funde <- args[2]; kacheln <- args[-(1:2)]
dir.create(work, recursive = TRUE, showWarnings = FALSE)
options(timeout = 3600); set.seed(1)

# ---- 1) Gehoelzhoehe 1 m je Kachelviertel (RAM), Ergebnisse einzeln sichern ----
viertel <- function(laz, core, tif) {
  if (file.exists(tif)) return(invisible())
  las <- readLAS(laz, select = "xyzc", filter = sprintf("-keep_xy %f %f %f %f",
                 core[1] - 30, core[2] - 30, core[3] + 30, core[4] + 30))
  if (is.empty(las)) return(invisible())
  st_crs(las) <- 28992
  las <- normalize_height(las, tin())
  veg <- filter_poi(las, !(Classification %in% c(2L, 6L, 9L, 26L)), Z >= 0.5, Z < 40)
  r1 <- terra::rast(terra::ext(core[1], core[3], core[2], core[4]), res = 1, crs = "EPSG:28992")
  h <- if (is.empty(veg)) terra::setValues(r1, NA) else
    terra::rasterize(cbind(veg$X, veg$Y), r1, values = veg$Z, fun = max)
  # Gebaeude/Wasser als eigene Maske (fuer Zufallspunkte und Ausschluss)
  bw <- filter_poi(las, Classification %in% c(6L, 9L, 26L))
  m <- if (is.empty(bw)) terra::setValues(r1, 0) else
    terra::rasterize(cbind(bw$X, bw$Y), r1, fun = "count")
  m <- terra::ifel(is.na(m), 0, 1)
  out <- c(h, m); names(out) <- c("gehoelz_h", "bau_wasser")
  terra::writeRaster(out, tif, overwrite = TRUE)
  cat(basename(tif), format(Sys.time(), "%H:%M"), "\n")
}
for (k in kacheln) {
  laz <- file.path(work, paste0(k, ".LAZ"))
  fertig <- file.path(work, paste0("fertig_", k))
  if (file.exists(fertig)) next
  if (!file.exists(laz))
    download.file(sprintf("https://geotiles.citg.tudelft.nl/AHN4_T/%s.LAZ", k), laz, mode = "wb", quiet = TRUE)
  h <- readLASheader(laz); x0 <- round(h$`Min X` + 20); y0 <- round(h$`Min Y` + 20)
  for (i in 0:1) for (j in 0:1)
    viertel(laz, c(x0 + 500 * i, y0 + 625 * j, x0 + 500 * (i + 1), y0 + 625 * (j + 1)),
            file.path(work, sprintf("geh_%s_%d%d.tif", k, i, j)))
  file.create(fertig); unlink(laz)
}

# ---- 2) Kennwerte auf dem Mosaik --------------------------------------------
G <- terra::merge(terra::sprc(lapply(list.files(work, "^geh_.*\\.tif$", full.names = TRUE), terra::rast)))
h <- G[["gehoelz_h"]]; bw <- G[["bau_wasser"]]
g3 <- terra::ifel(h >= 3, 1, NA); g6 <- terra::ifel(h >= 6, 1, NA)
# Linie = Gehoelz, das nach 10 m Einzug verschwindet (<= 20 m breit); Luecken bis 2 m schliessen
gp <- st_as_sf(terra::as.polygons(g3, dissolve = TRUE))
gp <- st_buffer(st_buffer(st_union(gp), 1), -1)
breit <- st_buffer(st_buffer(gp, -10), 10)
linie <- st_difference(gp, breit)
lr <- terra::rasterize(terra::vect(linie), h, field = 1)
K <- c(terra::distance(g3), terra::distance(g6), terra::distance(lr),
       terra::focal(h, w = 21, fun = max, na.rm = TRUE),
       terra::focal(terra::ifel(is.na(lr), 0, 1), w = terra::focalMat(h, 300, "circle"), fun = sum),
       terra::focal(terra::ifel(is.na(g3), 0, 1), w = terra::focalMat(h, 300, "circle"), fun = sum))
names(K) <- c("abst_gehoelz", "abst_hoch", "abst_linie", "hoehe_umkreis", "linien_300", "gehoelz_300")
terra::writeRaster(K, file.path(work, "fledermaus_kennwerte.tif"), overwrite = TRUE)

# ---- 3) Funde gegen Zufallspunkte --------------------------------------------
d <- fromJSON(funde)
p <- st_transform(st_as_sf(d, coords = c("decimalLongitude", "decimalLatitude"), crs = 4326), 28992)
inn <- terra::relate(terra::vect(p), terra::as.polygons(terra::ext(K)), "within")[, 1]
p <- p[inn, ]
xy <- st_coordinates(p)
grp <- ifelse(xy[, 1] < median(xy[, 1]), "West", "Ost")
fv <- terra::extract(K, terra::vect(p), ID = FALSE)
land <- terra::ifel(bw == 0, 1, NA)
bg <- terra::spatSample(land, 6000, method = "random", na.rm = TRUE, as.points = TRUE)
bxy <- terra::crds(bg); bgrp <- ifelse(bxy[, 1] < median(xy[, 1]), "West", "Ost")
bv <- terra::extract(K, bg, ID = FALSE)
auc <- function(s, y) { ok <- is.finite(s); s <- s[ok]; y <- y[ok]; r <- rank(s)
  n1 <- sum(y == 1); n0 <- sum(y == 0); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
res <- do.call(rbind, lapply(names(K), function(k) do.call(rbind, lapply(c("West", "Ost"), function(g) {
  a <- fv[[k]][grp == g]; b <- bv[[k]][bgrp == g]
  data.frame(kennwert = k, teilraum = g, n_funde = sum(is.finite(a)),
             median_fund = round(median(a, na.rm = TRUE), 1), median_zufall = round(median(b, na.rm = TRUE), 1),
             auc = round(auc(c(a, b), c(rep(1, length(a)), rep(0, length(b)))), 3)) }))))
write.csv(res, file.path(work, "fledermaus_auc.csv"), row.names = FALSE)
# Anteil Funde nahe Gehoelz (Verboom: Zwergfledermaus fast nur an Linienelementen)
anteil <- data.frame(
  schwelle_m = c(10, 25, 50),
  funde_nah_gehoelz = sapply(c(10, 25, 50), function(s) round(mean(fv$abst_gehoelz <= s, na.rm = TRUE), 2)),
  zufall_nah_gehoelz = sapply(c(10, 25, 50), function(s) round(mean(bv$abst_gehoelz <= s, na.rm = TRUE), 2)),
  funde_nah_hoch = sapply(c(10, 25, 50), function(s) round(mean(fv$abst_hoch <= s, na.rm = TRUE), 2)),
  zufall_nah_hoch = sapply(c(10, 25, 50), function(s) round(mean(bv$abst_hoch <= s, na.rm = TRUE), 2)))
write.csv(anteil, file.path(work, "fledermaus_naehe.csv"), row.names = FALSE)
cat(nrow(p), "Funde im Gebiet\n"); print(res, row.names = FALSE); print(anteil, row.names = FALSE)
