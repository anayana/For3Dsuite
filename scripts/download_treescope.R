# download_treescope.R -- TreeScope-Kacheln (WSF-19) herunterladen.
# Aufruf:  source("scripts/download_treescope.R")
#
# Laedt je Kachel cloud1_<N>/all/ die XYZ-Punktwolke + Instanz-Labels
# (+ trees_only) nach data/Treescope/. Reine Downloads, kein E57/XML
# -> laeuft auch unter Windows ohne den pye57/xml2-Absturz.
#
# Zum Anpassen einfach die drei Variablen unten aendern und erneut source()n:
ts_from  <- 1L         # erste Kachel
ts_to    <- 5L         # letzte Kachel
ts_scene <- "WSF-19"   # Szene

# ---------------------------------------------------------------------------
local({
  base   <- "https://tnl.treescope.org/Treescope/Treescope_v1.0_DIST"
  outdir <- file.path("data", "Treescope")
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

  suffixes <- c("all/%1$s_all_points.pcd",
                "all/%1$s_all_points.labels",
                "all/%1$s_trees_only.pcd")

  ok <- 0L; fail <- 0L
  for (n in ts_from:ts_to) {
    tile <- sprintf("cloud1_%d", n)
    for (suf in suffixes) {
      rel  <- sprintf(suf, tile)
      url  <- sprintf("%s/%s/ground_truth/scans/%s/%s", base, ts_scene, tile, rel)
      dest <- file.path(outdir, basename(rel))
      if (file.exists(dest) && file.info(dest)$size > 0) {
        cat(sprintf("  vorhanden, uebersprungen: %s\n", basename(dest)))
        ok <- ok + 1L; next
      }
      res <- tryCatch({
        download.file(url, dest, mode = "wb", quiet = TRUE)
        cat(sprintf("  OK  %-32s %8.1f KB\n",
                    basename(dest), file.info(dest)$size / 1024))
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
})
