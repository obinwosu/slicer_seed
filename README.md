# KCL CISS Slicer review

Review script for 241 vestibular schwannoma CISS cases from the [KCL TCIA set](https://www.cancerimagingarchive.net/collection/vestibular-schwannoma-mc-rc/). This repository is the Slicer script and the instructions. The MRI volumes are shared separately and are not in git.

## What to send back

Enter your name in the review window. Save overwrites the segment files already in the case and adds your name to the filename, for example `segments/vein_Jane_Doe.nii.gz` and `labels_Jane_Doe.nii.gz`. It does not keep the old file.

For each case you edited, upload that case's `segments` folder and the `labels_` file. Do not upload `ciss.nii.gz`. That file is the MRI.

## Get a batch

Download the batch you were assigned. Each batch is a folder of numbered cases:

```
batch_01_001-051/
  001/
    ciss.nii.gz
    labels.nii.gz
    labels.ctbl
    manifest.json
    segments/
      brainstem.nii.gz
      cerebellum.nii.gz
      vein.nii.gz
      labyrinth_L.nii.gz
      labyrinth_R.nii.gz
      tumor_expert.nii.gz
  002/
  ...
```

Put that folder anywhere on your computer. OneDrive, Desktop, and an external drive all work. The script does not expect the cases to sit next to this repository.

| Folder | Cases |
|---|---|
| `batch_01_001-051` | 50 |
| `batch_02_052-102` | 50 |
| `batch_03_103-154` | 50 |
| `batch_04_155-206` | 50 |
| `batch_05_207-250` | 41 |

Case 168 is not in this set. These TCIA IDs are also absent: 39, 97, 130, 133, 160, 208, 219, 227.

## Review in 3D Slicer

Requires [3D Slicer](https://download.slicer.org/) 5.8 or newer. Clone this repository, then launch Slicer with the script. Replace the path with where you cloned it:

```bash
/Applications/Slicer.app/Contents/MacOS/Slicer --python-script /path/to/slicer_seed/review_cases.py
```

On Windows or Linux, use that machine's `Slicer` executable with the same `--python-script` argument. Do not run `review_cases.py` from a terminal.

If Slicer is already open, paste this into the Python console (`View` → `Python Console`):

```python
import runpy
runpy.run_path("/path/to/slicer_seed/review_cases.py", run_name="__main__")
```

Click **Choose folder…** and select either:

- one batch folder, such as `batch_02_052-102`, or
- a parent folder that contains several batch folders, then select the batch from the list and click **Load**

**Change batch** switches folders without restarting Slicer.

The script loads one case at a time: CISS as the underlay, and the six masks in `segments/` as one segmentation. The left labyrinth is light green and the right labyrinth is pink.

Edit **Vein**, **Labyrinth_L**, and **Labyrinth_R** in Segment Editor. Brainstem, cerebellum, and tumor stay visible as context. Overlap is allowed, so painting one structure does not erase another.

**Save** and **Save and next** overwrite the masks inside the case you opened. Each filename gains your name (`vein_Jane_Doe.nii.gz`). Progress and your name are stored in `review_state.json` inside the batch folder.

## What the labels mean

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

Labyrinth islands that shared a face with brainstem or cerebellum were removed before the batches were shared. Those structures do not touch the labyrinth. Ten sides were emptied because every component touched brainstem or cerebellum, and those need to be drawn again: 004 R, 005 L, 007 L, 027 R, 064 L, 156 R, 157 R, 164 L, 191 L, 220 R.
