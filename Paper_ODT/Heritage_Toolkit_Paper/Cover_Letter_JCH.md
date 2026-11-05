Angel Naya\
Independent Researcher, Berlin, Germany\
angel.naya@posteo.de

3 November 2026

To the Editors\
Journal of Cultural Heritage

**Submission of an original research article: "How close is a Gaussian splat to the survey? Geometric
accuracy of 3D Gaussian Splatting against photogrammetric reference point clouds of historic buildings"**

Dear Editors,

Please find enclosed our manuscript for consideration as an original research article in the Journal of
Cultural Heritage.

3D Gaussian Splatting is rapidly being adopted for presenting historic buildings, because it turns
ordinary photographs into photorealistic, real-time walkthroughs. Whether its geometry can be trusted
for documentation, however, is rarely tested against an independent survey; most studies report only
image-similarity scores. Our manuscript closes this gap for a concrete, openly licensed case: we train
standard 3D Gaussian Splatting on the published camera orientations of the Pellis et al. (2025) heritage
dataset and compare the result with the labelled photogrammetric reference point cloud, per
architectural class.

The main findings are:

- Across three historic buildings the median deviation of the Gaussian centres from the reference is
  12.3–13.7 cm at full image resolution, with 52–67 % of the reference covered within 10 cm; arches reach
  5–6 cm in all three, while floors remain among the weakest classes. Half-resolution runs give the same
  result, so higher resolution sharpens the renderings but not the geometry.
- Held-out image quality on survey imagery mainly reflects capture coverage, not reconstruction fidelity,
  and is a misleading quality indicator for heritage use.
- Re-applying distortion models to already undistorted survey images degrades both reconstruction and
  geometry; we describe how to detect this.

We believe the work is of direct interest to the Journal's readership, because it tells heritage
practitioners what 3D Gaussian Splatting can and cannot be used for — presentation and dissemination
versus metric documentation — and provides a reproducible baseline. All data are openly licensed
(CC BY 4.0) and all code is released as free software, so the comparison can be repeated at no cost.

The manuscript is original, has not been published previously and is not under consideration elsewhere.
The author declares no conflicts of interest. The work received no specific funding.

Thank you for considering our manuscript.

Yours sincerely,

Angel Naya
