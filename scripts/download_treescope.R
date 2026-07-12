#!/usr/bin/env Rscript
# download_treescope.R -- TreeScope-Kacheln (WSF-19) herunterladen.
#
# Laedt je Kachel cloud1_<N>/all/ die XYZ-Punktwolke + Instanz-Labels
# (optional trees_only) nach data/Treescope/. Reine Downloads, kein E57/XML
# -> laeuft auch unter Windows ohne den bekannten pye57/xml2-Absturz.
#
# Nutzung:
#   Rscript scripts/download_treescope.R                # Kacheln 1..5
#   Rscript scripts/download_treescope.R 0 20           # Kacheln 0..20
#   Rscript scripts/download_treescope.R 1 5 UCM-0323   # andere Szene

args   <- commandArgs(trailingOnly = TRUE)
from   <- if (length(args) >= 1) as.integer(args[1]) else 1L
to     <- if (length(args) >= 2) as.integer(args[2]) else 5L
scene  <- if (length(args) >= 3) args[3] else "WSF-19"

base   <- "https://tnl.treescope.org/Treescope/Treescope_v1.0_DIST"
outdir <- file.path("data", "Treescope")
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

# Welche Dateien pro Kachel (all_points reicht fuer Inventur + Validierung;
# trees_only optional dazu)
suffixes <- c("all/%1$s_all_points.pcd",
              "all/%1$s_all_points.labels",
              "all/%1$s_trees_only.pcd")

ok <- 0L; fail <- 0L
for (n in from:to) {
  tile <- sprintf("cloud1_%d", n)
  for (suf in suffixes) {
    rel  <- sprintf(suf, tile)                       # z.B. all/cloud1_1_all_points.pcd
    url  <- sprintf("%s/%s/ground_truth/scans/%s/%s", base, scene, tile, rel)
    dest <- file.path(outdir, basename(rel))
    if (file.exists(dest) && file.info(dest)$size > 0) {
      cat(sprintf("  vorhanden, uebersprungen: %s\n", basename(dest)))
      ok <- ok + 1L; next
    }
    res <- tryCatch({
      download.file(url, dest, mode = "wb", quiet = TRUE)
      sz <- file.info(dest)$size
      cat(sprintf("  OK  %-32s %8.1f KB\n", basename(dest), sz / 1024))
      TRUE
    }, error = function(e) {
      cat(sprintf("  FEHLER %-30s %s\n", basename(dest), conditionMessage(e)))
      if (file.exists(dest)) file.remove(dest)
      FALSE
    })
    if (isTRUE(res)) ok <- ok + 1L else fail <- fail + 1L
  }
}
cat(sprintf("\nFertig: %d geladen/vorhanden, %d fehlgeschlagen -> %s\n",
            ok, fail, normalizePath(outdir)))
