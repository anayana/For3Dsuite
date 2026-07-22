#!/usr/bin/env Rscript
# qsm_tree.R -- Quantitatives Strukturmodell (QSM) eines Einzelbaums aus TLS.
#
#   Rscript qsm_tree.R <baum.laz> <out.json> [voxelgroesse] [max_punkte]
#
# Rekonstruiert die Verzweigungsarchitektur als Zylindermodell (aRchi) und
# leitet daraus Metriken ab, die sich aus der reinen Punktwolke NICHT ablesen
# lassen: Holzvolumen, Oberflaeche, Verzweigungsordnungen, Gabelungsrate,
# Path Fraction, WBE-Skalierungsexponenten.
#
# Warum das hier belastbarer ist als ueblich: QSM braucht Holzpunkte OHNE Laub,
# und die Blattfilterung ist sonst die groesste Fehlerquelle. Im SYSSIFOSS-
# Datensatz ist die Trennung MANUELL annotiert (classification 0 = Holz,
# 1 = Blatt) -- das Modell startet also auf gemessener Wahrheit statt auf einer
# geschaetzten Filterung.

suppressMessages({
  library(aRchi)
  library(lidR)
  library(data.table)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("Aufruf: qsm_tree.R <baum.laz> <out.json> [voxel] [max_punkte]")
laz <- args[1]; out_json <- args[2]
voxel <- if (length(args) >= 3) as.numeric(args[3]) else 0.03
maxpts <- if (length(args) >= 4) as.numeric(args[4]) else 400000
# Obergrenze, bis zu der die teuren Pfadmetriken versucht werden (s. unten)
max_cyl_paths <- if (length(args) >= 5) as.numeric(args[5]) else 12000

las <- readLAS(laz, select = "xyzc")
if (is.empty(las)) stop("LAZ leer oder nicht lesbar")
n_all <- npoints(las)

# --- Holzpunkte: Ground Truth statt Filterheuristik -------------------------
wood <- filter_poi(las, Classification == 0L)
n_wood <- npoints(wood)
if (n_wood < 5000) stop("Zu wenige Holzpunkte fuer ein QSM")

# Auf lokalen Ursprung ziehen: aRchi rechnet in Metern um den Stammfuss,
# UTM-Absolutwerte (5.4e6) waeren fuer die Skelettierung unbrauchbar.
off <- c(mean(wood$X), mean(wood$Y), min(wood$Z))
dt <- data.table(X = wood$X - off[1], Y = wood$Y - off[2], Z = wood$Z - off[3])

# Ausduennen: die Skelettierung skaliert schlecht, unter ~1 cm Punktabstand
# gewinnt sie ohnehin nichts mehr dazu.
if (nrow(dt) > maxpts) dt <- dt[sample(.N, maxpts)]

cat(sprintf("  %s: %d Punkte, davon %d Holz (%.1f %%), verwendet %d\n",
            basename(laz), n_all, n_wood, 100 * n_wood / n_all, nrow(dt)))

# --- QSM aufbauen -----------------------------------------------------------
# Die Skelettierung braucht Minuten; das Modell wird daher neben der Ausgabe
# abgelegt und beim naechsten Lauf wiederverwendet (Loeschen erzwingt Neubau).
cache <- sub("\\.json$", ".aRchi", out_json)
if (file.exists(cache)) {
  cat("  Modell aus Cache:", basename(cache), "\n")
  a <- read_aRchi(cache)
} else {
  a <- build_aRchi()
  a <- add_pointcloud(a, point_cloud = dt)
  a <- skeletonize_pc(a, D = voxel)
  a <- smooth_skeleton(a)
  # KEIN simplify_skeleton() hier: laeuft es vor add_radius, bleiben radius,
  # radius_cyl und volume anschliessend durchgehend 0 -- der Radius wird still
  # nicht mehr geschaetzt, und Volumen wie Oberflaeche kommen als 0 heraus,
  # ohne dass irgendetwas eine Warnung wirft.
  a <- add_radius(a, sec_length = 0.5, method = "median")

  # Make_Path() legt jeden Pfad Stammfuss->Spitze einzeln ab und ist die
  # Voraussetzung fuer PathFraction/ForkRate/WBE. Der Aufwand waechst mit der
  # Zahl der Spitzen: bei 38.000 Zylindern und Verzweigungsordnung 8 lief der
  # Aufruf hier 2 h und belegte 11 GB, ohne fertig zu werden. Deshalb nur
  # unterhalb einer Groessenschwelle und mit Zeitdeckel -- die uebrigen
  # Metriken (Volumen, Oberflaeche, BHD, Ordnungen) haengen nicht daran.
  n_cyl <- nrow(get_QSM(a))
  if (n_cyl <= max_cyl_paths) {
    cat(sprintf("  Make_Path bei %d Zylindern ...\n", n_cyl))
    setTimeLimit(elapsed = 900, transient = TRUE)
    ok <- try({ a <- Make_Path(a); TRUE }, silent = TRUE)
    setTimeLimit(elapsed = Inf, transient = FALSE)
    if (inherits(ok, "try-error")) cat("  Make_Path abgebrochen -- Pfadmetriken entfallen\n")
  } else {
    cat(sprintf("  %d Zylinder > %d: Make_Path uebersprungen (Pfadmetriken entfallen)\n",
                n_cyl, max_cyl_paths))
  }
  write_aRchi(a, cache)
}

qsm <- get_QSM(a)
setDT(qsm)

# --- Metriken ---------------------------------------------------------------
saveget <- function(expr, default = NA) {
  r <- try(suppressWarnings(eval(expr)), silent = TRUE)
  if (inherits(r, "try-error") || length(r) == 0) default else r
}
num1 <- function(x) if (is.null(x) || all(is.na(x))) NA_real_ else
  round(as.numeric(if (is.data.frame(x)) x[[ncol(x)]][1] else x[1]), 4)

# TreeVolume() summiert QSM$Volume (gross geschrieben). add_radius() legt die
# Spalte aber als "volume" an -- die Gross-/Kleinschreibung passt in aRchi 2.1.4
# nicht zusammen, und weil sum(NULL) in R 0 ergibt, liefert TreeVolume()
# stillschweigend 0 statt eines Fehlers. Daher direkt die vorhandene Spalte.
stopifnot(all(c("radius", "length", "volume") %in% names(qsm)))
if (all(qsm$radius == 0)) stop("add_radius() hat keine Radien geliefert")
qsm[, vol_m3 := volume]

pf    <- saveget(quote(PathFraction(a)))
fork  <- saveget(quote(ForkRate(a)))
surf  <- saveget(quote(WoodSurface(a)))
wbe   <- saveget(quote(WBEparameters(a)))

hoehe <- max(qsm$endZ, na.rm = TRUE) - min(qsm$startZ, na.rm = TRUE)
ordnungen <- if ("branching_order" %in% names(qsm))
  as.integer(max(qsm$branching_order, na.rm = TRUE)) else NA_integer_
n_zyl <- nrow(qsm)
vol_gesamt_l <- round(sum(qsm$vol_m3, na.rm = TRUE) * 1000, 2)

# Volumen je Verzweigungsordnung -- zeigt, wo das Holz sitzt (Stamm vs. Krone)
vol_ord <- NULL
if ("branching_order" %in% names(qsm)) {
  vo <- qsm[, .(volumen_l = round(sum(vol_m3) * 1000, 2), zylinder = .N),
            by = branching_order][order(branching_order)]
  vol_ord <- lapply(seq_len(nrow(vo)), function(i)
    list(ordnung = as.integer(vo$branching_order[i]),
         volumen_l = vo$volumen_l[i], zylinder = as.integer(vo$zylinder[i])))
}

# Stammdurchmesser in Brusthoehe direkt aus dem Modell -- unabhaengige
# Gegenprobe zum Kreis-Fit aus seed_syssifoss.py
# Zylinder, die die 1,3-m-Ebene schneiden; ein einzelner Treffer ist Zufall,
# daher ein 20-cm-Fenster um Brusthoehe.
bh <- qsm[startZ <= 1.4 & endZ >= 1.2 & branching_order <= 1]
bhd_qsm <- if (nrow(bh)) round(2 * median(bh$radius) * 100, 1) else NA_real_

res <- list(
  baum = basename(laz),
  punkte = list(gesamt = n_all, holz = n_wood,
                holz_anteil_pct = round(100 * n_wood / n_all, 1),
                verwendet = nrow(dt),
                quelle_holz = "LAS-classification 0 = Holz (manuell annotiert, Ground Truth)"),
  modell = list(paket = paste("aRchi", as.character(packageVersion("aRchi"))),
                voxel_m = voxel, zylinder = n_zyl,
                max_verzweigungsordnung = ordnungen),
  metriken = list(
    hoehe_holz_m = round(hoehe, 2),
    holzvolumen_l = vol_gesamt_l,
    holzoberflaeche_m2 = num1(surf),
    bhd_aus_qsm_cm = bhd_qsm,
    path_fraction = num1(pf),
    gabelungsrate = num1(fork)
  ),
  volumen_je_ordnung = vol_ord,
  wbe = if (is.data.frame(wbe)) as.list(round(wbe[1, sapply(wbe, is.numeric)], 4)) else NULL,
  limits = paste(
    "Einzelscan-QSM: verdeckte Kronenteile fehlen, das Holzvolumen ist damit",
    "eher eine Untergrenze. Die Radien stammen aus dem Median je 0,5-m-Abschnitt",
    "-- an duennen Aesten unterhalb der Punktdichte wird der Radius systematisch",
    "ueberschaetzt. Fuer belastbare Volumina gegen geerntete Referenzbaeume oder",
    "TreeQSM/SimpleForest gegenpruefen."
  )
)

write(toJSON(res, auto_unbox = TRUE, pretty = TRUE, digits = 6, na = "null"), out_json)
cat(sprintf("   %d Zylinder, Ordnung bis %s, Holzhoehe %.1f m\n", n_zyl,
            as.character(ordnungen), hoehe))
cat(sprintf("   Volumen %.1f l, Oberflaeche %.1f m2, BHD(QSM) %s cm, PathFraction %s\n",
            vol_gesamt_l, num1(surf), as.character(bhd_qsm), as.character(num1(pf))))
