KCL CISS Slicer seed pack
=========================
241 cases, split into batches of 50 (last batch 41).
Skip 168 (not in this set). Other TCIA IDs not present:
39, 97, 130, 133, 160, 208, 219, 227.

  batch_01_001-051    50 cases
  batch_02_052-102    50 cases
  batch_03_103-154    50 cases
  batch_04_155-206    50 cases
  batch_05_207-250    41 cases

Inventory: cohort.csv

Review in 3D Slicer
-------------------
Launch review_cases.py. It asks which batch folder to load.
Each batch keeps its own review_state.json, so annotators can work
on separate folders. Choose folder… loads any directory of cases.

  Slicer --python-script /path/to/slicer_seed/review_cases.py

See README.md for the full review steps. Do not run review_cases.py
directly in a terminal.

Load one case by hand
---------------------
1. File → Add Data → <case>/ciss.nii.gz  (underlay)
2. Then either:
   a. Add <case>/labels.nii.gz (same grid; Volumes → Convert labelmap to segmentation), or
   b. Add the files in <case>/segments/ into a Segmentation node.

Edit the segment binaries (segments/*.nii.gz), not labels.nii.gz.
labels.nii.gz is an exclusive preview map only (tumor wins overlaps).

Label IDs in labels.nii.gz / labels.ctbl
----------------------------------------
1 brainstem
2 cerebellum
3 vein
4 labyrinth_L
5 labyrinth_R
6 tumor_expert   (KCL expert contour, not a model prediction)

Seeds: SuperSynth on CISS (brainstem, cerebellum, vein) + IE-VNet both ears.
Geometry matches CISS — no transform.
