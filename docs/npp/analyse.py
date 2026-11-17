"""Requirements: python3, numpy, pandas, scikit-learn.
Run: python analyse.py  (downloads the database if missing and writes result.json, the data shown in index.html)

Exemplary analysis: N deposition, biomass production and allocation in
temperate and cold (boreal/continental) forests.
Data: Rodal, Luyssaert, Balzarolo & Campioli (2025) Sci Data 12:1534,
figshare doi:10.6084/m9.figshare.29085488 (CC BY 4.0)."""
import json, sqlite3, numpy as np, pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import RepeatedKFold, cross_val_score
from sklearn.inspection import permutation_importance

import os, urllib.request
DB = 'npp.db'
if not os.path.exists(DB):  # NetPrimaryProduction.db from figshare (CC BY 4.0)
    urllib.request.urlretrieve('https://ndownloader.figshare.com/files/56802545', DB)
c = sqlite3.connect(DB)
si = pd.read_sql('select * from site_information', c)
si['lat'] = np.where(si.north_south == 'S', -si.latitude, si.latitude)
si['lon'] = np.where(si.east_west == 'W', -si.longitude, si.longitude)
for_ = si[(si.biome == 'forest') & si.climate_region.isin(['temperate', 'cold'])].copy()

npp = pd.read_sql('select * from NPP_estimates', c)
npp = npp[npp.site_ID.isin(for_.site_ID)].copy()
npp['year'] = npp.end_year

# N deposition: nearest available year per measurement, kgN km-2 yr-1 -> kg N ha-1 yr-1
nd = pd.read_sql('select site_ID, year, total_Ndep from Ndep', c)
def ndep(row):
    d = nd[nd.site_ID == row.site_ID]
    if d.empty: return np.nan
    return d.iloc[(d.year - row.year).abs().argsort().iloc[0]].total_Ndep / 100
npp['ndep'] = npp.apply(ndep, axis=1)
npp['bnpp_frac'] = npp.BNPP / npp.NPP_tot1
npp.loc[(npp.bnpp_frac <= 0) | (npp.bnpp_frac >= 1), 'bnpp_frac'] = np.nan
npp['wood_frac'] = npp.ANPP_wood / npp.NPP_tot1

site = npp.groupby('site_ID').agg(npp=('NPP_tot1', 'mean'), bnpp=('BNPP', 'mean'),
                                  bnpp_frac=('bnpp_frac', 'mean'), wood_frac=('wood_frac', 'mean'),
                                  ndep=('ndep', 'mean'), n_meas=('measurement_ID', 'count')).reset_index()

bc = pd.read_sql('select site_ID, bio1, bio12, AI from BioClim', c)
hw = pd.read_sql('select site_ID, sequence, share, pH_water, CN_ratio, sand, total_N from HWSD', c)
hw = hw.sort_values(['site_ID', 'share'], ascending=[True, False]).groupby('site_ID').first().reset_index()
fe = pd.read_sql('select site_ID, fertility_status from site_fertility', c).drop_duplicates('site_ID')

d = (for_[['site_ID', 'plot_name', 'climate_region', 'dominant_functional_types', 'dominant_species',
           'management_code', 'lat', 'lon', 'elevation']]
     .merge(site, on='site_ID', how='inner').merge(bc, on='site_ID', how='left')
     .merge(hw[['site_ID', 'pH_water', 'CN_ratio', 'sand']], on='site_ID', how='left')
     .merge(fe, on='site_ID', how='left'))
d['evergreen'] = d.dominant_functional_types.fillna('').str.contains('evergreen').astype(int)
d['managed'] = (d.management_code == 'M').astype(int)
d['fert'] = d.fertility_status.map({'L': 0, 'M': 1, 'H': 2})
for col in ['pH_water', 'CN_ratio', 'sand']:
    d.loc[d[col] < 0, col] = np.nan  # HWSD missing-value codes

feat = {'ndep': 'N deposition', 'bio1': 'Mean annual temperature', 'bio12': 'Annual precipitation',
        'AI': 'Aridity index', 'pH_water': 'Soil pH', 'CN_ratio': 'Soil C:N', 'sand': 'Sand content',
        'managed': 'Management', 'evergreen': 'Evergreen vs deciduous'}

def rf_rank(target):
    x = d.dropna(subset=[target] + list(feat))
    X, y = x[list(feat)].values, x[target].values
    rf = RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=1)
    cv = cross_val_score(rf, X, y, cv=RepeatedKFold(n_splits=5, n_repeats=10, random_state=1), scoring='r2')
    rf.fit(X, y)
    pi = permutation_importance(rf, X, y, n_repeats=50, random_state=1)
    imp = sorted(zip(feat.values(), pi.importances_mean, pi.importances_std), key=lambda t: -t[1])
    return dict(n=len(x), r2=float(cv.mean()), r2_sd=float(cv.std()),
                importance=[dict(name=n, mean=float(m), sd=float(s)) for n, m, s in imp])

res = {'npp': rf_rank('npp'), 'bnpp_frac': rf_rank('bnpp_frac')}
summ = {
    'n_sites': int(len(d)), 'n_cold': int((d.climate_region == 'cold').sum()),
    'n_temperate': int((d.climate_region == 'temperate').sum()),
    'n_meas': int(d.n_meas.sum()), 'n_managed': int(d.managed.sum()),
}
for k in ['npp', 'bnpp_frac', 'ndep']:
    summ[k + '_median'] = float(d[k].median())
sp = d[['ndep', 'bnpp_frac']].dropna()
summ['spearman_ndep_bnppfrac'] = float(sp.corr(method='spearman').iloc[0, 1])
summ['n_spearman'] = int(len(sp))
sp2 = d[['ndep', 'npp']].dropna()
summ['spearman_ndep_npp'] = float(sp2.corr(method='spearman').iloc[0, 1])

cols = ['site_ID', 'plot_name', 'climate_region', 'dominant_species', 'managed', 'evergreen', 'lat', 'lon',
        'npp', 'bnpp', 'bnpp_frac', 'wood_frac', 'ndep', 'bio1', 'bio12', 'n_meas']
sites = d[cols].round(4).replace({np.nan: None}).to_dict('records')
json.dump({'summary': summ, 'rf': res, 'sites': sites}, open('result.json', 'w'))
print(json.dumps({'summary': summ, 'rf': res}, indent=1))
