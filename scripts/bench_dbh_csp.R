# bench_dbh_csp.R -- CspStandSegmentation-BHD je SYSSIFOSS-Baum (fuer bench_dbh.py).
#
# CspStandSegmentation (Frey & Schindler, Uni Freiburg) baut auf lidR auf:
#   readLAS -> homogenisieren -> find_base_coordinates_raster ->
#   csp_cost_segmentation -> forest_inventory (BHD in m, transponierte Ausgabe).
# Wir nehmen je Wolke den groessten erkannten Stamm-BHD.
#
# Aufruf (R 4.4.x, Pakete in lib):
#   Rscript scripts/bench_dbh_csp.R <laz-verzeichnis> <out.csv> [lib-pfad]
#
# Ergebnis-CSV (id,csp_DBH_cm) an bench_dbh.py uebergeben:
#   python scripts/bench_dbh.py --csp-csv <out.csv>

args <- commandArgs(trailingOnly = TRUE)
lazdir <- args[1]; outcsv <- args[2]
if (length(args) >= 3) .libPaths(args[3])
suppressMessages({library(lidR); library(CspStandSegmentation)})

files <- list.files(lazdir, pattern = "\\.laz$", full.names = TRUE)
res <- data.frame(id = character(), csp_DBH_cm = numeric())
for (f in files) {
  tid <- paste(head(strsplit(tools::file_path_sans_ext(basename(f)), "_")[[1]], 3),
               collapse = "_")
  dbh <- tryCatch({
    las <- readLAS(f, filter = "-keep_class 0")            # nur Holzpunkte
    if (is.empty(las)) las <- readLAS(f)
    las <- decimate_points(las, homogenize(2000, 0.05))
    map <- find_base_coordinates_raster(las)
    seg <- csp_cost_segmentation(las, map, N_cores = 1)
    inv <- as.data.frame(forest_inventory(seg, slice_min = 1.0, slice_max = 1.6))
    d <- inv[grep("DBH", rownames(inv)), ]                 # transponiert
    if (length(d) == 0) d <- inv$DBH
    round(max(as.numeric(d), na.rm = TRUE) * 100, 1)
  }, error = function(e) { cat(tid, "ERR:", conditionMessage(e), "\n"); NA })
  cat(sprintf("%-20s Csp DBH %s cm\n", tid, dbh))
  res <- rbind(res, data.frame(id = tid, csp_DBH_cm = dbh))
}
write.csv(res, outcsv, row.names = FALSE)
cat("->", outcsv, "\n")
