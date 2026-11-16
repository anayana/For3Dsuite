#!/usr/bin/env Rscript
# hvi_kalibrierung.R -- Paper D: Schwellen der Eignungskurven aus Funddaten
# schaetzen, Richtung aus der Literatur festhalten, raeumlich getrennt pruefen.
#
#   Kalibrierung: Kacheln 30HZ2_* (West), Test: Kacheln 31CZ1_* (Ost) -- und umgekehrt.
#   Art: Dorngrasmuecke (einzige Art mit genauen, offenen Funden im Gebiet).
#   Kennwerte und Richtung (Literatur, siehe lit/eignungskurven_quellen.md):
#     h_p95        fallend   (Stoate & Szczur 2001)
#     saum_breite  steigend  (Stoate & Szczur 2001)
#     dichte_02_2m fallend   (Annahme: dichte, hohe Hecken gemieden; Rotterdam § 11/13)
#   Kurve je Kennwert: linear zwischen p1 und p2 (mono_inc/mono_dec wie shrub_div).
#   p1/p2 = Quantile der Hintergrundwerte; gesucht wird das Paar mit der hoechsten
#   AUC auf der Kalibrierhaelfte. Kombination: gewichtetes arithmetisches Mittel
#   (tolerant), Gewichte gleich. Bewertet wird NUR auf der Testhaelfte.
#
#   Rscript hvi_kalibrierung.R <metrikdir> <gbif.json> <outdir>
# Nur R, nur CPU.

suppressMessages({ library(sf); library(terra); library(jsonlite) })
args <- commandArgs(trailingOnly = TRUE)
mdir <- args[1]; gbif <- args[2]; outdir <- args[3]
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
set.seed(1)

KENN <- c(h_p95 = "dec", saum_breite = "inc", dichte_02_2m = "dec")
Q <- seq(0.05, 0.95, by = 0.05)

tifs <- list.files(mdir, "^metrik_.*\\.tif$", full.names = TRUE)
haelfte <- ifelse(grepl("metrik_30HZ2", tifs), "West", "Ost")

d <- fromJSON(gbif); d <- d[grepl("^6ef0121b", d$datasetKey), ]
p <- st_transform(st_as_sf(d, coords = c("decimalLongitude", "decimalLatitude"), crs = 4326), 28992)

werte <- function(r, pts) {
  # Kennwerte an Punkten: Mittel der Heckenzellen im 5-m-Umkreis
  e <- terra::extract(r, terra::vect(st_buffer(pts, 5)), fun = mean, na.rm = TRUE, ID = FALSE)
  e[apply(e, 1, function(z) all(!is.finite(z))), ] <- NA
  e
}
daten <- list()
for (h in c("West", "Ost")) {
  R <- terra::merge(terra::sprc(lapply(tifs[haelfte == h], terra::rast)))
  names(R) <- names(terra::rast(tifs[haelfte == h][1]))
  inn <- terra::relate(terra::vect(p), terra::as.polygons(terra::ext(R)), "intersects")[, 1]
  fp <- werte(R, p[inn, ]); fp <- fp[is.finite(fp$h_p95), ]
  bg <- terra::spatSample(R[["h_p95"]], 3000, method = "random", na.rm = TRUE, as.points = TRUE)
  bv <- werte(R, st_as_sf(bg)); bv <- bv[is.finite(bv$h_p95), ]
  daten[[h]] <- rbind(cbind(fp, y = 1), cbind(bv, y = 0))
  cat(sprintf("%s: %d Funde an Hecken, %d Hintergrundpunkte\n", h, nrow(fp), nrow(bv)))
}

auc <- function(s, y) { ok <- is.finite(s); s <- s[ok]; y <- y[ok]
  r <- rank(s); n1 <- sum(y == 1); n0 <- sum(y == 0)
  (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
memb <- function(x, a, b, typ) {
  m <- pmin(pmax((x - a) / (b - a), 0), 1)
  if (typ == "dec") 1 - m else m
}
fit <- function(D) {
  par <- list()
  for (k in names(KENN)) {
    x <- D[[k]]; qs <- quantile(x[D$y == 0], Q, na.rm = TRUE)
    best <- c(NA, NA, -Inf)
    for (i in seq_along(qs)) for (j in seq_along(qs)) if (qs[j] > qs[i]) {
      a <- auc(memb(x, qs[i], qs[j], KENN[k]), D$y)
      if (is.finite(a) && a > best[3]) best <- c(qs[i], qs[j], a)
    }
    if (!is.finite(best[3])) best <- c(min(x, na.rm = TRUE), max(x, na.rm = TRUE) + 1e-6, NA)
    par[[k]] <- best
  }
  par
}
score <- function(D, par) {
  m <- sapply(names(par), function(k) memb(D[[k]], par[[k]][1], par[[k]][2], KENN[k]))
  rowMeans(m, na.rm = TRUE)
}
# Literaturkurven aus data/arten_eignung.csv zum Vergleich
lit <- list(h_p95 = c(1.8, 2.8), saum_breite = c(1.2, 3.2))

res <- list(); parout <- list()
for (cal in c("West", "Ost")) {
  test <- setdiff(c("West", "Ost"), cal)
  par <- fit(daten[[cal]])
  parout[[cal]] <- do.call(rbind, lapply(names(par), function(k)
    data.frame(kalibriert_auf = cal, kennwert = k, richtung = KENN[k],
               p1 = round(par[[k]][1], 3), p2 = round(par[[k]][2], 3),
               auc_kalibrierung = round(par[[k]][3], 3))))
  Dt <- daten[[test]]
  einzel <- sapply(names(par), function(k) auc(memb(Dt[[k]], par[[k]][1], par[[k]][2], KENN[k]), Dt$y))
  ml <- cbind(memb(Dt$h_p95, lit$h_p95[1], lit$h_p95[2], "dec"),
              memb(Dt$saum_breite, lit$saum_breite[1], lit$saum_breite[2], "inc"))
  res[[cal]] <- data.frame(
    kalibriert_auf = cal, getestet_auf = test,
    n_funde_test = sum(Dt$y == 1), n_hintergrund_test = sum(Dt$y == 0),
    auc_kalibriert_kombiniert = round(auc(score(Dt, par), Dt$y), 3),
    auc_literaturkurven = round(auc(rowMeans(ml), Dt$y), 3),
    auc_nur_hoehe_kalibriert = round(einzel[["h_p95"]], 3),
    auc_nur_saum_kalibriert = round(einzel[["saum_breite"]], 3),
    auc_nur_dichte_kalibriert = round(einzel[["dichte_02_2m"]], 3))
}
r <- do.call(rbind, res); pa <- do.call(rbind, parout)
write.csv(r, file.path(outdir, "kalibrierung_test_auc.csv"), row.names = FALSE)
write.csv(pa, file.path(outdir, "kalibrierung_schwellen.csv"), row.names = FALSE)
# Verteilung der Kennwerte: Funde vs Hintergrund (beide Haelften)
A <- do.call(rbind, daten)
vt <- do.call(rbind, lapply(c(names(KENN), "breite", "baum_anteil", "fhd"), function(k)
  data.frame(kennwert = k,
             median_fund = round(median(A[[k]][A$y == 1], na.rm = TRUE), 3),
             median_hintergrund = round(median(A[[k]][A$y == 0], na.rm = TRUE), 3),
             anteil_null_fund = round(mean(A[[k]][A$y == 1] == 0, na.rm = TRUE), 2))))
write.csv(vt, file.path(outdir, "kennwerte_fund_vs_hintergrund.csv"), row.names = FALSE)
print(pa, row.names = FALSE); print(r, row.names = FALSE); print(vt, row.names = FALSE)
