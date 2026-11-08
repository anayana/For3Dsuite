#!/usr/bin/env Rscript
# hvi_adaptiv.R -- Paper D: Segmente nach Struktur bzw. Eignung statt festem Raster.
#
# Idee: Feste Segmente (20/40 m) mitteln gute und schlechte Teilstuecke zusammen.
# Stattdessen:
#   1) Grundeinheit 5-m-Zellen (kleinste Laenge, bei der AHN noch genug Punkte
#      fuer Schichten/FHD liefert; Punktzahl wird mit ausgegeben).
#   2) Artbezogene Flecken: benachbarte 5-m-Zellen mit Eignung > 0,5 zu einem
#      Fleck zusammenfassen (Rest bleibt eigener Bereich).
#      Vergleich: Wie viel geeignete Flaeche finden feste 20/40-m-Segmente,
#      wie viel davon ist echt (in 5-m-Zellen geeignet)?
#   3) Strukturbezogene Einheiten: benachbarte 5-m-Zellen mit aehnlichem
#      Kennwertprofil verschmelzen (Kanten nach Abstand sortiert, Union-Find,
#      Schwelle im standardisierten Kennwertraum), dann Kennwerte neu je Einheit.
#
#   Rscript hvi_adaptiv.R <shrub_div> <outdir> <norm_cache.las>
# Nur R, nur CPU.

suppressMessages({ library(lidR); library(sf); library(terra) })
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) stop("Aufruf: hvi_adaptiv.R <shrub_div> <outdir> <norm_cache.las>")
shrub <- args[1]; outdir <- args[2]; cache <- args[3]
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))))
for (f in c("hvi_metrics.R", "hvi_index.R", "hvi_pipeline.R"))
  source(file.path(shrub, "R", f))
source(file.path(here, "hecken_funs.R"))
req <- read.csv(file.path(shrub, "data", "species_requirements.csv"), stringsAsFactors = FALSE)
SPECIES <- unique(req$species)
kurz <- function(s) sub(" \\(.*", "", s)

las <- readLAS(cache, select = "xyzc"); st_crs(las) <- 28992
las <- filter_poi(las, !(Classification %in% c(6L, 9L, 26L)))
chm <- hvi_chm(las, res = 0.5)
netz <- hedge_net(chm)
breite <- 2 * median(as.numeric(st_area(netz)) /
                     as.numeric(st_length(st_cast(st_geometry(netz), "MULTILINESTRING"))))
cat(sprintf("Heckennetz %d Teile, %.0f m2, Breite ~%.1f m\n",
            nrow(netz), sum(as.numeric(st_area(netz))), breite))

# Union-Find fuer zusammenhaengende Bereiche
uf_groups <- function(n, i, j) {
  p <- seq_len(n)
  fnd <- function(x) { while (p[x] != x) { p[x] <<- p[p[x]]; x <- p[x] }; x }
  for (k in seq_along(i)) { a <- fnd(i[k]); b <- fnd(j[k]); if (a != b) p[max(a, b)] <- min(a, b) }
  vapply(seq_len(n), fnd, integer(1))
}
# Nachbarschaft: Zellen, die eine Kante teilen (nicht nur eine Ecke)
edges_of <- function(cells) {
  nb <- st_relate(cells, cells, pattern = "F***1****")
  e <- do.call(rbind, lapply(seq_along(nb), function(a) if (length(nb[[a]])) cbind(a, nb[[a]])))
  e[e[, 1] < e[, 2], , drop = FALSE]
}

# ---- 1) Feine 5-m-Zellen + feste 20/40-m-Segmente ---------------------------
units <- list()
for (L in c(5, 20, 40)) {
  s <- cut_segments(netz, L)
  M <- segment_metrics(las, s, chm)
  s <- s[match(M$hedge_id, s$hedge_id), ]
  s$flaeche <- as.numeric(st_area(s))
  S <- suitability_two(M, req)
  units[[as.character(L)]] <- list(segs = s, M = M, S = S)
  cat(sprintf("%2d m: %d Einheiten\n", L, nrow(M)))
}
c5 <- units[["5"]]
# Punktzahl je 5-m-Zelle (reicht das fuer Schichten?)
idr <- terra::rasterize(terra::vect(c5$segs), terra::rast(chm), field = "hedge_id")
pid <- terra::extract(idr, cbind(las$X, las$Y))[, 1]
npz <- table(factor(pid[!is.na(pid)], levels = c5$segs$hedge_id))
cat(sprintf("Punkte je 5-m-Zelle: Median %d, 5%%-Quantil %d\n",
            as.integer(median(npz)), as.integer(quantile(npz, 0.05))))

# ---- 2) Artbezogene Flecken -------------------------------------------------
E5 <- edges_of(c5$segs)
grid1 <- terra::rast(terra::ext(netz), res = 1, crs = "EPSG:28992")
burn <- function(s, v) terra::values(terra::rasterize(terra::vect(cbind(s, v = v)), grid1, field = "v"))[, 1]

flecken <- list(); vergleich <- list()
for (sp in SPECIES) for (mode in c("streng", "tolerant")) {
  col <- paste0(sp, "|", mode)
  ok5 <- c5$S[[col]] > 0.5
  # Flecken: geeignete Zellen, die ueber eine Kante verbunden sind
  if (any(ok5)) {
    idx <- which(ok5)
    e <- E5[ok5[E5[, 1]] & ok5[E5[, 2]], , drop = FALSE]
    g <- uf_groups(length(idx), match(e[, 1], idx), match(e[, 2], idx))
    geo <- aggregate(c5$segs[idx, "flaeche"], by = list(fleck = g), FUN = sum)
    names(geo)[names(geo) == "flaeche"] <- "flaeche_m2"
    geo$art <- kurz(sp); geo$modus <- mode
    # Laenge ~ Zahl der 5-m-Zellen x 5 m (Diagonale ueberschaetzt bis Faktor 1,4)
    geo$laenge_m <- 5 * as.numeric(table(g)[as.character(geo$fleck)])
    flecken[[col]] <- geo
  }
  # Vergleich auf 1-m-Zellen: Referenz = geeignet in 5-m-Zellen
  r5 <- burn(c5$segs, as.numeric(ok5))
  for (L in c("20", "40")) {
    u <- units[[L]]
    rL <- burn(u$segs, as.numeric(u$S[[col]] > 0.5))
    m <- !is.na(r5) & !is.na(rL)
    vergleich[[paste(col, L)]] <- data.frame(
      art = kurz(sp), modus = mode, segment_m = as.integer(L),
      geeignet_5m_m2 = sum(r5[m] == 1),
      geeignet_fest_m2 = sum(rL[m] == 1),
      davon_echt_m2 = sum(r5[m] == 1 & rL[m] == 1),
      verpasst_anteil = round(1 - sum(r5[m] == 1 & rL[m] == 1) / max(1, sum(r5[m] == 1)), 3),
      falsch_anteil = round(1 - sum(r5[m] == 1 & rL[m] == 1) / max(1, sum(rL[m] == 1)), 3))
  }
}
vgl <- do.call(rbind, vergleich)
write.csv(vgl, file.path(outdir, "arteignung_5m_vs_fest.csv"), row.names = FALSE)
fl_all <- do.call(rbind, flecken)
fl_zus <- do.call(rbind, lapply(split(st_drop_geometry(fl_all), paste(fl_all$art, fl_all$modus)), function(d)
  data.frame(art = d$art[1], modus = d$modus[1], flecken = nrow(d),
             flaeche_m2 = round(sum(d$flaeche_m2)),
             laenge_median_m = round(median(d$laenge_m), 1),
             laenge_max_m = round(max(d$laenge_m), 1),
             flecken_unter_10m = sum(d$laenge_m < 10))))
write.csv(fl_zus, file.path(outdir, "flecken_je_art.csv"), row.names = FALSE)
st_write(fl_all, file.path(outdir, "flecken_je_art.gpkg"), delete_dsn = TRUE, quiet = TRUE)

# ---- 3) Strukturbezogene Einheiten (Region-Merging) ------------------------
feat <- c("h_p95", "fhd", "n_layers", "canopy_sd", "vertical_gap", "understory_openness")
X <- scale(as.matrix(c5$M[, feat])); X[is.na(X)] <- 0
d <- sqrt(rowSums((X[E5[, 1], , drop = FALSE] - X[E5[, 2], , drop = FALSE])^2))
merge_units <- function(thr) {
  # Kanten aufsteigend; Verschmelzen nur, wenn die Einheitsmittel nah bleiben
  # (Average-Linkage-Kriterium verhindert Kettenbildung des Single-Linkage).
  n <- nrow(X); p <- seq_len(n); sums <- X; cnt <- rep(1, n)
  fnd <- function(x) { while (p[x] != x) { p[x] <<- p[p[x]]; x <- p[x] }; x }
  for (k in order(d)) {
    if (d[k] > thr * 2) break
    a <- fnd(E5[k, 1]); b <- fnd(E5[k, 2]); if (a == b) next
    if (sqrt(sum((sums[a, ] / cnt[a] - sums[b, ] / cnt[b])^2)) <= thr) {
      lo <- min(a, b); hi <- max(a, b); p[hi] <- lo
      sums[lo, ] <- sums[lo, ] + sums[hi, ]; cnt[lo] <- cnt[lo] + cnt[hi]
    }
  }
  vapply(seq_len(n), fnd, integer(1))
}
ad_res <- list()
for (thr in c(1.0, 1.5, 2.0)) {
  g <- merge_units(thr)
  au <- aggregate(c5$segs["flaeche"], by = list(einheit = g), FUN = sum)
  au$hedge_id <- seq_len(nrow(au))
  au <- st_make_valid(au)
  Ma <- segment_metrics(las, au, chm)
  au <- au[match(Ma$hedge_id, au$hedge_id), ]
  hvi <- aggregate_hvi(subindices(Ma, "lokal"), "arithm")
  # Homogenitaet: mittlere Streuung der 5-m-Kennwerte innerhalb der Einheiten
  within <- mean(sapply(split(seq_len(nrow(X)), g), function(i) if (length(i) > 1) mean(apply(X[i, , drop = FALSE], 2, sd)) else 0))
  laenge <- 5 * as.numeric(table(g)[as.character(au$einheit)])
  ad_res[[as.character(thr)]] <- data.frame(schwelle = thr, einheiten = nrow(au),
    laenge_median_m = round(median(laenge), 1), laenge_p90_m = round(quantile(laenge, 0.9), 1),
    streuung_innen = round(within, 3), hvi_sd = round(sd(hvi), 3))
  if (thr == 1.5) {
    au$HVI <- hvi; au$laenge_m <- laenge
    st_write(au, file.path(outdir, "einheiten_adaptiv.gpkg"), delete_dsn = TRUE, quiet = TRUE)
  }
}
# Referenz: Streuung innerhalb fester Segmente (5-m-Zellen den festen Segmenten zuordnen)
ctr <- st_point_on_surface(st_geometry(c5$segs))
fest_ref <- do.call(rbind, lapply(c("20", "40"), function(L) {
  s <- units[[L]]$segs
  w <- st_within(ctr, s); g <- vapply(w, function(v) if (length(v)) v[1] else NA_integer_, integer(1))
  okg <- !is.na(g)
  within <- mean(sapply(split(which(okg), g[okg]), function(i) if (length(i) > 1) mean(apply(X[i, , drop = FALSE], 2, sd)) else 0))
  hv <- aggregate_hvi(subindices(units[[L]]$M, "lokal"), "arithm")
  data.frame(schwelle = paste0("fest ", L, " m"), einheiten = nrow(s),
             laenge_median_m = as.numeric(L), laenge_p90_m = as.numeric(L),   # nominell
             streuung_innen = round(within, 3), hvi_sd = round(sd(hv), 3))
}))
ad <- rbind(do.call(rbind, ad_res), fest_ref)
write.csv(ad, file.path(outdir, "einheiten_adaptiv_vs_fest.csv"), row.names = FALSE)

cat("\n== Geeignete Flaeche: 5-m-Zellen vs feste Segmente ==\n"); print(vgl, row.names = FALSE)
cat("\n== Flecken je Art (5-m-Zellen zusammengefasst) ==\n"); print(fl_zus, row.names = FALSE)
cat("\n== Strukturbezogene Einheiten vs feste Segmente ==\n"); print(ad, row.names = FALSE)
