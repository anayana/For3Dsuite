"""Gesamtkette: occurrence -> covariates -> multiscale -> model -> validate -> aoa -> sampling -> report."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import aoa as A
from . import model as M
from . import sampling as S
from . import validate as V
from .covariates import CovariateStack, Layer
from .grid import Grid, aggregate, area_mask, write_raster
from .multiscale import radius_list
from .occurrence import coarsen_xy, load_observations, occupancy_null, read_area, visit_matrix
from .profiles import load_profile, merge_overrides
from .project import load_project
from .provenance import LayerRecord


class Log:
    def __init__(self, echo=True):
        self.lines, self.echo, self.t0 = [], echo, time.time()

    def __call__(self, msg):
        line = f"[{time.time() - self.t0:6.1f}s] {msg}"
        self.lines.append(line)
        if self.echo:
            print(line, flush=True)


# ------------------------------------------------------------------ Einflussgroessen
def build_covariates(cfg, grid: Grid, base: Path, log) -> tuple[CovariateStack, dict, list]:
    cov = cfg["covariates"]
    st = CovariateStack(grid=grid, kernel=cov.get("kernel", "gauss"))
    warnings_, extra = [], {}
    for L in cov.get("local") or []:
        st.add_file(base / L["path"], L.get("name") or Path(L["path"]).stem, L.get("group", "other"),
                    L.get("kind", "continuous"), source=L.get("source", "Nutzerdatei"))
        log(f"Raster geladen: {L['path']} -> {L.get('name')}")
    od = cov.get("open") or {}
    period = cfg.get("period") or {}
    cache_key = None
    if od and cov.get("cache", True):
        import hashlib
        cache_key = hashlib.sha1(json.dumps([grid.to_dict(), od, period], sort_keys=True, default=str).encode()).hexdigest()[:12]
        cache_dir = base / "cache" / "offene_daten" / cache_key
    if cache_key and (cache_dir / "layers.npz").exists():
        from .provenance import LayerRecord as _LR
        arrs = np.load(cache_dir / "layers.npz")
        meta = json.loads((cache_dir / "layers.json").read_text(encoding="utf-8"))
        for m in meta:
            rec = _LR(**m["record"])
            rec.processing = rec.processing + [f"aus Cache {cache_key}"]
            st.layers[m["name"]] = Layer(m["name"], arrs[m["name"]], m["group"], m["kind"], m["multiscale"])
            st.provenance.add(rec)
        log(f"Offene Daten aus Cache geladen ({len(meta)} Layer, {cache_dir}).")
        od = {}
    before = set(st.layers)
    if od.get("sentinel2"):
        o = od["sentinel2"] if isinstance(od["sentinel2"], dict) else {}
        try:
            from .covariates import intensity, opendata
            lay, recs, series = opendata.sentinel2_stack(grid, period["start"], period["end"],
                                                         cloud_max=o.get("cloud_max", 60),
                                                         endpoint=o.get("endpoint", opendata.EARTH_SEARCH), log=log)
            for r in recs:
                st.add(Layer(r.name, lay[r.name], "spectral"), r)
            for nm, arr in intensity.intensity_layers(series).items():
                st.add(Layer(nm, arr, "intensity"), LayerRecord(name=nm, source="abgeleitet aus Sentinel-2-Zeitreihe",
                                                                group="intensity", processing=["bioscale.covariates.intensity"]))
        except Exception as e:
            warnings_.append(f"Sentinel-2 konnte nicht geladen werden ({type(e).__name__}: {e}). Ohne Sentinel-2 weitergerechnet.")
    if od.get("sentinel1"):
        o = od["sentinel1"] if isinstance(od["sentinel1"], dict) else {}
        try:
            from .covariates import opendata
            lay, recs, _ = opendata.sentinel1_stack(grid, period["start"], period["end"],
                                                    endpoint=o.get("endpoint", opendata.PLANETARY_COMPUTER),
                                                    collection=o.get("collection", "sentinel-1-rtc"), log=log)
            for r in recs:
                st.add(Layer(r.name, lay[r.name], "structure"), r)
        except Exception as e:
            warnings_.append(f"Sentinel-1 konnte nicht geladen werden ({type(e).__name__}: {e}).")
    if od.get("dem"):
        try:
            from .covariates import opendata
            elev, rec = opendata.copernicus_dem(grid)
            st.add(Layer("elevation", elev, "topography"), rec)
            for nm, arr in opendata.terrain(elev, grid.res).items():
                st.add(Layer(nm, arr, "topography"), LayerRecord(name=nm, source="abgeleitet aus Copernicus DEM",
                                                                 group="topography", processing=["bioscale terrain()"]))
            log("Copernicus DEM + Gelaendeableitungen geladen.")
        except Exception as e:
            warnings_.append(f"Hoehenmodell konnte nicht geladen werden ({type(e).__name__}: {e}).")
    if od.get("worldcover"):
        try:
            from .covariates import opendata
            wc, rec = opendata.worldcover(grid)
            st.add(Layer("worldcover", wc, "landcover", "categorical"), rec)
            log("ESA WorldCover geladen.")
        except Exception as e:
            warnings_.append(f"WorldCover konnte nicht geladen werden ({type(e).__name__}: {e}).")
    for prod, p in (od.get("hrl") or {}).items():
        from .covariates import opendata
        arr, rec, spec = opendata.hrl_layer(base / p, prod, grid)
        st.add(Layer(rec.name, arr, spec["group"], spec["kind"]), rec)
    if od.get("dwd"):
        from .covariates import opendata
        for var in (od["dwd"] if isinstance(od["dwd"], list) else ["air_temperature_mean", "precipitation"]):
            try:
                arr, rec = opendata.dwd_multi_annual(grid, var, cache_dir=str(base / "cache" / "dwd"))
                st.add(Layer(rec.name, arr, "climate", multiscale=False), rec)
            except Exception as e:
                warnings_.append(f"DWD {var} konnte nicht geladen werden ({type(e).__name__}: {e}).")
    if cache_key and od:
        newl = [n for n in st.layers if n not in before]
        if newl:
            from dataclasses import asdict
            cache_dir.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache_dir / "layers.npz", **{n: st.layers[n].array for n in newl})
            meta = [dict(name=n, group=st.layers[n].group, kind=st.layers[n].kind, multiscale=st.layers[n].multiscale,
                         record=asdict(st.provenance.records[n])) for n in newl if n in st.provenance.records]
            (cache_dir / "layers.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    if cov.get("als"):
        from .covariates import als
        paths = [base / p for p in cov["als"].get("paths", [])]
        lay, recs, extra_als = als.als_metrics(paths, grid, cov["als"].get("res", 1.0), log=log)
        for r in recs:
            st.add(Layer(r.name, lay[r.name], "structure"), r)
        extra["als"] = extra_als
        log(f"ALS-Metriken berechnet: {', '.join(lay)}")
    if cov.get("access"):
        a = cov["access"]
        st.add_file(base / a["path"], a.get("name", "access"), "access", "continuous")
        extra["access"] = a.get("name", "access")
    return st, extra, warnings_


# ------------------------------------------------------------------ Hauptlauf
def run(project_path, out_dir=None, echo=True, make_report=True) -> dict:
    log = Log(echo)
    cfg = load_project(project_path)
    base = Path(cfg["_base"])
    out = Path(out_dir) if out_dir else base / cfg.get("output", "ergebnis")
    out.mkdir(parents=True, exist_ok=True)
    mc = cfg["model"]
    seed = int(mc.get("seed", 0))
    warn = []

    prof = merge_overrides(load_profile(cfg["question"]["profile"] if not str(cfg["question"]["profile"]).endswith(".yml")
                                        else base / cfg["question"]["profile"]), cfg["question"].get("profile_overrides"))
    log(f"Profil: {prof['label']} - Wirkradius {prof['radius_m'][0]}-{prof['radius_m'][1]} m ({prof['status']})")

    # Gebiet + Raster
    geom = read_area(base / cfg["area"], cfg["crs"])
    grid = Grid.from_bounds(geom.bounds, float(cfg["resolution_m"]), cfg["crs"])
    mask = area_mask(grid, geom)
    log(f"Analyseraster: {grid.width} x {grid.height} Zellen a {grid.res:g} m, {mask.sum() * grid.res ** 2 / 1e4:.0f} ha")

    # Punktdaten
    target = cfg["question"].get("target", "occurrence")
    occ_cfg = dict(cfg["occurrence"])
    if target == "abundance":
        occ_cfg["type"] = "counts"
    obs = load_observations(occ_cfg, cfg["question"].get("species") or "", cfg["crs"], base, geom, cfg.get("period"),
                            cfg["sensitive"].get("taxa"), target="richness" if target == "richness" else "occurrence")
    if target == "richness":
        filt = cfg["occurrence"].get("taxon_filter")
        obs.species = "Artenzahl" + (f" ({', '.join(f'{k}={v}' for k, v in filt.items())})" if filt else "")
    obs.sensitive = obs.sensitive or bool(prof.get("sensitive"))
    if obs.n_events < 5:
        raise ValueError(f"Zu wenige Daten fuer '{obs.species}': {obs.n} Standorte, {obs.n_events} Ereignisse "
                         "(mindestens 5 Nachweise und 5 Fehlen bzw. 5 Vorkommen). Artname und Datei pruefen.")
    warn += obs.issues
    log(f"Punktdaten: {obs.n} Standorte, Typ {obs.dtype}, {obs.n_events} Ereignisse" + (" - SENSIBEL" if obs.sensitive else ""))

    # Einflussgroessen
    stack, extra, w_cov = build_covariates(cfg, grid, base, log)
    warn += w_cov
    groups = set(prof["variable_groups"])
    bases = [n for n, L in stack.layers.items() if L.group in groups]
    skipped = [n for n, L in stack.layers.items() if L.group not in groups and L.group != "access"]
    if skipped:
        log(f"Nicht im Profil vorgesehen (nicht verwendet): {', '.join(skipped)}")
    if not bases:
        raise ValueError("Keine Einflussgroessen passend zum Profil. Raster/Offene Daten in der Projektdatei angeben.")
    rmin, rmax = prof["radius_m"]
    radii = radius_list(rmin, rmax, int(prof.get("n_radii", 8)), grid.res)
    radii_by_base = {b: (radii if stack.layers[b].multiscale else [0.0]) for b in bases}
    log(f"Radien je Variable: {', '.join(f'{r:g}' for r in radii)} m (Kernel {stack.kernel}, r = 2 Sigma)")

    # Datensatz
    s = obs.sites
    xy = s[["x", "y"]].values
    X_, Y_ = grid.cell_centers()
    cell_xy = np.column_stack([X_[mask], Y_[mask]])
    if obs.dtype == "presence_only":
        rng = np.random.default_rng(seed)
        if obs.background is not None and len(obs.background) >= 30:
            bg = obs.background[["x", "y"]].values
            bg_note = f"Zielgruppen-Hintergrund ({len(bg)} Fundpunkte anderer Arten, gleicher Erfassungs-Bias)"
        else:
            n_bg = min(5000, len(cell_xy))
            p = None
            if extra.get("access"):
                d = stack.layers[extra["access"]].array[mask]
                dp = grid.sample(stack.layers[extra["access"]].array, xy[:, 0], xy[:, 1])
                h_pts, edges = np.histogram(dp[np.isfinite(dp)], bins=10, range=(0, np.nanmax(d)))
                h_area, _ = np.histogram(d[np.isfinite(d)], bins=edges)
                ratio = (h_pts + 0.5) / (h_area + 0.5)
                p = ratio[np.clip(np.digitize(d, edges[1:-1]), 0, 9)]
                p = np.where(np.isfinite(p), p, 0)
                p = p / p.sum()
                bg_note = "Zufallshintergrund, gewichtet nach Abstand zu Wegen (Bias-Korrektur)"
            else:
                bg_note = "Zufallshintergrund im Gebiet (keine Bias-Korrektur moeglich - Wege/Zielgruppe angeben!)"
                warn.append("Nur-Vorkommen ohne Zielgruppen-Hintergrund oder Wegelayer: Erfassungs-Bias wird nicht korrigiert.")
            bg = cell_xy[rng.choice(len(cell_xy), n_bg, replace=False, p=p)]
        xy_all = np.vstack([xy, bg])
        y = np.r_[np.ones(len(xy)), np.zeros(len(bg))]
        ds = M.Dataset(y, xy_all, np.ones(len(y)), "presence_only")
        log(bg_note)
        warn.append("Nur-Vorkommen-Daten: Die Karte zeigt relative Eignung, keine Vorkommenswahrscheinlichkeit.")
    else:
        y = s["response"].values.astype(float)
        vm0 = visit_matrix(s)
        vis = vm0.astype(float) if (vm0 is not None and vm0.shape[1] >= 2 and obs.dtype == "presence_absence") else None
        ds = M.Dataset(y, xy, s["effort"].values.astype(float), obs.dtype, visits=vis)
        bg_note = None

    # Pruef-Folds
    k = int(mc.get("folds", 5))
    if mc.get("cv", "knndm") == "knndm":
        f_pts, kinfo = V.knndm_folds(xy, cell_xy, k, seed)
    else:
        bs = float(mc.get("block_size_m", rmax))
        f_pts, kinfo = V.block_folds(xy, bs, k, seed), {"block_size_m": bs}
    if obs.dtype == "presence_only":
        from scipy.spatial import cKDTree
        folds = np.r_[f_pts, f_pts[cKDTree(xy).query(ds.xy[len(xy):])[1]]]
    else:
        folds = f_pts
    f_rand = V.random_folds(len(ds.y), k, seed)
    log(f"Raeumliche Pruefung: {mc.get('cv', 'knndm')}, {k} Folds" +
        (f", {kinfo.get('n_clusters')} Cluster (W = {kinfo['W']:.0f} vs. zufaellig {kinfo['W_random']:.0f})" if "W" in kinfo else ""))

    # Merkmale an Punkten
    pf = stack.sample_features(radii_by_base, ds.xy[:, 0], ds.xy[:, 1])
    okrow = np.all(np.column_stack([np.isfinite(v) for v in pf.values()]), 1)
    if (~okrow).any():
        warn.append(f"{int((~okrow).sum())} Datenpunkte ohne vollstaendige Einflussgroessen (Rand/Luecken) entfernt.")
        ds = ds.sub(okrow)
        folds, f_rand = folds[okrow], f_rand[okrow]
        pf = {kk: v[okrow] for kk, v in pf.items()}
        _, folds = np.unique(folds, return_inverse=True)
    n_events = int(min((ds.y > 0).sum(), (ds.y == 0).sum())) if ds.dtype != "counts" else int((ds.y > 0).sum())
    if obs.dtype == "presence_only":
        n_events = int((ds.y == 1).sum())
    max_feat = max(1, n_events // int(mc.get("events_per_variable", 10)))

    chosen, rad_results, sel_notes = M.select_features(bases, radii_by_base, pf, ds, folds, max_feat,
                                                       float(mc.get("corr_max", 0.7)), seed)
    for r in rad_results:
        warn += [w for w in r.warnings if r.useful]
    log("Gewaehlt: " + ", ".join(f"{b}@{r:g} m" for b, r in chosen))

    # Modelle vergleichen (verschachtelte Pruefung)
    cand = [c for c in mc.get("candidates", ["glm", "rf"])]
    if obs.dtype == "presence_only" and "maxent" not in cand:
        cand = ["maxent"] + cand
    if ds.visits is not None and mc.get("occupancy", True) and "occ" not in cand:
        cand = cand + ["occ"]
        log("Wiederholte Begehungen vorhanden: Occupancy-Modell (Besetzung um Nicht-Nachweis korrigiert) wird mitgeprueft.")
    if "gbm" in cand:
        try:
            import lightgbm  # noqa: F401
        except ImportError:
            cand.remove("gbm"); warn.append("lightgbm nicht installiert - GBM uebersprungen.")
    cv_results = {}
    for kind in cand:
        p_sp, ch_sp = M.nested_cv(kind, bases, radii_by_base, pf, ds, folds, max_feat, seed, inner="same")
        p_rd, _ = M.nested_cv(kind, bases, radii_by_base, pf, ds, f_rand, max_feat, seed, inner="random")
        cv_results[kind] = dict(raeumlich=V.metrics(ds.dtype, ds.y, p_sp), zufaellig=V.metrics(ds.dtype, ds.y, p_rd),
                                p_spatial=p_sp, chosen_per_fold=[[f"{b}@{r:g}" for b, r in c] for c in ch_sp])
        log(f"{kind}: raeumlich {fmt_metrics(cv_results[kind]['raeumlich'])} | zufaellig {fmt_metrics(cv_results[kind]['zufaellig'])}")
    best = max(cand, key=lambda c: V.main_score(ds.dtype, cv_results[c]["raeumlich"]))
    if "occ" in cand and best != "occ":
        # Occupancy liefert die eigentlich gesuchte Groesse (wahre Besetzung). Bevorzugen, wenn es in der
        # raeumlichen Pruefung nicht deutlich schlechter vorhersagt (Devianz-Unterschied < 0.02).
        d = V.main_score(ds.dtype, cv_results[best]["raeumlich"]) - V.main_score(ds.dtype, cv_results["occ"]["raeumlich"])
        if d < float(mc.get("occupancy_tolerance", 0.02)):
            log(f"Occupancy-Modell gewaehlt (Vorhersage fast gleich gut wie {best}, Unterschied {d:.3f}), "
                "weil es die um Nicht-Nachweis korrigierte Besetzung liefert.")
            best = "occ"
    log(f"Bestes Modell (raeumliche Pruefung): {best}")

    # Endmodell
    Xp = np.column_stack([pf[c] for c in chosen])
    final = M.Model(best, ds.dtype, seed).fit(Xp, ds.target, ds.fit_weight, ds.visits)
    occ_model = dict(p=final.m.p) if best == "occ" else None
    if occ_model:
        log(f"Occupancy-Modell: Nachweis je Begehung p = {occ_model['p']:.2f}; Karte = Besetzungswahrscheinlichkeit psi")
    imp = M.permutation_importance(final, Xp, ds, seed=seed)
    stack._cache.clear()
    Xc = stack.matrix(chosen, mask)
    ok_cells = np.all(np.isfinite(Xc), 1)
    ref_eff = float(np.median(ds.effort)) if ds.dtype == "counts" else 1.0
    pred = np.full(len(Xc), np.nan)
    pred[ok_cells] = final.predict(Xc[ok_cells]) * ref_eff
    from sklearn.cluster import KMeans
    ncl = max(5, min(len(ds.y) // 4, 60))
    clusters = KMeans(n_clusters=ncl, n_init=3, random_state=seed).fit_predict(ds.xy)
    nb = int(mc.get("bootstrap", 20))
    boot = M.cluster_bootstrap(best, Xp, ds, Xc[ok_cells], nb, seed, clusters) * ref_eff
    sd = np.full(len(Xc), np.nan); lo = sd.copy(); hi = sd.copy()
    sd[ok_cells] = boot.std(0)
    lo[ok_cells], hi[ok_cells] = np.percentile(boot, [5, 95], axis=0)

    # Gueltigkeitsbereich
    aoa_m = A.train_di(Xp, imp, folds, [f"{b}@{r:g}m" for b, r in chosen])
    aoa_c, di_c = aoa_m.aoa(Xc)
    aoa_frac = float(np.nanmean(aoa_c))
    log(f"Gueltigkeitsbereich: {100 * aoa_frac:.0f} % der Flaeche (DI-Schwelle {aoa_m.threshold:.3f})")

    def to_map(v):
        a = np.full(grid.shape, np.nan, "float32")
        a[mask] = v
        return a

    maps = dict(vorhersage=to_map(pred), unsicherheit_sd=to_map(sd), q05=to_map(lo), q95=to_map(hi),
                aoa=to_map(aoa_c), di=to_map(di_c))
    maps["vorhersage_im_aoa"] = np.where(maps["aoa"] == 1, maps["vorhersage"], np.nan).astype("float32")

    # Repraesentativitaet + Vorschlaege
    names = [f"{b}@{r:g} m" for b, r in chosen]
    pts_idx = ds.y > 0 if obs.dtype == "presence_only" else np.ones(len(ds.y), bool)
    cov_tab = S.coverage_table(names, Xp[pts_idx], Xc[ok_cells])
    bias = None
    if extra.get("access"):
        acc = stack.layers[extra["access"]].array
        bias = S.access_bias(grid.sample(acc, s.x.values, s.y.values), acc[mask])
        if bias and bias["verzerrt"]:
            warn.append(f"Standorte liegen deutlich naeher an Wegen als das Gebiet im Mittel "
                        f"(Median {bias['median_punkte']:.0f} m vs. {bias['median_gebiet']:.0f} m): Erfassungs-Bias.")
    sugg = S.suggest_sites(aoa_m, Xc, cell_xy, int(cfg["sampling"].get("n_suggestions", 10)),
                           cfg["sampling"].get("min_distance_m") or 2 * rmin + 2 * grid.res, seed=seed)
    log(f"{len(sugg)} neue Standorte vorgeschlagen" + (f", AOA danach {100 * sugg[-1]['aoa_anteil_danach']:.0f} % (Stichprobe)" if sugg else ""))

    # Erkennungswahrscheinlichkeit
    occ = None
    vm = visit_matrix(s)
    if vm is not None and vm.shape[1] >= 2 and obs.dtype != "presence_only":
        occ = occupancy_null(vm)
        log(f"Nachweis je Begehung p = {occ['p']:.2f}, kumuliert {occ['p_cum']:.2f}; Besetzung psi = {occ['psi']:.2f} (naiv {occ['naive']:.2f})")
        if occ["p_cum"] < 0.8:
            warn.append(f"Nachweiswahrscheinlichkeit nach {occ['mean_visits']:.1f} Begehungen nur {occ['p_cum']:.2f}: "
                        "Fehlen ist oft Nicht-Nachweis. Mehr Begehungen oder Occupancy-Modell (Phase 2).")
    elif obs.dtype != "presence_only":
        warn.append("Nur eine Begehung je Standort: Nachweiswahrscheinlichkeit nicht schaetzbar - 'Fehlen' kann Nicht-Nachweis sein.")

    # Leitplanken
    sp = cv_results[best]["raeumlich"]; rd = cv_results[best]["zufaellig"]
    warn += guardrails(obs.dtype, n_events, len(chosen), aoa_frac, sp, rd)
    ampel = traffic_light(obs.dtype, n_events, aoa_frac, sp)

    # Schreiben
    for nm, arr in maps.items():
        write_raster(out / "karten" / f"{nm}.tif", arr, grid)
    stack.save_layers(out / "einflussgroessen", chosen)
    pub = None
    if obs.sensitive:
        f = max(1, int(round(cfg["sensitive"].get("publish_resolution_m", 250) / grid.res)))
        pub = out / "veroeffentlichung"
        for nm in ("vorhersage_im_aoa", "unsicherheit_sd", "aoa"):
            write_raster(pub / f"{nm}_{int(f * grid.res)}m.tif", aggregate(maps[nm], f), grid)
        (out / "karten" / "NICHT_VEROEFFENTLICHEN.txt").write_text(
            "Sensible Art: Karten in diesem Ordner haben volle Aufloesung und koennen Standorte verraten.\n"
            "Zum Teilen nur den Ordner 'veroeffentlichung' verwenden.\n", encoding="utf-8")
        log(f"Sensible Art: vergroeberte Karten ({int(f * grid.res)} m) in {pub}")
    S.write_suggestions(sugg, grid.crs, out / "neue_standorte.gpkg", out / "neue_standorte.gpx")
    stack.provenance.save(out / "herkunft.json")

    pts_x, pts_y = s.x.values, s.y.values
    if obs.sensitive:
        pts_x, pts_y = coarsen_xy(pts_x, pts_y, float(cfg["sensitive"].get("coarsen_m", 1000)))
    result = dict(
        project=cfg.get("name", ""), species=obs.species, dtype=obs.dtype, n_sites=int(obs.n), n_events=n_events,
        sensitive=obs.sensitive, target=target, rarefy_k=obs.rarefy_k, occupancy_model=occ_model,
        profile={k: prof[k] for k in ("name", "label", "radius_m", "status", "hints", "references")},
        grid=grid.to_dict(), area_ha=float(mask.sum() * grid.res ** 2 / 1e4),
        radii=radii, chosen=[dict(variable=b, radius_m=r, wichtigkeit=float(i)) for (b, r), i in zip(chosen, imp)],
        radius_results=[r.__dict__ for r in rad_results], selection_notes=sel_notes,
        cv={k: {kk: vv for kk, vv in v.items() if kk != "p_spatial"} for k, v in cv_results.items()},
        best_model=best, cv_info={k: v for k, v in kinfo.items() if not isinstance(v, np.ndarray)},
        calibration=V.calibration_table(ds.y, np.clip(cv_results[best]["p_spatial"], 0, 1)) if ds.dtype != "counts" else None,
        aoa=dict(fraction=aoa_frac, threshold=aoa_m.threshold, d_bar=aoa_m.d_bar),
        coverage=cov_tab, access_bias=bias, suggestions=sugg, occupancy=occ, warnings=dedupe(warn),
        ampel=ampel, notes=obs.notes + ([bg_note] if bg_note else []), log=log.lines,
        provenance=stack.provenance.to_list(), ref_effort=ref_eff, outputs=str(out),
        published=str(pub) if pub else None,
    )
    if cfg.get("demo_truth"):
        result["truth"] = compare_truth(base / cfg["demo_truth"], maps, grid, base)
        log(f"Demo-Kontrolle: Korrelation mit Wahrheit im AOA {result['truth']['corr_aoa']:.2f}, ausserhalb {result['truth']['corr_out']:.2f}")
    result["coarsen_m"] = float(cfg["sensitive"].get("coarsen_m", 1000))
    (out / "ergebnis.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=_json), encoding="utf-8")
    if make_report:
        from .report import write_report
        rp = write_report(result, maps, grid, out, points=(pts_x, pts_y, s["response"].values), truth=None)
        log(f"Bericht: {rp}")
        result["report"] = str(rp)
    return result


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return str(o)


def dedupe(lst):
    seen, out = set(), []
    for x in lst:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def fmt_metrics(m):
    keys = ["AUC", "TSS", "Boyce"] if "AUC" in m else ["R2", "Deviance_erklaert", "Spearman"]
    return ", ".join(f"{k} {m[k]:.2f}" for k in keys if k in m and np.isfinite(m[k]))


def guardrails(dtype, n_events, n_vars, aoa_frac, sp, rd):
    w = []
    if n_events < 15:
        w.append(f"Sehr wenige Ereignisse ({n_events}): Ergebnis ist kaum belastbar.")
    elif n_events < 50:
        w.append(f"Wenige Ereignisse ({n_events}): nur einfache Modelle sinnvoll, Unsicherheit hoch.")
    if aoa_frac < 0.5:
        w.append(f"Nur {100 * aoa_frac:.0f} % des Gebiets liegen im Gueltigkeitsbereich - der Rest waere Extrapolation.")
    if "AUC" in sp and "AUC" in rd:
        gap = rd["AUC"] - sp["AUC"]
        if gap > 0.03:
            w.append(f"Zufaellige Pruefung waere zu optimistisch (AUC {rd['AUC']:.2f} statt {sp['AUC']:.2f} raeumlich).")
        if sp["AUC"] < 0.7:
            w.append(f"Raeumlich gepruefte Trennschaerfe schwach (AUC {sp['AUC']:.2f}).")
        cs = sp.get("Kalibrierung_Steigung", np.nan)
        if np.isfinite(cs) and (cs < 0.7 or cs > 1.4) and dtype != "presence_only":
            w.append(f"Kalibrierung maessig (Steigung {cs:.2f}; 1 = ideal): Wahrscheinlichkeiten nicht woertlich nehmen.")
    if "R2" in sp and sp.get("Deviance_erklaert", 0) < 0.1:
        w.append("Raeumlich geprueft wird kaum Devianz erklaert (< 10 %).")
    w.append("Korrelation ist keine Ursache: Die Karte zeigt statistische Zusammenhaenge im Untersuchungsraum, "
             "keine Wirkungen von Massnahmen. Uebertragung auf andere Gebiete ist unsicher.")
    return w


def traffic_light(dtype, n_events, aoa_frac, sp):
    perf = sp.get("AUC", np.nan) if "AUC" in sp else 0.5 + sp.get("Deviance_erklaert", 0)
    if n_events < 15 or aoa_frac < 0.3 or (np.isfinite(perf) and perf < 0.65):
        return "rot"
    if n_events >= 50 and aoa_frac >= 0.7 and perf >= 0.75:
        return "gruen"
    return "gelb"


def compare_truth(path, maps, grid, base):
    """Nur fuer den synthetischen Testfall: Karte gegen die bekannte Wahrheit."""
    from .grid import read_to_grid
    t = read_to_grid(path, grid)
    js = Path(path).with_suffix(".json")
    info = json.loads(js.read_text()) if js.exists() else {}
    a, p = maps["aoa"], maps["vorhersage"]
    ok_in = (a == 1) & np.isfinite(t) & np.isfinite(p)
    ok_out = (a == 0) & np.isfinite(t) & np.isfinite(p)
    c_in = float(np.corrcoef(t[ok_in], p[ok_in])[0, 1]) if ok_in.sum() > 10 else float("nan")
    c_out = float(np.corrcoef(t[ok_out], p[ok_out])[0, 1]) if ok_out.sum() > 10 else float("nan")
    mae_in = float(np.mean(np.abs(t[ok_in] - p[ok_in]))) if ok_in.any() else float("nan")
    mae_out = float(np.mean(np.abs(t[ok_out] - p[ok_out]))) if ok_out.any() else float("nan")
    return dict(info, corr=c_in, corr_aoa=c_in, corr_out=c_out, mae_aoa=mae_in, mae_out=mae_out)
