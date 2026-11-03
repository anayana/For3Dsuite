# Cover letter — Journal of Cultural Heritage (Entwurf, Stand 03.11.2026)

Hinweise: Einreichung über den Abo-Weg (kein Open Access, **keine Gebühr**). Platzhalter in [eckigen
Klammern] vor dem Absenden füllen; 3_SS/2_OSA-Zahlen nachtragen.

---

[Name]
[Institution, Adresse]
[E-Mail]

[Datum]

To the Editors
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

- Across building 5_CB the median deviation of the Gaussian centres from the reference is 12.0 cm, with
  59 % of the reference covered within 10 cm; arches and columns reach 4–6 cm, while floors and roofs
  remain markedly worse. [TODO: zweites/drittes Gebäude]
- Held-out image quality on survey imagery mainly reflects capture coverage, not reconstruction fidelity,
  and is a misleading quality indicator for heritage use.
- Re-applying distortion models to already undistorted survey images degrades both reconstruction and
  geometry; we describe how to detect this.

We believe the work is of direct interest to the Journal's readership, because it tells heritage
practitioners what 3D Gaussian Splatting can and cannot be used for — presentation and dissemination
versus metric documentation — and provides a reproducible baseline. All data are openly licensed
(CC BY 4.0) and all code is released as free software, so the comparison can be repeated at no cost.

The manuscript is original, has not been published previously and is not under consideration elsewhere.
All authors have approved the submission. There are no conflicts of interest to declare. The work
received no specific funding. [prüfen]

Possible reviewers: [optional — nur Personen ohne Interessenkonflikt].

Thank you for considering our manuscript.

Yours sincerely,

[Name]
