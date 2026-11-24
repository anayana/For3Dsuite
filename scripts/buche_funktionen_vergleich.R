# Vergleich vorhandener Biomassefunktionen für Buche bei starken Bäumen.
# Deutsche BWI-Funktionen (Kändler & Bösch 2012) und NSUR (Vonderach et al. 2018)
# aus dem freien R-Paket TapeS (CRAN), dazu Jenkins et al. 2003 und die lokale
# TLS-Stammvolumenfunktion aus scripts/kohlenstoff_beispiel.py (x Dichte 0,56 x Astfaktor 1,25).
# Höhen: typische Altbuchen-Höhenkurve H = 1,3 + 36 (1 - exp(-0,04 D)).
# Aufruf: Rscript scripts/buche_funktionen_vergleich.R   (vorher install.packages("TapeS"))
suppressMessages(library(TapeS))
D <- c(20, 30, 40, 50, 60, 70, 80, 90, 100, 110)
H <- round(1.3 + 36 * (1 - exp(-0.04 * D)), 1)
obj <- tprTrees(spp = rep(15, length(D)), Dm = as.list(D), Hm = as.list(rep(1.3, length(D))), Ht = H)
nfi  <- tprBiomass(obj, component = "agb", useNFI = TRUE, interval = "confidence")
nsur <- tprBiomass(obj, component = "all", useNFI = FALSE, interval = "none")
jen  <- exp(-2.0127 + 2.4342 * log(D))
loc  <- 7.75e-5 * D^1.727 * H^1.078 * 0.56 * 1.25 * 1000
out <- data.frame(BHD_cm = D, Hoehe_m = H,
                  BWI_kg = round(nfi[, "agb"]), BWI_KI_pct = round(100 * (nfi[, "agb_upr"] / nfi[, "agb"] - 1), 1),
                  NSUR_kg = round(nsur[, "agb"]), NSUR_Reisig_pct = round(100 * nsur[, "fwb"] / nsur[, "agb"], 1),
                  Jenkins_kg = round(jen), TLS_Wien_kg = round(loc))
mx <- pmax(out$BWI_kg, out$NSUR_kg, out$Jenkins_kg, out$TLS_Wien_kg)
mn <- pmin(out$BWI_kg, out$NSUR_kg, out$Jenkins_kg, out$TLS_Wien_kg)
out$Spanne_pct <- round(100 * (mx / mn - 1))
print(out, row.names = FALSE)
f <- file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE))), "buche_funktionen_vergleich.csv")
write.csv(out, f, row.names = FALSE)
