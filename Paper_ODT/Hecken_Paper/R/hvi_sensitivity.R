#!/usr/bin/env Rscript
# hvi_sensitivity.R -- Paper D, F2: Wie stark haengt der HVI an Segmentlaenge,
# Normierung und Aggregation?  12 Varianten = 3 x 2 x 2:
#   Segmentlaenge  10 / 20 / 40 m
#   Normierung     lokal (2.-98. Perzentil des Ausschnitts, wie shrub_div)
#                  fest  (physikalische Spannen, unten FIXED_RANGE)
#   Aggregation    arithmetisch (gewichtetes Mittel der Subindizes, wie shrub_div)
#                  geometrisch  (gewichtetes geom. Mittel, Liebig-artig)
# Arteignung zusaetzlich streng (geom.) / tolerant (arithm.) je Segmentlaenge.
#
#   Rscript hvi_sensitivity.R <shrub_div> <outdir> <laz1> [laz2 ...]
#
# Daten: AHN4 (CC0), GeoTiles TU Delft 28FN2_16 + 28FN2_21, Ausschnitt
# RD New 255000-256000 / 494500-495500 (derselbe wie die Galerie-Szene).
# Nur CPU, nur R.

suppressMessages({ library(lidR); library(sf); library(terra) })

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) stop("Aufruf: hvi_sensitivity.R <shrub_div> <outdir> <laz...>")
shrub <- args[1]; outdir <- args[2]; lazs <- args[-(1:2)]
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
for (f in c("hvi_metrics.R", "hvi_index.R", "hvi_pipeline.R"))
  source(file.path(shrub, "R", f))
req <- read.csv(file.path(shrub, "data", "species_requirements.csv"),
                stringsAsFactors = FALSE)

AOI <- c(255000, 494500, 256000, 495500)
SEG_LEN <- c(10, 20, 40)
set.seed(1)

# ---- 1) Ausschnitt lesen, normalisieren (Cache) ---------------------------
cache <- file.path(outdir, "_norm_cache.las")
if (file.exists(cache)) {
  las <- readLAS(cache, select = "xyzc"); st_crs(las) <- 28992
} else {
  las <- readLAS(lazs, select = "xyzc",
                 filter = sprintf("-keep_xy %f %f %f %f -drop_z_below -10 -drop_z_above 200",
                                  AOI[1], AOI[2], AOI[3], AOI[4]))
  st_crs(las) <- 28992
  cat(sprintf("1) %s Punkte gelesen\n", format(npoints(las), big.mark = " ")))
  las <- normalize_height(las, tin())
  las <- filter_poi(las, Z >= -0.5, Z < 40)
  writeLAS(las, cache)
}
# Gebaeude, Wasser, Sonstiges raus (wie hvi_ahn_scene.R)
las <- filter_poi(las, !(Classification %in% c(6L, 9L, 26L)))
cat(sprintf("   %s Punkte nach Filter\n", format(npoints(las), big.mark = " ")))
chm <- hvi_chm(las, res = 0.5)

# ---- 2) Heckennetz (Schmalheitstest) und Segmente -------------------------
# Identisch mit hvi_ahn_scene.R, nur die Segmentlaenge variiert.
hedge_net <- function(chm, h_min = 1, h_max = 8, max_halbbreite = 4, min_area = 60) {
  veg <- terra::classify(chm, rbind(c(-Inf, h_min, NA), c(h_min, h_max, 1),
                                    c(h_max, Inf, NA)))
  polys <- st_as_sf(terra::as.polygons(veg, dissolve = TRUE))
  polys <- st_make_valid(st_cast(polys, "POLYGON", warn = FALSE))
  fl <- as.numeric(st_area(polys))
  um <- as.numeric(st_length(st_cast(st_geometry(polys), "MULTILINESTRING")))
  polys[fl >= min_area & fl / pmax(um, 1e-6) <= max_halbbreite, ]
}
cut_segments <- function(netz, seg_len, min_area = 60) {
  bb <- st_bbox(netz)
  gitter <- st_make_grid(netz, cellsize = seg_len, offset = c(bb["xmin"], bb["ymin"]))
  segs <- suppressWarnings(st_intersection(st_union(st_geometry(netz)), gitter))
  segs <- st_collection_extract(st_sf(geometry = segs), "POLYGON", warn = FALSE)
  segs <- st_cast(segs, "POLYGON", warn = FALSE)
  # Mindestflaeche skaliert mit der Zellflaeche (bei 20 m = 30 m2 wie bisher)
  segs <- segs[as.numeric(st_area(segs)) >= min_area / 2 * (seg_len / 20)^2, ]
  segs$hedge_id <- seq_len(nrow(segs))
  st_crs(segs) <- 28992
  segs
}

# Kennwerte je Segment: Punkte ueber ein 0,5-m-ID-Raster zuordnen statt
# clip_roi je Segment (bei 10 m sonst ~1000 Volldurchlaeufe).
segment_metrics <- function(las, segs, chm) {
  idr <- terra::rasterize(terra::vect(segs), terra::rast(chm), field = "hedge_id")
  pid <- terra::extract(idr, cbind(las$X, las$Y))[, 1]
  zs  <- split(las$Z[!is.na(pid)], pid[!is.na(pid)])
  cv  <- terra::extract(chm, terra::vect(segs))
  cvs <- split(cv[, 2], segs$hedge_id[cv$ID])
  ids <- intersect(names(zs), names(cvs))
  M <- do.call(rbind, lapply(ids, function(i)
    data.frame(hedge_id = as.integer(i),
               t(hvi_segment_metrics(zs[[i]], chm_vals = cvs[[i]], ndvi = NA, dz = 0.5)))))
  M[!is.na(M$h_p95), ]
}

# ---- 3) Normierung und Aggregation ----------------------------------------
# Feste Spannen (Annahmen, im Paper offen zu nennen):
#   fhd 0-ln(20): Shannon-Entropie ueber 0,5-m-Baender bis 10 m Hoehe
#   n_layers 1-5: Zahl der HVI-Schichten
#   h_p95 0-10 m: Heckenmaske endet bei 8 m, Ueberhaelter bis ~10 m
#   canopy_sd 0-3 m, canopy_cv 0-1, vertical_gap 0-1 (Anteil)
FIXED_RANGE <- list(fhd = c(0, log(20)), n_layers = c(1, 5), h_p95 = c(0, 10),
                    canopy_sd = c(0, 3), canopy_cv = c(0, 1), vertical_gap = c(0, 1))
rescale_fixed <- function(x, r) pmin(pmax((x - r[1]) / (r[2] - r[1]), 0), 1)

subindices <- function(M, norm = c("lokal", "fest")) {
  norm <- match.arg(norm)
  sc <- function(v) if (norm == "lokal") hvi_rescale(M[[v]]) else rescale_fixed(M[[v]], FIXED_RANGE[[v]])
  rmean <- function(...) rowMeans(cbind(...), na.rm = TRUE)
  data.frame(
    vertical_complexity = rmean(sc("fhd"), M$vci, sc("n_layers"), M$strata_evenness),
    volume_size         = rmean(sc("h_p95"), M$cover_frac),
    heterogeneity       = rmean(sc("canopy_sd"), sc("canopy_cv"), sc("vertical_gap")))
}
aggregate_hvi <- function(sub, agg = c("arithm", "geom")) {
  agg <- match.arg(agg)
  w <- hvi_default_weights[colnames(sub)]; w <- w / sum(w)   # ohne NDVI
  S <- as.matrix(sub)
  if (agg == "arithm") as.numeric(S %*% w)
  else exp(as.numeric(log(pmax(S, 1e-3)) %*% w))
}

suitability_two <- function(M, req) {
  species <- unique(req$species)
  out <- list()
  for (sp in species) {
    r <- req[req$species == sp & req$metric %in% names(M), ]
    memb <- sapply(seq_len(nrow(r)), function(j) {
      p <- as.numeric(r[j, c("p1", "p2", "p3", "p4")]); p <- p[!is.na(p)]
      vapply(M[[r$metric[j]]], hvi_membership, numeric(1), type = r$type[j], p = p)
    })
    memb <- matrix(memb, nrow = nrow(M))
    keep <- colSums(!is.na(memb)) > 0
    w <- r$weight[keep] / sum(r$weight[keep]); mk <- memb[, keep, drop = FALSE]
    out[[paste0(sp, "|streng")]]   <- exp(as.numeric(log(pmax(mk, 1e-6)) %*% w))
    out[[paste0(sp, "|tolerant")]] <- as.numeric(mk %*% w)
  }
  as.data.frame(out, check.names = FALSE)
}

# ---- 4) Alle Varianten ------------------------------------------------------
netz <- hedge_net(chm)
cat(sprintf("2) Heckennetz: %d Teile, %.0f m2\n", nrow(netz), sum(as.numeric(st_area(netz)))))
grid1 <- terra::rast(terra::ext(AOI[1], AOI[3], AOI[2], AOI[4]), res = 1, crs = "EPSG:28992")

seg_tab <- list(); cells <- list(); suit_tab <- list()
for (L in SEG_LEN) {
  segs <- cut_segments(netz, L)
  M <- segment_metrics(las, segs, chm)
  segs <- segs[segs$hedge_id %in% M$hedge_id, ]
  cat(sprintf("3) %d m: %d Segmente\n", L, nrow(M)))
  S <- suitability_two(M, req)
  suit_tab[[as.character(L)]] <- data.frame(seg_len = L, hedge_id = M$hedge_id, S, check.names = FALSE)
  for (nm in c("lokal", "fest")) {
    sub <- subindices(M, nm)
    for (ag in c("arithm", "geom")) {
      v <- sprintf("L%02d_%s_%s", L, nm, ag)
      hvi <- aggregate_hvi(sub, ag)
      seg_tab[[v]] <- data.frame(variante = v, seg_len = L, norm = nm, agg = ag,
                                 hedge_id = M$hedge_id, sub, HVI = hvi,
                                 M[, c("h_p95", "fhd", "n_layers", "cover_frac")])
      segs$HVI <- hvi[match(segs$hedge_id, M$hedge_id)]
      cells[[v]] <- terra::values(terra::rasterize(terra::vect(segs), grid1, field = "HVI"))[, 1]
    }
  }
}
seg_df <- do.call(rbind, seg_tab)
write.csv(seg_df, file.path(outdir, "segmente_alle_varianten.csv"), row.names = FALSE)
write.csv(do.call(rbind, suit_tab), file.path(outdir, "arteignung_streng_tolerant.csv"), row.names = FALSE)

# ---- 5) Vergleich gegen Basis (20 m, lokal, arithm = shrub_div-Standard) ---
# Unterschiedliche Segmentlaengen haben verschiedene Segmente -> Vergleich
# auf 1-m-Zellen, die in ALLEN Varianten in einer Hecke liegen.
C <- do.call(cbind, cells)
ok <- stats::complete.cases(C)
base <- "L20_lokal_arithm"
cmp <- do.call(rbind, lapply(colnames(C), function(v) {
  a <- C[ok, base]; b <- C[ok, v]
  ta <- a >= quantile(a, 0.75); tb <- b >= quantile(b, 0.75)
  data.frame(variante = v,
             spearman_vs_basis = cor(a, b, method = "spearman"),
             mittl_abs_diff = mean(abs(a - b)),
             oberes_quartil_gleich = mean(ta == tb & ta),          # Anteil Zellen in beiden Top-25 %
             top25_ueberlappung = sum(ta & tb) / sum(ta),
             hvi_median = median(b), hvi_p05 = quantile(b, 0.05), hvi_p95 = quantile(b, 0.95))
}))
cmp$oberes_quartil_gleich <- NULL
write.csv(cmp, file.path(outdir, "vergleich_varianten.csv"), row.names = FALSE)

# Varianzanteile: balanciertes Design (jede Zelle in allen 12 Varianten), daher
# Haupteffekte direkt aus Mittelwerten -- lm() mit Zell-Faktor sprengt den RAM.
Z <- C[ok, , drop = FALSE]
fac <- list(seg_len = sub("_.*", "", colnames(Z)),
            norm = sub("^L\\d+_([a-z]+)_.*", "\\1", colnames(Z)),
            agg = sub(".*_", "", colnames(Z)))
gm <- mean(Z)
ss_tot <- sum((Z - gm)^2)
ss <- c(zelle = ncol(Z) * sum((rowMeans(Z) - gm)^2))
for (f in names(fac)) {
  lv <- tapply(seq_len(ncol(Z)), fac[[f]], function(j) mean(Z[, j]))
  nj <- table(fac[[f]])[names(lv)] * nrow(Z)
  ss[f] <- sum(nj * (lv - gm)^2)
}
ss["rest_wechselwirkung"] <- ss_tot - sum(ss)
anteil <- ss / ss_tot
write.csv(data.frame(quelle = names(anteil), anteil_varianz = round(anteil, 4)),
          file.path(outdir, "varianzanteile.csv"), row.names = FALSE)

# Arteignung: Segmente > 0,5 je Segmentlaenge, streng vs tolerant
st <- do.call(rbind, suit_tab)
artcols <- setdiff(names(st), c("seg_len", "hedge_id"))
zus <- do.call(rbind, lapply(split(st, st$seg_len), function(d)
  data.frame(seg_len = d$seg_len[1], n_segmente = nrow(d),
             t(sapply(artcols, function(k) round(100 * mean(d[[k]] > 0.5), 1))),
             check.names = FALSE)))
write.csv(zus, file.path(outdir, "arteignung_anteil_ueber_0.5.csv"), row.names = FALSE)

cat(sprintf("4) %d Zellen in allen Varianten\n", sum(ok)))
print(cmp[, c("variante", "spearman_vs_basis", "mittl_abs_diff", "top25_ueberlappung", "hvi_median")], digits = 3)
print(data.frame(anteil = round(anteil, 3)))
print(zus)
