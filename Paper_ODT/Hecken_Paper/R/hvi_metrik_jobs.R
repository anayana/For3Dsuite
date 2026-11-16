#!/usr/bin/env Rscript
# hvi_metrik_jobs.R -- Paper D: Kennwerte je 5-m-Heckenzelle als 1-m-Raster, fuer
# beliebige Regionen (Flandern DHMV II, Rheinland-Pfalz LPO/LPG, NL AHN4).
#
#   Rscript hvi_metrik_jobs.R <shrub_div> <jobs.csv> <workdir> [max_jobs]
#
# jobs.csv: id, epsg, xmin, ymin, xmax, ymax, urls  (urls mit ";" getrennt)
#   Jeder Job = ein Ausschnitt (Kern). Gelesen wird Kern + 50 m Rand aus allen
#   genannten LAZ-Dateien (z. B. mehrere Flugstreifen), Ergebnis auf den Kern
#   zugeschnitten: <workdir>/metrik_<id>.tif (oder .leer, wenn keine Hecke).
# Fertige Jobs werden uebersprungen -> nach Neustart einfach erneut aufrufen.
# Heruntergeladene LAZ liegen in <workdir>/laz/ und werden geloescht, sobald kein
# offener Job sie mehr braucht. Nur R, nur CPU.

suppressMessages({ library(lidR); library(sf); library(terra) })
args <- commandArgs(trailingOnly = TRUE)
shrub <- args[1]; jobs_csv <- args[2]; work <- args[3]
max_jobs <- if (length(args) >= 4) as.integer(args[4]) else Inf
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))))
owd <- setwd(shrub)   # hvi_pipeline.R laedt R/... relativ
for (f in c("hvi_metrics.R", "hvi_index.R", "hvi_pipeline.R")) source(file.path(shrub, "R", f))
setwd(owd)
source(file.path(here, "hecken_funs.R"))
options(timeout = 3600)
dir.create(file.path(work, "laz"), recursive = TRUE, showWarnings = FALSE)

METRIKEN <- c("h_p95", "h_mean", "fhd", "n_layers", "understory_openness", "vertical_gap",
              "canopy_sd", "breite", "dichte_02_2m", "baum_anteil", "saum_breite",
              "graben_tiefe", "wald_abstand", "verbund_laenge")
J <- read.csv(jobs_csv, stringsAsFactors = FALSE)
ziel <- function(id) file.path(work, paste0("metrik_", id, ".tif"))
fertig <- function(id) file.exists(ziel(id)) || file.exists(paste0(ziel(id), ".leer"))

lade <- function(url) {
  f <- file.path(work, "laz", basename(sub("\\?.*$", "", url)))
  if (!file.exists(f) || file.size(f) < 1000) {
    tmp <- paste0(f, ".part")
    download.file(url, tmp, mode = "wb", quiet = TRUE)
    # Flandern liefert teils .zip mit einer LAZ darin
    if (grepl("\\.zip$", f, ignore.case = TRUE)) {
      inn <- unzip(tmp, exdir = file.path(work, "laz")); unlink(tmp)
      return(inn[grepl("\\.la[sz]$", inn, ignore.case = TRUE)])
    }
    file.rename(tmp, f)
  }
  if (grepl("\\.zip$", f, ignore.case = TRUE))
    return(list.files(file.path(work, "laz"), sub("\\.zip$", "", basename(f), ignore.case = TRUE),
                      full.names = TRUE))
  f
}

job <- function(j, rand = 50) {
  id <- J$id[j]; if (fertig(id)) return(invisible(NULL))
  epsg <- J$epsg[j]; core <- c(J$xmin[j], J$ymin[j], J$xmax[j], J$ymax[j])
  files <- unlist(lapply(strsplit(J$urls[j], ";")[[1]], lade))
  las <- readLAS(files, select = "xyzc", filter = sprintf(
    "-keep_xy %f %f %f %f -drop_z_below -100 -drop_z_above 3000 -drop_withheld",
    core[1] - rand, core[2] - rand, core[3] + rand, core[4] + rand))
  if (is.empty(las) || sum(las$Classification == 2L) < 100) {
    file.create(paste0(ziel(id), ".leer")); return(invisible(NULL)) }
  st_crs(las) <- epsg
  las <- filter_duplicates(las)
  dtm <- rasterize_terrain(las, res = 1, algorithm = tin())
  las <- normalize_height(las, tin())
  las <- filter_poi(las, Z >= -0.5, Z < 40, !(Classification %in% c(6L, 7L, 9L, 17L, 18L, 26L)))
  chm <- hvi_chm(las, res = 0.5)
  netz <- hedge_net(chm)
  if (nrow(netz) == 0) { file.create(paste0(ziel(id), ".leer")); return(invisible(NULL)) }
  st_crs(netz) <- epsg
  mk <- gehoelz_masken(chm)
  grid1 <- terra::rast(terra::ext(chm), res = 1, crs = paste0("EPSG:", epsg))
  s <- cut_segments(netz, 5); st_crs(s) <- epsg
  M <- segment_metrics(las, s, chm)
  s <- s[match(M$hedge_id, s$hedge_id), ]
  X <- extra_metrics(las, s, chm, netz, mk, dtm = dtm)
  M <- cbind(M, X[, setdiff(names(X), "hedge_id")])
  keep <- !M$im_wald; M <- M[keep, ]; s <- s[keep, ]
  if (nrow(M) == 0) { file.create(paste0(ziel(id), ".leer")); return(invisible(NULL)) }
  r <- terra::rast(lapply(METRIKEN, function(n)
    terra::rasterize(terra::vect(cbind(s, v = as.numeric(M[[n]]))), grid1, field = "v")))
  names(r) <- METRIKEN
  r <- terra::crop(r, terra::ext(core[1], core[3], core[2], core[4]))
  terra::writeRaster(r, ziel(id), overwrite = TRUE)
  cat(sprintf("%s: %d Zellen (%s)\n", id, nrow(M), format(Sys.time(), "%H:%M")))
  rm(las, chm); gc(verbose = FALSE)
}

aufraeumen <- function() {
  offen <- J$urls[!vapply(J$id, fertig, logical(1))]
  noetig <- basename(sub("\\?.*$", "", unlist(strsplit(offen, ";"))))
  noetig <- c(noetig, sub("\\.zip$", "", noetig, ignore.case = TRUE))
  for (f in list.files(file.path(work, "laz"), full.names = TRUE))
    if (!any(startsWith(basename(f), sub("\\.(laz|zip)$", "", noetig, ignore.case = TRUE)))) unlink(f)
}

n <- 0
for (j in seq_len(nrow(J))) {
  if (fertig(J$id[j])) next
  if (n >= max_jobs) break
  r <- try(job(j))
  if (inherits(r, "try-error")) cat("FEHLER bei", J$id[j], "\n")
  n <- n + 1
  aufraeumen()
}
cat(sprintf("offen: %d von %d\n", sum(!vapply(J$id, fertig, logical(1))), nrow(J)))
