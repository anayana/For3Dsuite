#!/usr/bin/env Rscript
# hvi_flandern_punkte.R -- Paper D: Zaehlpunkt-Ebene (Anwesenheit/Abwesenheit) fuer
# Flandern (INBO Meetnet Agrarische Soorten, CC0; DHMV II).
#
# Je Zaehlpunkt (Kreis r = 300 m): Heckenkennwerte zusammengefasst (Flaeche, Median,
# Anteile in Klassen nach Literatur). Je Art: am Punkt nachgewiesen (Apr-Jul) ja/nein.
# Test 1: Einzelkennwert -> AUC je Teilraum (West/Ost), Richtung stabil?
# Test 2: Logistisches Modell (wenige Kennwerte), auf West geschaetzt, auf Ost
#         getestet und umgekehrt (raeumlich getrennt).
# Kontrolle: Feldhase (Offenlandart) sollte schwach reagieren.
#
#   Rscript hvi_flandern_punkte.R <metrikdir> <auswahl_punkte.csv> <funde_arten.csv> <outdir>
# Nur R, nur CPU.

suppressMessages({ library(sf); library(terra); library(data.table) })
args <- commandArgs(trailingOnly = TRUE)
mdir <- args[1]; pkt <- fread(args[2]); fu <- fread(args[3]); outdir <- args[4]
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

pkt[, id := paste0("vl_", gsub(".", "_", locationID, fixed = TRUE))]
zus <- rbindlist(lapply(seq_len(nrow(pkt)), function(i) {
  f <- file.path(mdir, paste0("metrik_", pkt$id[i], ".tif"))
  leer <- file.exists(paste0(f, ".leer"))
  if (!file.exists(f) && !leer) return(NULL)
  base <- data.table(locationID = pkt$locationID[i], region = pkt$region[i])
  if (leer) return(cbind(base, hecke_m2 = 0))
  r <- terra::rast(f)
  kreis <- terra::vect(st_buffer(st_sfc(st_point(c(pkt$x[i], pkt$y[i])), crs = 31370), 300))
  v <- as.data.table(terra::values(terra::mask(r, kreis)))[is.finite(h_p95)]
  if (!nrow(v)) return(cbind(base, hecke_m2 = 0))
  cbind(base, data.table(
    hecke_m2       = nrow(v),                         # 1-m-Zellen = m2 Heckenflaeche
    h_p95_med      = median(v$h_p95),
    anteil_niedrig = mean(v$h_p95 < 3),               # < 3 m (Stoate & Szczur: Revier 1,8 / kein 2,8)
    anteil_hoch    = mean(v$h_p95 >= 6),              # >= 6 m (Verboom: Zwergfl. erst ab 6 m)
    breite_med     = median(v$breite),
    anteil_breit   = mean(v$breite >= 2),             # 2-m-Klasse (Chamberlain 1999)
    dichte_med     = median(v$dichte_02_2m, na.rm = TRUE),
    saum_med       = median(v$saum_breite, na.rm = TRUE),
    graben_med     = median(v$graben_tiefe, na.rm = TRUE),
    baum_anteil    = mean(v$baum_anteil, na.rm = TRUE),
    verbund_med    = median(v$verbund_laenge, na.rm = TRUE),
    wald_abst_med  = median(v$wald_abstand, na.rm = TRUE)))
}), fill = TRUE)
zus[is.na(hecke_m2), hecke_m2 := 0]
cat(nrow(zus), "Zaehlpunkte ausgewertet,", sum(zus$hecke_m2 > 0), "mit Hecke im 300-m-Kreis\n")

brut <- fu[month %in% 4:7]
arten <- sort(unique(brut$art))
for (a in arten) zus[, (a) := as.integer(locationID %in% brut[art == a]$locationID)]
fwrite(zus, file.path(outdir, "zaehlpunkte_kennwerte.csv"))

auc <- function(s, y) { ok <- is.finite(s) & !is.na(y); s <- s[ok]; y <- y[ok]
  n1 <- sum(y == 1); n0 <- sum(y == 0); if (n1 < 5 || n0 < 5) return(NA_real_)
  r <- rank(s); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
KW <- c("hecke_m2", "h_p95_med", "anteil_niedrig", "anteil_hoch", "breite_med", "anteil_breit",
        "dichte_med", "saum_med", "graben_med", "baum_anteil", "verbund_med", "wald_abst_med")

# Test 1: Einzelkennwerte je Teilraum
E <- rbindlist(lapply(arten, function(a) rbindlist(lapply(KW, function(k) {
  w <- zus[region == "West"]; o <- zus[region == "Ost"]
  data.table(art = a, kennwert = k, praevalenz = round(mean(zus[[a]]), 2),
             auc_west = round(auc(w[[k]], w[[a]]), 3), auc_ost = round(auc(o[[k]], o[[a]]), 3)) }))))
E[, stabil := sign(auc_west - 0.5) == sign(auc_ost - 0.5)]
E[, staerke := pmin(abs(auc_west - 0.5), abs(auc_ost - 0.5))]
fwrite(E, file.path(outdir, "einzelkennwerte_punkte.csv"))

# Test 2: logistisches Modell, raeumlich getrennt. Kennwerte standardisiert; NA (keine
# Hecke) -> Mittelwert, plus Heckenflaeche als eigener Term.
X <- copy(zus)
for (k in KW) { m <- mean(X[[k]], na.rm = TRUE); s <- sd(X[[k]], na.rm = TRUE)
  X[[k]] <- ifelse(is.finite(X[[k]]), (X[[k]] - m) / ifelse(s > 0, s, 1), 0) }
modell_kw <- c("hecke_m2", "h_p95_med", "breite_med", "dichte_med", "verbund_med", "baum_anteil")
M <- rbindlist(lapply(arten, function(a) rbindlist(lapply(c("West", "Ost"), function(cal) {
  test <- setdiff(c("West", "Ost"), cal)
  fm <- as.formula(paste(a, "~", paste(modell_kw, collapse = " + ")))
  g <- try(suppressWarnings(glm(fm, binomial, data = X[region == cal])), silent = TRUE)
  if (inherits(g, "try-error")) return(NULL)
  p <- predict(g, X[region == test], type = "response")
  data.table(art = a, kalibriert_auf = cal, getestet_auf = test,
             n_test = sum(X$region == test), praevalenz_test = round(mean(X[region == test][[a]]), 2),
             auc_test = round(auc(p, X[region == test][[a]]), 3))
}))))
fwrite(M, file.path(outdir, "modell_raeumlich_getrennt.csv"))

options(width = 160)
print(M[order(-auc_test)])
print(E[stabil == TRUE & staerke >= 0.05][order(-staerke)][1:40])
