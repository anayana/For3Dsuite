import os

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin


def pytest_collection_modifyitems(config, items):
    if os.environ.get("BIOSCALE_NETWORK") == "1":
        return
    skip = pytest.mark.skip(reason="Netztest: mit BIOSCALE_NETWORK=1 ausfuehren")
    for it in items:
        if "network" in it.keywords:
            it.add_marker(skip)


@pytest.fixture(scope="session")
def world():
    from bioscale.synthetic import make_world
    return make_world(seed=42)


def write_tif(path, arr, x0, y0, res, crs="EPSG:25832", nodata=None, dtype=None):
    arr = np.asarray(arr)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype=dtype or arr.dtype.name, crs=crs, transform=from_origin(x0, y0, res, res),
                       nodata=nodata) as d:
        d.write(arr.astype(dtype or arr.dtype.name), 1)
    return path
