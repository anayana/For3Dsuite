#!/usr/bin/env Rscript
# hvi_stabilitaet.R -- Paper D: Sind die eignungsbasierten Flecken echt oder
# Rasterzufall? Das 5-m-Raster wird um 2,5 m verschoben (x, y, beides); je Art
# wird verglichen, ob dieselbe Heckenflaeche als geeignet erscheint.
#   Jaccard = |A & B| / |A | B| auf 1-m-Zellen (1 = identisch).
# Zum Vergleich dieselbe Pruefung fuer feste 20-m-Segmente (Verschiebung 10 m).
#
#   Rscript hvi_stabilitaet.R <shrub_div> <outdir> <norm_cache.las>
# Nur R, nur CPU.

suppressMessages({ library(lidR); library(sf); library(terra) })
args <- commandArgs(trailingOnly = TRUE)
shrub <- args[1]; outdir <- args[2]; cache <- args[3]
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))))
for (f in c("hvi_metrics.R", "hvi_index.R", "hvi_pipeline.R")) source(file.path(shrub, "R", f))
source(file.path(here, "hecken_funs.R"))
req <- read.csv(file.path(shrub, "data", "species_requirements.csv"), stringsAsFactors = FALSE)
kurz <- function(s) sub(" \\(.*", "", s)

las <- readLAS(cache, select = "xyzc"); st_crs(las) <- 28992
las <- filter_poi(las, !(Classification %in% c(6L, 9L, 26L)))
chm <- hvi_chm(las, res = 0.5)
netz <- hedge_net(chm)
grid1 <- terra::rast(terra::ext(netz), res = 1, crs = "EPSG:28992")

suit_raster <- function(L, shift) {
  s <- cut_segments(netz, L, shift = shift)
  M <- segment_metrics(las, s, chm)
  s <- s[match(M$hedge_id, s$hedge_id), ]
  S <- suitability_two(M, req)
  lapply(S, function(v) terra::values(terra::rasterize(
    terra::vect(cbind(s, v = as.numeric(v > 0.5))), grid1, field = "v"))[, 1])
}
jac <- function(a, b) { m <- !is.na(a) & !is.na(b); u <- sum((a[m] == 1) | (b[m] == 1))
  if (u == 0) NA else sum(a[m] == 1 & b[m] == 1) / u }

res <- list()
for (cfg in list(list(L = 5, d = 2.5), list(L = 20, d = 10))) {
  base <- suit_raster(cfg$L, c(0, 0))
  for (sh in list(c(cfg$d, 0), c(0, cfg$d), c(cfg$d, cfg$d))) {
    alt <- suit_raster(cfg$L, sh)
    for (k in names(base)) res[[length(res) + 1]] <- data.frame(
      raster_m = cfg$L, verschiebung = paste(sh, collapse = "/"),
      art = kurz(sub("\\|.*", "", k)), modus = sub(".*\\|", "", k),
      geeignet_m2 = sum(base[[k]] == 1, na.rm = TRUE), jaccard = jac(base[[k]], alt[[k]]))
    cat(sprintf("%d m, Verschiebung %s fertig\n", cfg$L, paste(sh, collapse = "/")))
  }
}
# ---- Gleitendes Fenster: Eignung je 1-m-Zelle = Mittel ueber 4 verschobene
# 5-m-Raster (Versatz 0/2,5 m in x und y), erst DANN Schwelle 0,5. Test: zweites
# Ensemble um 1,25 m versetzt; beide sollten dieselben Flecken liefern.
suit_mean <- function(L, shifts) {
  ras <- lapply(shifts, function(sh) {
    s <- cut_segments(netz, L, shift = sh)
    M <- segment_metrics(las, s, chm)
    s <- s[match(M$hedge_id, s$hedge_id), ]
    S <- suitability_two(M, req)
    lapply(S, function(v) terra::values(terra::rasterize(
      terra::vect(cbind(s, v = v)), grid1, field = "v"))[, 1])
  })
  setNames(lapply(names(ras[[1]]), function(k)
    rowMeans(sapply(ras, `[[`, k), na.rm = TRUE)), names(ras[[1]]))
}
off <- list(c(0, 0), c(2.5, 0), c(0, 2.5), c(2.5, 2.5))
eA <- suit_mean(5, off)
eB <- suit_mean(5, lapply(off, function(o) o + 1.25))
for (k in names(eA)) {
  a <- as.numeric(eA[[k]] > 0.5); b <- as.numeric(eB[[k]] > 0.5)
  a[is.nan(eA[[k]])] <- NA; b[is.nan(eB[[k]])] <- NA
  res[[length(res) + 1]] <- data.frame(raster_m = 0, verschiebung = "Ensemble 1.25",
    art = kurz(sub("\\|.*", "", k)), modus = sub(".*\\|", "", k),
    geeignet_m2 = sum(a == 1, na.rm = TRUE), jaccard = jac(a, b))
}
saveRDS(eA, file.path(outdir, "eignung_gleitend_1m.rds"))
cat("Gleitendes Fenster fertig\n")
r <- do.call(rbind, res)
write.csv(r, file.path(outdir, "stabilitaet_rasterverschiebung.csv"), row.names = FALSE)
z <- aggregate(jaccard ~ raster_m + art + modus, r, function(v) round(mean(v), 2))
z <- reshape(z, idvar = c("art", "modus"), timevar = "raster_m", direction = "wide")
names(z) <- sub("jaccard\\.", "jaccard_", names(z)); names(z)[names(z) == "jaccard_0"] <- "jaccard_gleitend5"
write.csv(z, file.path(outdir, "stabilitaet_zusammenfassung.csv"), row.names = FALSE)
print(z, row.names = FALSE)
