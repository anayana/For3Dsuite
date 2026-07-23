#!/usr/bin/env Rscript
# qsm_export.R -- Zylindergeometrie eines QSM (aRchi-Cache) fuer den Web-Viewer.
#
#   Rscript qsm_export.R <modell.aRchi> <baum.laz> <out-prefix>
#
# Schreibt <out-prefix>.json (Offset + Anzahl) und <out-prefix>.bin (float32-
# Bloecke: Start n*3, Ende n*3, Radius n, Verzweigungsordnung n). Die Zylinder
# liegen im LOKALEN Frame des QSM (um den Stammfuss zentriert); der Offset ist
# genau die Zentrierung, die qsm_tree.R vor dem Bau abgezogen hat
# (mean X/Y, min Z der Holzpunkte) -- damit laesst sich das Modell spaeter
# pixelgenau auf dieselbe Punktwolke legen: welt = lokal + offset.

suppressMessages({library(aRchi); library(lidR); library(data.table)})

a <- commandArgs(trailingOnly = TRUE)
if (length(a) < 3) stop("Aufruf: qsm_export.R <modell.aRchi> <baum.laz> <out-prefix>")
archi <- a[1]; laz <- a[2]; outp <- a[3]

# Offset exakt wie in qsm_tree.R: aus ALLEN Holzpunkten (vor dem Ausduennen)
las <- readLAS(laz, select = "xyzc")
wood <- filter_poi(las, Classification == 0L)
off <- c(mean(wood$X), mean(wood$Y), min(wood$Z))

q <- get_QSM(read_aRchi(archi)); setDT(q)
n <- nrow(q)
starts <- as.matrix(q[, .(startX, startY, startZ)])
ends   <- as.matrix(q[, .(endX, endY, endZ)])
rad    <- as.numeric(q$radius_cyl)
ord    <- as.numeric(q$branching_order)

con <- file(paste0(outp, ".bin"), "wb")
writeBin(as.numeric(t(starts)), con, size = 4)   # n*3, row-major (x,y,z je Zyl)
writeBin(as.numeric(t(ends)),   con, size = 4)
writeBin(rad, con, size = 4)
writeBin(ord, con, size = 4)
close(con)

writeLines(sprintf('{"off": [%.6f, %.6f, %.6f], "count": %d, "order_max": %d}',
                   off[1], off[2], off[3], n, max(ord)),
           paste0(outp, ".json"))
cat(sprintf("-> %s.bin (%d Zylinder), Offset (%.2f, %.2f, %.2f)\n",
            basename(outp), n, off[1], off[2], off[3]))
