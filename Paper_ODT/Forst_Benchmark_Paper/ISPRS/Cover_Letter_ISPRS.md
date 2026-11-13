Angel Naya
Independent Researcher, Berlin, Germany
angel.naya@posteo.de

To the Editors-in-Chief, *ISPRS Journal of Photogrammetry and Remote Sensing*

Dear Editor,

please consider the enclosed manuscript, "How much of the stem must a terrestrial laser scanner see?
Diameter error as a function of circumferential coverage, and what it means for scan design", for
publication as a research article in the *ISPRS Journal of Photogrammetry and Remote Sensing*.

Diameters at breast height derived from terrestrial laser scanning (TLS) are fitted to the part of the
stem circumference that the scanner recorded. Processing software therefore applies coverage rules;
3DFin, for example, accepts a diameter only if at least 9 of 16 angular sectors (202.5°) contain points.
How much coverage is actually needed, whether one threshold suits all fitting methods, and what such a
rule costs in completeness have not been quantified. The manuscript addresses these questions with
three complementary approaches:

- a Monte Carlo experiment with six circle and cylinder estimators under non-circular cross-sections,
  outliers and registration offsets;
- HELIOS++ simulations of three stand densities and of a stand with branches at breast height, in which
  the visible arc of every stem is computed geometrically;
- two open real datasets (SegmentedForests, LAUT) and a run of 3DFin itself on twelve real plots with
  simulated partial coverage.

The results are directly relevant to forest inventory practice: the required coverage depends on the
estimator and on how well stem points are separated from branches; least-squares fits fail at any
coverage when branch points remain, whereas an arc-constrained RANSAC does not; the 202.5° rule keeps
accepted diameters accurate but leaves about half of the stems without a diameter even with four to
six spread scan positions; and spreading scan positions matters more than adding them. The manuscript
also discusses why the coverage question remains relevant for mobile and personal laser scanning, and it
complements the recent simulation study of hand-held trajectories by Kuželka (2025) in this journal by
addressing static scan positions, the choice of estimator and the acceptance rules of processing
software.

All code and result tables are archived on Zenodo (https://doi.org/10.5281/zenodo.23911186); all
third-party data are openly licensed.

The manuscript is original, has not been published and is not under consideration elsewhere. The
author declares no competing interests and received no specific funding.

Yours sincerely,

Angel Naya
