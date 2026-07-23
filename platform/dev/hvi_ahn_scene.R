#!/usr/bin/env Rscript
# hvi_ahn_scene.R -- HVI auf einem AHN-Ausschnitt rechnen und als Szenen-
# Rohmaterial ablegen. Aufgerufen aus seed_hvi_ahn.py.
#
#   Rscript hvi_ahn_scene.R <kachel.laz> <xmin> <ymin> <xmax> <ymax> <outdir> [shrub_div]
#
# Warum nicht hvi_ahn_run() aus shrub_div: das liest die KOMPLETTE Kachel
# (hier 340 Mio. Punkte) und schneidet erst danach zu -- das sprengt den
# Speicher. Hier wird der Ausschnitt schon beim Lesen per -keep_xy gefiltert,
# LASlib verwirft den Rest, bevor er im RAM landet.
#
# Ausgabe in <outdir>:
#   aoi_norm.las    hoehennormalisierte Punkte, PointSourceID = hedge_id (0 = keine)
#   hedges.gpkg     Heckenpolygone
#   hvi_result.json Kennwerte + Index je Segment

suppressMessages({
  library(lidR); library(sf); library(terra); library(jsonlite)
})

# PROJ_LIB zeigt auf dieser Maschine auf eine veraltete PostgreSQL/PostGIS-
# proj.db, die terras eigene ueberschattet -- jede EPSG-Aufloesung scheitert dann
# mit "empty srs". Auf die mit terra gelieferte Datenbank umbiegen.
local({
  p <- system.file("proj", package = "terra")
  if (nzchar(p)) Sys.setenv(PROJ_LIB = p, PROJ_DATA = p)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 6) stop("Aufruf: hvi_ahn_scene.R <laz> <xmin> <ymin> <xmax> <ymax> <outdir> [shrub_div] [ndvi.asc]")
laz <- args[1]
xmin <- as.numeric(args[2]); ymin <- as.numeric(args[3])
xmax <- as.numeric(args[4]); ymax <- as.numeric(args[5])
outdir <- args[6]
shrub <- if (length(args) >= 7 && nzchar(args[7])) args[7] else "C:/Users/A/Desktop/R/shrub_div"
ndvi_path <- if (length(args) >= 8 && nzchar(args[8])) args[8] else NA

dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
source(file.path(shrub, "R", "hvi_metrics.R"))
source(file.path(shrub, "R", "hvi_index.R"))
source(file.path(shrub, "R", "hvi_pipeline.R"))   # hvi_segment_table, hvi_chm
source(file.path(shrub, "R", "hvi_ahn.R"))        # hvi_ahn_hedges

# ---- 1+2) Ausschnitt lesen und auf Hoehe ueber Grund bringen ---------------
# Der -keep_xy-Filter muss die 340-Mio.-Punkt-Kachel trotzdem komplett
# dekomprimieren (~6 min), unabhaengig von der Fenstergroesse. Ergebnis daher
# zwischenspeichern -- Loeschen der Datei erzwingt einen Neubau.
cache <- file.path(outdir, "_norm_cache.las")
if (file.exists(cache)) {
  cat("1+2) Normalisierte Punkte aus Cache\n")
  las <- readLAS(cache, select = "xyzc")
  st_crs(las) <- 28992
} else {
  cat(sprintf("1) Lese %.0f x %.0f m aus %s\n", xmax - xmin, ymax - ymin, basename(laz)))
  las <- readLAS(laz, select = "xyzc",
                 filter = sprintf("-keep_xy %f %f %f %f -drop_z_below -1 -drop_z_above 200",
                                  xmin, ymin, xmax, ymax))
  if (is.empty(las)) stop("Ausschnitt leer -- Koordinaten pruefen")
  st_crs(las) <- 28992                    # RD New / Amersfoort
  cat(sprintf("   %s Punkte\n", format(npoints(las), big.mark = " ")))
  cat("2) Hoehennormalisierung (TIN ueber Bodenklasse 2)\n")
  las <- normalize_height(las, tin())
  las <- filter_poi(las, Z >= -0.5, Z < 40)
  writeLAS(las, cache)
}

# ---- 3) Heckensegmente aus dem CHM -----------------------------------------
# Nicht hvi_ahn_hedges(): das verwirft Polygone ueber 1500 m2, ein
# zusammenhaengendes Heckennetz ist aber GENAU ein grosses Polygon und fliegt
# damit komplett raus (im 500-m-Test blieben 2 Fragmente uebrig). Stattdessen:
#   a) Schmalheit statt Groesse pruefen -- Flaeche/Umfang ist bei einem Streifen
#      etwa die halbe Breite und haengt nicht an der Laenge. Waldbloecke haben
#      ein hohes Verhaeltnis, Hecken ein niedriges.
#   b) Das Netz danach mit einem Raster in Segmente fester Laenge schneiden.
#      ~20 m ist die uebliche Erhebungseinheit in Heckenkartierungen und liefert
#      genug Segmente, damit die relative HVI-Normierung ueberhaupt traegt.
hedge_segments <- function(las_norm, chm_res = 0.5, h_min = 1, h_max = 8,
                           max_halbbreite = 4, min_area = 60, seg_len = 20) {
  chm <- rasterize_canopy(las_norm, res = chm_res, algorithm = p2r())
  veg <- terra::classify(chm, rbind(c(-Inf, h_min, NA), c(h_min, h_max, 1),
                                    c(h_max, Inf, NA)))
  polys <- sf::st_as_sf(terra::as.polygons(veg, dissolve = TRUE))
  polys <- sf::st_cast(polys, "POLYGON", warn = FALSE)
  polys <- sf::st_make_valid(polys)

  flaeche <- as.numeric(sf::st_area(polys))
  umfang  <- as.numeric(sf::st_length(sf::st_cast(sf::st_geometry(polys),
                                                  "MULTILINESTRING")))
  schmal <- flaeche / pmax(umfang, 1e-6)          # ~ halbe Streifenbreite
  netz <- polys[flaeche >= min_area & schmal <= max_halbbreite, ]
  if (nrow(netz) == 0) return(netz)
  cat(sprintf("   Heckennetz: %d Teile, %.0f m2, Streifenbreite ~%.1f m\n",
              nrow(netz), sum(as.numeric(sf::st_area(netz))),
              2 * median(schmal[flaeche >= min_area & schmal <= max_halbbreite])))

  bb <- sf::st_bbox(netz)
  gitter <- sf::st_make_grid(netz, cellsize = seg_len,
                             offset = c(bb["xmin"], bb["ymin"]))
  segs <- suppressWarnings(sf::st_intersection(sf::st_union(sf::st_geometry(netz)),
                                               gitter))
  # Wo eine Rasterkante das Netz nur streift, entstehen Punkte und Linien.
  # st_cast("POLYGON") bricht daran ab ("polygons require at least 4 points"),
  # deshalb vorher die echten Flaechen herausziehen.
  segs <- sf::st_collection_extract(sf::st_sf(geometry = segs), "POLYGON",
                                    warn = FALSE)
  segs <- sf::st_cast(segs, "POLYGON", warn = FALSE)
  segs <- segs[as.numeric(sf::st_area(segs)) >= min_area / 2, ]
  segs$hedge_id <- seq_len(nrow(segs))
  segs
}

cat("3) Heckensegmente aus dem Kronenmodell\n")
hedges <- hedge_segments(las)
if (nrow(hedges) == 0) stop("Keine Heckensegmente im Ausschnitt")
st_crs(hedges) <- 28992
cat(sprintf("   %d Segmente\n", nrow(hedges)))

# ---- 4) HVI ----------------------------------------------------------------
cat("4) Metriken + Index je Segment\n")
chm <- hvi_chm(las, res = 0.5)

# NDVI-Analog (CIR-Pseudo-NDVI, ndvi_pdok.py) optional dazunehmen: aktiviert den
# HVI-Zustandssubindex (Gewicht 0,10) und die NDVI-Komponente der Wildbienen-
# Eignung. Das .asc traegt seine Georeferenz selbst, nur das CRS fehlt.
ndvi_rast <- NULL
if (!is.na(ndvi_path) && file.exists(ndvi_path)) {
  ndvi_rast <- terra::rast(ndvi_path)
  # CRS vom CHM uebernehmen statt aus dem String zu parsen -- terra 1.9 lehnt
  # das direkte "EPSG:28992" beim .asc mit "empty srs" ab; das CHM traegt es.
  terra::crs(ndvi_rast) <- terra::crs(chm)
  ndvi_rast[ndvi_rast <= -9990] <- NA
  cat(sprintf("   NDVI: median %.2f (CIR-Pseudo, PDOK)\n",
              median(terra::values(ndvi_rast), na.rm = TRUE)))
}
M <- hvi_segment_table(las, hedges, chm = chm, ndvi_rast = ndvi_rast)
M <- M[!is.na(M$h_p95), ]
hedges <- hedges[hedges$hedge_id %in% M$hedge_id, ]
idx <- hvi_compute(M)
res <- cbind(M, idx[, c("vertical_complexity", "volume_size",
                        "heterogeneity", "condition", "HVI")])
if (nrow(idx) >= 4) res$hedge_type <- hvi_classify(idx, k = 4)

# Arteignung auf ZWEI Arten aggregieren, um die Frage "haengt das nur an der
# Hoehe?" beantwortbar zu machen:
#   streng   = Liebig-Minimumgesetz (geom. Mittel, wie shrub_div): ein schlechter
#              Kennwert kippt die Eignung -- in diesem Gebiet ist das die Hoehe.
#   tolerant = gewichtetes arithmetisches Mittel derselben Antwortkurven: ein
#              schwacher Kennwert wird von den anderen ausgeglichen. Zeigt, wieviel
#              die NICHT-Hoehen-Kennwerte beitragen, wenn die Hoehe nicht vetoen darf.
# Beide aus denselben Memberships -- der Unterschied ist allein die Aggregation.
suitability_two <- function(M, req) {
  M <- as.data.frame(M); species <- unique(req$species)
  strict <- tol <- matrix(NA_real_, nrow(M), length(species),
                          dimnames = list(NULL, species))
  for (sp in species) {
    r <- req[req$species == sp, ]
    memb <- matrix(NA_real_, nrow(M), nrow(r))
    for (j in seq_len(nrow(r))) {
      p <- as.numeric(r[j, c("p1", "p2", "p3", "p4")]); p <- p[!is.na(p)]
      memb[, j] <- vapply(M[[r$metric[j]]], hvi_membership, numeric(1),
                          type = r$type[j], p = p)
    }
    w <- r$weight / sum(r$weight)
    keep <- !is.na(memb[1, ])                    # Kennwerte ohne Daten (NDVI-NA) raus
    wk <- w[keep] / sum(w[keep]); mk <- memb[, keep, drop = FALSE]
    strict[, sp] <- exp(as.numeric(log(pmax(mk, 1e-6)) %*% wk))   # geom. Mittel
    tol[, sp]    <- as.numeric(mk %*% wk)                          # arithm. Mittel
  }
  list(strict = as.data.frame(strict), tolerant = as.data.frame(tol))
}

req_path <- file.path(shrub, "data", "species_requirements.csv")
if (file.exists(req_path)) {
  req <- read.csv(req_path)
  two <- try(suitability_two(M, req), silent = TRUE)
  if (!inherits(two, "try-error")) {
    res <- cbind(res, two$strict)
    tol <- two$tolerant; names(tol) <- paste0(names(tol), "__tol")
    res <- cbind(res, tol)
  }
}
cat(sprintf("   HVI %.2f bis %.2f (Median %.2f)\n",
            min(res$HVI), max(res$HVI), median(res$HVI)))

# ---- 5) Punkte den Segmenten zuordnen --------------------------------------
# Punkt-in-Polygon fuer Millionen Punkte waere zu langsam -> Polygone in ein
# 0,5-m-Raster brennen und die Zelle je Punkt nachschlagen.
cat("5) Punkte den Segmenten zuordnen\n")
hid <- terra::rasterize(terra::vect(hedges), terra::rast(chm), field = "hedge_id")
vals <- terra::extract(hid, cbind(las$X, las$Y))[, 1]
vals[is.na(vals)] <- 0
# PointSourceID statt UserData: bei 20-m-Segmenten gibt es schnell mehr als die
# 255, die in ein uint8 passen; PointSourceID ist uint16.
las@data$PointSourceID <- as.integer(pmin(vals, 65535L))
cat(sprintf("   %s Punkte in Hecken\n",
            format(sum(vals > 0), big.mark = " ")))

# ---- 6) Ausgabe ------------------------------------------------------------
# Ausduennen: die Web-Wolke braucht keine 20 Mio. Punkte, Heckenpunkte werden
# aber vollstaendig behalten -- sie sind das Motiv.
keep_h <- which(las$PointSourceID > 0)
keep_o <- which(las$PointSourceID == 0)
if (length(keep_o) > 1.5e6) keep_o <- sample(keep_o, 1.5e6)
if (length(keep_h) > 2.0e6) keep_h <- sample(keep_h, 2.0e6)
las_out <- filter_poi(las, seq_len(npoints(las)) %in% c(keep_h, keep_o))

writeLAS(las_out, file.path(outdir, "aoi_norm.las"))
st_write(hedges, file.path(outdir, "hedges.gpkg"), delete_dsn = TRUE, quiet = TRUE)

zentren <- st_coordinates(st_centroid(st_geometry(hedges)))
res$x <- zentren[match(res$hedge_id, hedges$hedge_id), 1]
res$y <- zentren[match(res$hedge_id, hedges$hedge_id), 2]
res$flaeche_m2 <- as.numeric(st_area(hedges))[match(res$hedge_id, hedges$hedge_id)]

out <- list(
  quelle = list(datensatz = "AHN (Actueel Hoogtebestand Nederland), offene ALS-Punktwolke",
                kachel = basename(laz), crs = "EPSG:28992 (RD New)",
                aoi = c(xmin, ymin, xmax, ymax),
                lizenz = "CC-BY 4.0"),
  segmente = nrow(res),
  gewichte = as.list(hvi_default_weights),
  segmentliste = lapply(seq_len(nrow(res)), function(i) as.list(res[i, ])),
  limits = paste(
    "Heckenpolygone sind aus dem Kronenmodell abgeleitet (Hoehe 1-8 m, kleine",
    "lineare Objekte), NICHT kartiert -- Segmentgrenzen und die Abgrenzung",
    "gegen Baumreihen sind entsprechend unscharf. Der HVI ist zudem RELATIV:",
    "hvi_rescale normiert auf das 2.-98.-Perzentil DIESES Ausschnitts, ein Wert",
    "von 0,8 heisst 'strukturreich verglichen mit den anderen Hecken hier',",
    "nicht absolut. Antwortkurven der Arteignung sind unkalibrierte Startwerte."
  )
)
write(toJSON(out, auto_unbox = TRUE, pretty = TRUE, digits = 5, na = "null"),
      file.path(outdir, "hvi_result.json"))
cat(sprintf("-> %s (%d Segmente, %s Punkte)\n", outdir, nrow(res),
            format(npoints(las_out), big.mark = " ")))
