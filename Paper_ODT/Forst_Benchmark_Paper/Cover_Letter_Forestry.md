Angel Naya
Independent Researcher, Berlin, Germany
angel.naya@posteo.de

To the Editors of *Forestry: An International Journal of Forest Research*

Dear Editors,

please consider the enclosed manuscript, "How much of the stem must a terrestrial laser scanner see?
Diameter error as a function of circumferential coverage, and what it means for scan design", for
publication as an Original Article in *Forestry*.

Terrestrial laser scanning (TLS) inventories accept or reject a stem diameter depending on how much of
the stem circumference was scanned. 3DFin, published in *Forestry* in 2024, accepts a diameter only if
at least 9 of 16 angular sectors (202.5°) contain points. How much coverage is actually needed, and
whether one threshold suits all fitting methods, has not been quantified. The manuscript does this
with three complementary approaches:

- a Monte Carlo experiment with six circle and cylinder estimators under realistic perturbations
  (non-circular stems, outliers, registration offsets);
- HELIOS++ simulations of three stand densities and a stand with branches at breast height, with the
  visible arc computed geometrically and independently of point density (26 712 stem × scan-configuration
  cases plus 9 360 with branches);
- two open real datasets (SegmentedForests, LAUT) and 3DFin itself run on twelve real plots with
  simulated reduced coverage.

The main findings are directly relevant to inventory practice: the coverage threshold depends on the
estimator and on how well stem points are separated from branches; least-squares fits fail at any
coverage when branch points remain, whereas an arc-constrained RANSAC does not; 3DFin's rule keeps
accepted diameters accurate (88 % within 2 cm) but leaves about half of the stems without a diameter
even with four to six spread scan positions; and spreading scan positions matters more than adding
them.

All code, result tables and derived data are openly available (GitHub, archived on Zenodo); all
third-party data are openly licensed.

The manuscript is original, has not been published and is not under consideration elsewhere. The
author declares no competing interests and received no specific funding.

Yours sincerely,

Angel Naya
