# hecken_funs.R -- gemeinsame Funktionen fuer Paper D (Segmentierung, Kennwerte,
# Normierung, Aggregation, Arteignung). Wird von hvi_sensitivity.R und
# hvi_adaptiv.R per source() geladen; setzt shrub_div-Funktionen voraus.

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
cut_segments <- function(netz, seg_len, min_area = 60, shift = c(0, 0)) {
  bb <- st_bbox(netz)
  # shift verschiebt das Raster (Stabilitaetstest); Ursprung liegt dann vor bbox
  gitter <- st_make_grid(netz, cellsize = seg_len,
                         offset = c(bb["xmin"] - shift[1], bb["ymin"] - shift[2]))
  segs <- suppressWarnings(st_intersection(st_union(st_geometry(netz)), gitter))
  segs <- st_collection_extract(st_sf(geometry = segs), "POLYGON", warn = FALSE)
  segs <- st_cast(segs, "POLYGON", warn = FALSE)
  # Mindestflaeche skaliert mit der Zellflaeche (bei 20 m = 30 m2 wie bisher)
  segs <- segs[as.numeric(st_area(segs)) >= max(5, min_area / 2 * (seg_len / 20)^2), ]
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

