# KCL CISS Slicer seed

241 vestibular schwannoma cases from the [KCL TCIA set](https://www.cancerimagingarchive.net/collection/vestibular-schwannoma-mc-rc/), prepared for review in 3D Slicer. Each case is a CISS MRI plus segmentations for brainstem, cerebellum, vein and dural sinuses, left and right labyrinth, and the KCL expert tumor contour.

The cases are split into batches so more than one person can annotate at the same time. Give each person one batch folder.

| Folder | Cases |
|---|---|
| `batch_01_001-051` | 50 |
| `batch_02_052-102` | 50 |
| `batch_03_103-154` | 50 |
| `batch_04_155-206` | 50 |
| `batch_05_207-250` | 41 |

Case 168 is not in this set. These TCIA IDs are also absent: 39, 97, 130, 133, 160, 208, 219, 227.

`cohort.csv` is the inventory (laterality and voxel counts).

The clone is about 4 GB.

## Review in 3D Slicer

Requires [3D Slicer](https://download.slicer.org/) 5.8 or newer.

From the cloned folder:

```bash
/Applications/Slicer.app/Contents/MacOS/Slicer --python-script /path/to/slicer_seed/review_cases.py
```

On Windows or Linux, use that machine's `Slicer` executable with the same `--python-script` argument. Do not run `review_cases.py` directly in a terminal. It only works inside Slicer.

If Slicer is already open, paste this into the Python console (`View` → `Python Console`):

```python
import runpy
runpy.run_path("/path/to/slicer_seed/review_cases.py", run_name="__main__")
```

A window lists the five batches. Select one and click **Load**, or use **Choose folder…** to open a batch that was copied somewhere else. **Change batch** switches folders without restarting Slicer.

The script loads one case at a time:

- CISS as the underlay
- the six masks in `segments/` as one segmentation
- left labyrinth in light green, right labyrinth in pink

Edit **Vein**, **Labyrinth_L**, and **Labyrinth_R** in Segment Editor. Brainstem, cerebellum, and tumor stay visible as context. Overlap is allowed, so painting one structure does not erase another.

**Save** and **Save and next** write `segments/*.nii.gz` and rebuild `labels.nii.gz`. Progress is stored in `review_state.json` inside the batch folder, which is not part of this repository, so each person starts at the first case.

## What is in a case

```
batch_01_001-051/001/
  ciss.nii.gz          underlay
  labels.nii.gz        exclusive preview (tumor wins overlaps)
  labels.ctbl          Slicer color table
  manifest.json
  segments/
    brainstem.nii.gz
    cerebellum.nii.gz
    vein.nii.gz
    labyrinth_L.nii.gz
    labyrinth_R.nii.gz
    tumor_expert.nii.gz
```

Edit the files in `segments/`. `labels.nii.gz` is only a preview: where labels overlap, the later structure replaces the earlier one, and the tumor contour replaces everything.

| Label | Structure |
|---|---|
| 1 | brainstem |
| 2 | cerebellum |
| 3 | vein |
| 4 | labyrinth_L |
| 5 | labyrinth_R |
| 6 | tumor_expert (KCL expert contour, not a model prediction) |

Brainstem, cerebellum, and vein started from SuperSynth on CISS. Both labyrinths started from IE-VNet. Geometry matches the CISS grid, so no transform is needed.

Labyrinth islands that shared a face with brainstem or cerebellum were removed before publication. Those structures do not touch the labyrinth. The list of what was removed is in `labyrinth_touch_cleanup.json`. Ten sides were emptied because every component touched brainstem or cerebellum, and those need to be drawn again: 004 R, 005 L, 007 L, 027 R, 064 L, 156 R, 157 R, 164 L, 191 L, 220 R.

## Load a single case by hand

1. **File → Add Data** and open `<case>/ciss.nii.gz`.
2. Add `<case>/labels.nii.gz`, then **Volumes → Convert labelmap to segmentation**. Or add the files in `<case>/segments/` into one Segmentation node.
3. Save edits back to `segments/*.nii.gz`, not only to `labels.nii.gz`.
