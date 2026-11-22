"""Gekapselte Bruecke zu R (nur fuer Dinge, die es nur in R gibt: Hmsc, spOccupancy, CAST-Abgleich).

Das MVP laeuft OHNE R. Austausch ausschliesslich ueber CSV-Dateien in einem Arbeitsordner und
`Rscript`; keine R-Objekte im Python-Prozess. Fehlt R oder ein Paket, gibt es eine klare Meldung.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd


class RNotAvailable(RuntimeError):
    pass


def rscript():
    exe = shutil.which("Rscript")
    if not exe:
        raise RNotAvailable("Rscript nicht gefunden. R installieren (https://cran.r-project.org) - fuer das MVP nicht noetig.")
    return exe


def has_package(pkg: str) -> bool:
    try:
        r = subprocess.run([rscript(), "-e", f"quit(status = !requireNamespace('{pkg}', quietly=TRUE))"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except RNotAvailable:
        return False


def run_r(code: str, inputs: dict[str, pd.DataFrame], outputs: list[str], timeout=3600) -> dict[str, pd.DataFrame]:
    """Fuehrt R-Code aus. inputs werden als <name>.csv bereitgestellt, outputs als <name>.csv zurueckgelesen.
    Im R-Code steht der Arbeitsordner in der Variable `wd`."""
    exe = rscript()
    with tempfile.TemporaryDirectory(prefix="bioscale_r_") as wd:
        for n, df in inputs.items():
            df.to_csv(Path(wd) / f"{n}.csv", index=False)
        script = Path(wd) / "job.R"
        script.write_text(f'wd <- "{Path(wd).as_posix()}"\n' + code, encoding="utf-8")
        r = subprocess.run([exe, str(script)], capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"R-Fehler:\n{r.stderr[-3000:]}")
        return {n: pd.read_csv(Path(wd) / f"{n}.csv") for n in outputs}


CAST_AOA = r"""
library(CAST)
tr <- read.csv(file.path(wd, "train.csv")); nw <- read.csv(file.path(wd, "new.csv"))
w <- read.csv(file.path(wd, "weights.csv")); f <- read.csv(file.path(wd, "folds.csv"))$fold
folds <- lapply(sort(unique(f)), function(k) which(f == k))
wt <- as.data.frame(t(w$weight)); names(wt) <- w$variable
tdi <- trainDI(train = tr, weight = wt, CVtest = folds)
a <- aoa(newdata = nw, trainDI = tdi)
write.csv(data.frame(DI = a$DI, AOA = a$AOA, threshold = tdi$threshold), file.path(wd, "out.csv"), row.names = FALSE)
"""


def cast_aoa(train: pd.DataFrame, new: pd.DataFrame, weights: dict, folds) -> pd.DataFrame:
    """Referenzrechnung mit CAST (zum Abgleich der Python-Umsetzung)."""
    w = pd.DataFrame({"variable": list(weights), "weight": list(weights.values())})
    return run_r(CAST_AOA, {"train": train, "new": new, "weights": w, "folds": pd.DataFrame({"fold": folds})}, ["out"])["out"]


SPOCC_NULL = r"""
library(spOccupancy)
y <- as.matrix(read.csv(file.path(wd, "y.csv")))
occ <- read.csv(file.path(wd, "occ.csv"))
data <- list(y = y, occ.covs = occ)
form <- as.formula(paste("~", paste(names(occ), collapse = "+")))
m <- PGOcc(occ.formula = form, det.formula = ~ 1, data = data, n.samples = 5000, n.burn = 2000, n.thin = 5, verbose = FALSE)
s <- summary(m)
write.csv(data.frame(psi_mean = colMeans(m$psi.samples)), file.path(wd, "psi.csv"), row.names = FALSE)
"""


def spoccupancy_fit(y: pd.DataFrame, occ_covs: pd.DataFrame) -> pd.DataFrame:
    """Phase 2: Occupancy-Modell mit spOccupancy (Begehungen x Standorte)."""
    return run_r(SPOCC_NULL, {"y": y, "occ": occ_covs}, ["psi"])["psi"]
