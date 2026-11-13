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


# ---- Zusatzkennwerte aus der Literatur (Paper D, 09.11.2026) ---------------
# Je 5-m-Zelle (oder Segment). Quellen in lit/eignungskurven_quellen.md.
#   breite         Flaeche / Zelllaenge (m)                    Defra 2007; Graham 2018
#   dichte_02_2m   Anteil Treffer 0,2-2 m an allen Treffern < 2 m (dichteunabhaengig
#                  gegen Flugstreifen-Ueberlappung)            Hinsley & Bellamy 2000
#   baum_anteil    Anteil CHM > 8 m im Umkreis 2 m             Green 1994
#   saum_breite    Krautsaum: Flaeche mit Treffern 0,2-1 m im Ring 0-3 m ausserhalb der
#                  Gehoelzmaske, geteilt durch Zelllaenge (beide Seiten) Stoate 2001
#   graben_tiefe   Median Gelaende in der Zelle minus Minimum im Ring 0-5 m   Stoate 2001
#   wald_abstand   Abstand zur naechsten Gehoelzflaeche >= 1 ha und > 30 m breit
#                  (m, gekappt 1000)                           Batary 2012
#   im_wald        Zelle liegt im Wald -> keine Hecke (Unterholz/Waldrand 1-8 m wurde
#                  sonst als Hecke erkannt; Twente: ~50 % der 5-m-Zellen!)
#   verbund_laenge Laenge des Heckenverbunds, Teile mit Luecken <= 3 m zusammengefasst
#                  (Flaeche / Breite)                          Gelling 2007
gehoelz_masken <- function(chm, h_min = 1, wald_halbbreite = 15, wald_min = 10000) {
  veg <- terra::classify(chm, rbind(c(-Inf, h_min, NA), c(h_min, Inf, 1)))
  p <- st_as_sf(terra::as.polygons(veg, dissolve = TRUE))
  p <- st_make_valid(st_cast(p, "POLYGON", warn = FALSE))
  vu <- st_union(st_geometry(p))
  # Wald = Gehoelz, das nach 15 m Einzug noch besteht (> 30 m breit), mind. 1 ha
  # (Twente-Test: 10/15/20 m Einzug -> 17,0/14,3/10,6 ha, robust).
  # Flaeche/Umfang taugt hier nicht: Waldraender im 0,5-m-CHM sind stark zerfranst.
  # AHN ist laubfrei -> Kronendach loechrig; erst Luecken bis 3 m schliessen
  # (1,5 m raus, 1,5 m rein), sonst bleibt nach dem Einzug fast nichts (Test Twente:
  # ohne Schliessen 27 m2, mit 99 347 m2).
  zu <- st_buffer(st_buffer(vu, 1.5), -1.5)
  kern <- st_buffer(st_buffer(zu, -wald_halbbreite), wald_halbbreite)
  kern <- st_cast(st_make_valid(kern), "POLYGON", warn = FALSE)
  kern <- kern[as.numeric(st_area(kern)) >= wald_min]
  list(veg = vu, wald = if (length(kern)) st_union(kern) else st_sfc(st_polygon(), crs = st_crs(vu)))
}

extra_metrics <- function(las, segs, chm, netz, masken, dtm = NULL, L = 5) {
  n <- nrow(segs); g <- st_geometry(segs)
  out <- data.frame(hedge_id = segs$hedge_id,
                    breite = as.numeric(st_area(g)) / L)
  # Dichte 0,2-2 m als Trefferanteil, ueber 1-m-Raster und Zellmittel
  r1 <- terra::rast(terra::ext(chm), res = 1, crs = terra::crs(chm))
  lo <- las$Z < 2
  nall <- terra::rasterize(cbind(las$X[lo], las$Y[lo]), r1, fun = "count")
  nveg <- terra::rasterize(cbind(las$X[lo & las$Z >= 0.2], las$Y[lo & las$Z >= 0.2]), r1, fun = "count")
  nveg[is.na(nveg)] <- 0
  v <- terra::vect(g)
  a <- terra::extract(nall, v, fun = sum, na.rm = TRUE, ID = FALSE)[, 1]
  b <- terra::extract(nveg, v, fun = sum, na.rm = TRUE, ID = FALSE)[, 1]
  out$dichte_02_2m <- ifelse(a > 0, b / a, NA)
  # Baumanteil im Umkreis 2 m
  hoch <- terra::classify(chm, rbind(c(-Inf, 8, 0), c(8, Inf, 1)))
  out$baum_anteil <- terra::extract(hoch, terra::vect(st_buffer(g, 2)), fun = mean,
                                    na.rm = TRUE, ID = FALSE)[, 1]
  # Krautsaum
  krt <- las$Z >= 0.2 & las$Z < 1
  saum <- terra::rasterize(cbind(las$X[krt], las$Y[krt]), r1, fun = "count")
  saum <- terra::classify(saum, rbind(c(-Inf, 0.5, NA), c(0.5, Inf, 1)))
  ausser <- terra::mask(saum, terra::vect(masken$veg), inverse = TRUE)
  # Raster ist schon ausserhalb der Gehoelzmaske -> Puffer genuegt (kein st_difference,
  # das verwirft Zellen, die ganz in der Maske liegen)
  sv <- terra::extract(ausser, terra::vect(st_buffer(g, 3)), fun = sum, na.rm = TRUE, ID = FALSE)[, 1]
  out$saum_breite <- ifelse(is.na(sv), 0, sv) / L
  # Graben
  if (!is.null(dtm)) {
    med <- terra::extract(dtm, v, fun = median, na.rm = TRUE, ID = FALSE)[, 1]
    mn <- terra::extract(dtm, terra::vect(st_buffer(g, 5)), fun = min, na.rm = TRUE, ID = FALSE)[, 1]
    out$graben_tiefe <- pmax(0, med - mn)
  } else out$graben_tiefe <- NA_real_
  # Abstand zum Wald
  ctr <- st_point_on_surface(g)
  out$wald_abstand <- if (!all(st_is_empty(masken$wald)))
    pmin(1000, as.numeric(st_distance(ctr, masken$wald))) else 1000
  out$im_wald <- out$wald_abstand == 0
  # Verbund: Heckenteile, die sich mit 1,5 m Puffer beruehren (Luecke <= 3 m)
  verb <- st_cast(st_union(st_buffer(st_geometry(netz), 1.5)), "POLYGON")
  vid <- vapply(st_intersects(ctr, verb), function(i) if (length(i)) i[1] else NA_integer_, integer(1))
  netz_fl <- as.numeric(st_area(st_intersection(verb, st_union(st_geometry(netz)))))
  br <- median(out$breite, na.rm = TRUE)
  out$verbund_laenge <- netz_fl[vid] / br
  out
}
