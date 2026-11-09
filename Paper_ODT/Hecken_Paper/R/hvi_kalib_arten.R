#!/usr/bin/env Rscript
# hvi_kalib_arten.R -- Paper D: Validierung und raeumlich getrennte Kalibrierung
# fuer mehrere Arten und Regionen (Flandern, Rheinland-Pfalz, Rotterdam).
#
#   Rscript hvi_kalib_arten.R <metrikdir> <funde.csv> <epsg> <outdir> [arten.csv]
#
# funde.csv: art, x, y, gruppe   (Koordinaten im CRS der Raster, gruppe = Teilraum
#            fuer die raeumliche Trennung, genau 2 Werte)
# Vorgehen je Art:
#   1. Fund = Mittel der Heckenzellen im 5-m-Umkreis; Funde ohne Hecke im 5-m-Umkreis
#      zaehlen als "nicht an Hecke" (Anteil wird berichtet).
#   2. Hintergrund = 3000 zufaellige Heckenzellen je Teilraum (verfuegbare Hecke).
#   3. Literaturkurven (arten.csv, unveraendert) -> AUC je Teilraum.
#   4. Kalibrierung: Richtung/Form aus Literatur, Schwellen per Gittersuche
#      (Quantile des Hintergrunds) auf Teilraum A, Test auf B, und umgekehrt.
#   5. Jeder Kennwert einzeln (ohne Richtungsvorgabe): AUC je Teilraum -> zeigt,
#      welche Struktur ueberhaupt Information traegt und ob die Richtung stabil ist.
# Nur R, nur CPU.

suppressMessages({ library(sf); library(terra) })
args <- commandArgs(trailingOnly = TRUE)
mdir <- args[1]; fund_csv <- args[2]; epsg <- as.integer(args[3]); outdir <- args[4]
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))))
arten_csv <- if (length(args) >= 5) args[5] else file.path(here, "..", "data", "arten_eignung.csv")
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
set.seed(1)

req <- read.csv(arten_csv, stringsAsFactors = FALSE)
req$kurz <- sub(" \\(.*", "", req$species)
F <- read.csv(fund_csv, stringsAsFactors = FALSE)
gruppen <- sort(unique(F$gruppe)); stopifnot(length(gruppen) == 2)

tifs <- list.files(mdir, "^metrik_.*\\.tif$", full.names = TRUE)
cat(length(tifs), "Kennwertraster\n")
# 5-m-Umkreismittel je Kachel vorab (Fokalmittel 11 x 11 Zellen, nur Heckenzellen);
# ein Gesamtmosaik waere bei weit verstreuten Kacheln riesig und fast leer.
fdir <- file.path(outdir, "fokal"); dir.create(fdir, showWarnings = FALSE)
ftifs <- vapply(tifs, function(t) {
  z <- file.path(fdir, basename(t))
  if (!file.exists(z)) {
    r <- terra::rast(t)
    terra::writeRaster(terra::focal(r, w = matrix(1, 11, 11), fun = mean, na.rm = TRUE,
                                    na.policy = "all"), z, overwrite = TRUE)
  }
  z }, character(1))
V <- terra::vrt(ftifs)
names(V) <- names(terra::rast(tifs[1]))
KW <- names(V)
werte <- function(pts) {
  e <- terra::extract(V, terra::vect(pts), ID = FALSE)
  e[!apply(e, 1, function(z) any(is.finite(z))), ] <- NA
  e
}
pf <- st_as_sf(F, coords = c("x", "y"), crs = epsg)
FW <- cbind(F, werte(pf))
# Hintergrund je Teilraum: zufaellige HECKENzellen (Originalraster, nicht fokal) aus den
# Kacheln, die die Huelle der Funde (+500 m) schneiden
BG <- do.call(rbind, lapply(gruppen, function(g) {
  hull <- st_buffer(st_convex_hull(st_union(pf[F$gruppe == g, ])), 500)
  hv <- terra::vect(hull)
  xy <- do.call(rbind, lapply(tifs, function(t) {
    r <- terra::rast(t, lyrs = 1)
    if (!terra::relate(terra::as.polygons(terra::ext(r), crs = terra::crs(r)), hv, "intersects")[1, 1]) return(NULL)
    r <- terra::mask(r, hv); i <- which(!is.na(terra::values(r)))
    if (length(i)) terra::xyFromCell(r, i) }))
  xy <- xy[sample(nrow(xy), min(3000, nrow(xy))), , drop = FALSE]
  cbind(data.frame(gruppe = g), werte(st_as_sf(data.frame(x = xy[, 1], y = xy[, 2]),
                                               coords = c("x", "y"), crs = epsg)))
}))
cat("Hintergrund je Teilraum:", paste(table(BG$gruppe), collapse = " / "), "\n")

auc <- function(s, y) { ok <- is.finite(s) & !is.na(y); s <- s[ok]; y <- y[ok]
  n1 <- sum(y == 1); n0 <- sum(y == 0); if (n1 < 5 || n0 < 5) return(NA_real_)
  r <- rank(s); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
mb <- function(x, typ, p) vapply(x, function(v) if (is.na(v)) NA_real_ else
  hvi_m(v, typ, p), numeric(1))
hvi_m <- function(x, type, p) switch(type,
  trapz = { a <- p[1]; b <- p[2]; c <- p[3]; d <- p[4]
    if (x <= a || x >= d) 0 else if (x < b) (x - a) / (b - a) else if (x <= c) 1 else (d - x) / (d - c) },
  mono_inc = { if (x <= p[1]) 0 else if (x >= p[2]) 1 else (x - p[1]) / (p[2] - p[1]) },
  mono_dec = { if (x <= p[1]) 1 else if (x >= p[2]) 0 else (p[2] - x) / (p[2] - p[1]) })
score <- function(D, kurven) {
  m <- sapply(seq_len(nrow(kurven)), function(i) {
    p <- as.numeric(kurven[i, c("p1", "p2", "p3", "p4")]); p <- p[!is.na(p)]
    mb(D[[kurven$metric[i]]], kurven$type[i], p) })
  m <- matrix(m, nrow = nrow(D)); w <- kurven$weight
  apply(m, 1, function(z) { ok <- is.finite(z); if (!any(ok)) NA else sum(z[ok] * w[ok]) / sum(w[ok]) })
}
kalibriere <- function(D, kurven) {
  Q <- seq(0.05, 0.95, by = 0.05)
  for (i in seq_len(nrow(kurven))) {
    k <- kurven$metric[i]; x <- D[[k]]; qs <- unique(quantile(x[D$y == 0], Q, na.rm = TRUE))
    best <- -Inf; bp <- NULL
    for (a in seq_along(qs)) for (b in seq_along(qs)) if (qs[b] > qs[a]) {
      p <- if (kurven$type[i] == "trapz") {
        w <- (qs[b] - qs[a]) / 2; c(qs[a] - w, qs[a], qs[b], qs[b] + w) } else c(qs[a], qs[b])
      s <- auc(mb(x, kurven$type[i], p), D$y)
      if (is.finite(s) && s > best) { best <- s; bp <- p }
    }
    if (!is.null(bp)) { kurven[i, c("p1", "p2", "p3", "p4")] <- c(bp, rep(NA, 4 - length(bp))) }
  }
  kurven
}

ergeb <- list(); schw <- list(); einzel <- list()
for (art in unique(F$art)) {
  kurven <- req[req$kurz == art & req$metric %in% KW, ]
  for (g in gruppen) {
    fa <- FW[FW$art == art & FW$gruppe == g, ]
    an <- is.finite(fa$h_p95)
    D <- rbind(cbind(fa[an, KW], y = 1), cbind(BG[BG$gruppe == g, KW], y = 0))
    for (k in KW) einzel[[length(einzel) + 1]] <- data.frame(art = art, gruppe = g, kennwert = k,
      auc = round(auc(D[[k]], D$y), 3), median_fund = round(median(D[[k]][D$y == 1], na.rm = TRUE), 3),
      median_hg = round(median(D[[k]][D$y == 0], na.rm = TRUE), 3))
    ergeb[[paste(art, g)]] <- data.frame(art = art, gruppe = g, n_funde = nrow(fa),
      anteil_an_hecke = round(mean(an), 2), n_an_hecke = sum(an),
      auc_literatur = if (nrow(kurven)) round(auc(score(D, kurven), D$y), 3) else NA)
  }
  if (nrow(kurven) == 0) next
  for (cal in gruppen) {
    test <- setdiff(gruppen, cal)
    mk <- function(g) { fa <- FW[FW$art == art & FW$gruppe == g & is.finite(FW$h_p95), ]
      rbind(cbind(fa[, KW], y = 1), cbind(BG[BG$gruppe == g, KW], y = 0)) }
    kc <- kalibriere(mk(cal), kurven)
    Dt <- mk(test)
    schw[[paste(art, cal)]] <- cbind(data.frame(art = art, kalibriert_auf = cal, getestet_auf = test,
      auc_test_kalibriert = round(auc(score(Dt, kc), Dt$y), 3),
      auc_test_literatur = round(auc(score(Dt, kurven), Dt$y), 3)),
      kurven = paste(sprintf("%s %s [%s]", kc$metric, kc$type,
        apply(round(kc[, c("p1", "p2", "p3", "p4")], 2), 1, function(z) paste(z[!is.na(z)], collapse = "/"))),
        collapse = "; "))
  }
}
E <- do.call(rbind, ergeb); S <- do.call(rbind, schw); Z <- do.call(rbind, einzel)
write.csv(E, file.path(outdir, "uebersicht_literaturkurven.csv"), row.names = FALSE)
write.csv(S, file.path(outdir, "kalibrierung_test.csv"), row.names = FALSE)
write.csv(Z, file.path(outdir, "einzelkennwerte_auc.csv"), row.names = FALSE)
# Stabilitaet der Einzelkennwerte: gleiche Richtung in beiden Teilraeumen?
st <- do.call(rbind, lapply(split(Z, paste(Z$art, Z$kennwert)), function(d)
  data.frame(art = d$art[1], kennwert = d$kennwert[1], auc_A = d$auc[1], auc_B = d$auc[2],
             richtung_stabil = sign(d$auc[1] - 0.5) == sign(d$auc[2] - 0.5),
             min_abstand_0.5 = round(min(abs(d$auc - 0.5)), 3))))
st <- st[order(-st$min_abstand_0.5 * st$richtung_stabil), ]
write.csv(st, file.path(outdir, "einzelkennwerte_stabil.csv"), row.names = FALSE)
print(E, row.names = FALSE); print(S[, 1:5], row.names = FALSE)
print(head(st[st$richtung_stabil, ], 15), row.names = FALSE)
