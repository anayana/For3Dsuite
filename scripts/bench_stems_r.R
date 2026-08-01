# bench_stems_r.R -- Stammdetektion und BHD mit den R-Verfahren, auf Plot-Ebene.
#
# Gegenstueck zum Python-Strang (3DFin, scripts/dbh_methods.py). Damit der
# Vergleich etwas wert ist, bekommen ALLE Verfahren dieselbe Wolke und dieselbe
# Aufgabe: finde die Staemme einer Plot-Wolke und miss ihren BHD.
#
# Verfahren:
#   lidR      Eigenbau auf lidR-Basis: Boden normalisieren, Brusthoehen-Scheibe,
#             Punktdichte-Cluster, Kreisfit. Die R-Baseline -- entspricht dem,
#             was inventory_from_cloud.py in Python macht, aber mit lidRs
#             Bodenmodell (csf) statt unserem Rasterperzentil.
#   csp       CspStandSegmentation (Frey & Schindler, Uni Freiburg): Segmentierung
#             ueber Kostenpfade vom Stammfuss aus, dann forest_inventory().
#             Das ist zugleich eine ITCD -- also der direkte R-Gegenspieler zu
#             unserem itcd_cloud.py.
#
# Aufruf:
#   Rscript scripts/bench_stems_r.R <plot.laz> <out-prefix> [lib-pfade,komma]
#
# Ausgabe: <out-prefix>_<verfahren>.csv mit x,y,DBH_cm  (+ <out-prefix>_log.txt)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2)
  stop("Aufruf: bench_stems_r.R <plot.laz> <out-prefix> [libs] [verfahren,komma]")
laz <- args[1]; outp <- args[2]
if (length(args) >= 3) .libPaths(c(strsplit(args[3], ",")[[1]], .libPaths()))
# Verfahren einzeln aufrufbar: die drei brauchen sehr unterschiedlich lange
# (lidR ~1 min, Csp ~11 min) -- ohne Filter wartet jeder Neuversuch
# eines Verfahrens auf alle anderen.
want <- if (length(args) >= 4) strsplit(args[4], ",")[[1]] else c("lidr", "csp")
run_it <- function(name) name %in% want

logfile <- paste0(outp, "_log.txt")
say <- function(...) {
  msg <- paste0(...)
  cat(msg, "\n"); cat(msg, "\n", file = logfile, append = TRUE)
}
cat("", file = logfile)

suppressMessages(library(lidR))
say("lidR ", as.character(packageVersion("lidR")))

las <- readLAS(laz)
if (is.empty(las)) stop("LAZ leer oder nicht lesbar")
say("Punkte gelesen: ", format(npoints(las), big.mark = "."))

# Bodennormalisierung einmal fuer alle Verfahren -- unterschiedliche Boeden
# waeren ein zweiter Unterschied neben dem Verfahren und wuerden den Vergleich
# unbrauchbar machen.
t0 <- Sys.time()
gnd <- tryCatch({
  l <- classify_ground(las, csf(sloop_smooth = TRUE, class_threshold = 0.2,
                                cloth_resolution = 0.5))
  normalize_height(l, tin())
}, error = function(e) { say("Normalisierung ERR: ", conditionMessage(e)); NULL })
if (is.null(gnd)) quit(status = 1)
say("normalisiert in ", round(as.numeric(Sys.time() - t0, units = "secs")), " s")

# ---------------------------------------------------------------- Kreisfit
fit_circle <- function(x, y) {
  A <- cbind(x, y, 1); b <- x^2 + y^2
  s <- tryCatch(qr.solve(A, b), error = function(e) NULL)
  if (is.null(s)) return(NULL)
  cx <- s[1] / 2; cy <- s[2] / 2
  r2 <- s[3] + cx^2 + cy^2
  if (r2 <= 0) return(NULL)
  r <- sqrt(r2)
  d <- sqrt((x - cx)^2 + (y - cy)^2)
  ang <- atan2(y - cy, x - cx) * 180 / pi
  arc <- sum(table(cut(ang, breaks = seq(-180, 180, by = 10))) > 0) * 10
  list(cx = cx, cy = cy, r = r, rms = sqrt(mean((d - r)^2)), arc = arc)
}

write_res <- function(name, df) {
  f <- paste0(outp, "_", name, ".csv")
  write.csv(df, f, row.names = FALSE)
  say("-> ", basename(f), ": ", nrow(df), " Staemme")
}

# ------------------------------------------------------------------- lidR
if (run_it("lidr")) {
t0 <- Sys.time()
res <- tryCatch({
  sl <- filter_poi(gnd, Z >= 1.05, Z <= 1.55)
  say("lidR: ", npoints(sl), " Punkte in der Brusthoehen-Scheibe")
  p <- as.data.frame(sl@data[, c("X", "Y")])
  # Zusammenhangskomponenten im 4-cm-Raster (wie die Python-Baseline)
  cell <- 0.04
  key <- paste(floor(p$X / cell), floor(p$Y / cell))
  # Nachbarschaftssuche ueber ein Gitter waere in R langsam -> hclust auf den
  # belegten Zellmittelpunkten mit 8-cm-Schnitt ist dieselbe Idee, schneller.
  cent <- aggregate(cbind(X, Y) ~ key, data = cbind(p, key = key), FUN = mean)
  if (nrow(cent) > 40000) stop("zu viele Zellen fuer hclust: ", nrow(cent))
  cl <- cutree(hclust(dist(cent[, c("X", "Y")]), method = "single"), h = 0.08)
  out <- do.call(rbind, lapply(unique(cl), function(k) {
    idx <- which(cl == k)
    if (length(idx) < 6) return(NULL)
    pts <- p[key %in% cent$key[idx], ]
    if (nrow(pts) < 40) return(NULL)
    f <- fit_circle(pts$X, pts$Y)
    if (is.null(f) || f$r < 0.04 || f$r > 0.75 || f$rms > 0.03 || f$arc < 100)
      return(NULL)
    data.frame(x = f$cx, y = f$cy, DBH_cm = round(200 * f$r, 1),
               RMS_cm = round(100 * f$rms, 1), arc_deg = f$arc)
  }))
  if (is.null(out)) out <- data.frame(x = numeric(), y = numeric(), DBH_cm = numeric())
  out
}, error = function(e) { say("lidR ERR: ", conditionMessage(e)); NULL })
if (!is.null(res)) {
  say("lidR fertig in ", round(as.numeric(Sys.time() - t0, units = "secs")), " s")
  write_res("lidr", res)
}
}

# -------------------------------------------------------------------- Csp
if (run_it("csp")) {
t0 <- Sys.time()
res <- tryCatch({
  library(CspStandSegmentation)
  say("CspStandSegmentation ", as.character(packageVersion("CspStandSegmentation")))
  thin <- decimate_points(gnd, homogenize(2000, 0.05))
  say("Csp: ausgeduennt auf ", npoints(thin), " Punkte")
  map <- find_base_coordinates_raster(thin)
  seg <- csp_cost_segmentation(thin, map, N_cores = 1)
  inv <- as.data.frame(forest_inventory(seg, slice_min = 1.0, slice_max = 1.6))
  say("Csp: forest_inventory Spalten: ", paste(names(inv), collapse = ", "))
  inv
}, error = function(e) { say("Csp ERR: ", conditionMessage(e)); NULL })
if (!is.null(res)) {
  say("Csp fertig in ", round(as.numeric(Sys.time() - t0, units = "secs")), " s")
  write.csv(res, paste0(outp, "_csp_raw.csv"), row.names = FALSE)
  say("-> ", basename(paste0(outp, "_csp_raw.csv")))
}
}

say("fertig.")
