"""Case-by-case review of KCL CISS seed segmentations in 3D Slicer 5.8.

Loads one case at a time: CISS underlay plus the binary masks in segments/.
Edits are written back to those NIfTI files. labels.nii.gz is rebuilt only as
the exclusive preview (tumor overwrites everything else).

Launch from a clone of this folder (path is wherever the repo was cloned):

  /Applications/Slicer.app/Contents/MacOS/Slicer --python-script /path/to/slicer_seed/review_cases.py

Or, with Slicer already open, paste into the Python console:

  import runpy
  runpy.run_path("/path/to/slicer_seed/review_cases.py", run_name="__main__")
"""

import json
import os

import qt
import slicer
import vtk

# Folder that contains this script. Case batches are not part of the git
# repo; they can live anywhere on disk (a OneDrive download, for example).
# Slicer --python-script and runpy.run_path both set __file__.
try:
    SEED = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SEED = os.getcwd()
# Full CISS grid, so saved masks stay aligned with the underlay.
EXTENT_REFERENCE_GEOMETRY = 0

# name, display name, RGB 0-1, 2D fill opacity
# vein and both labyrinths are the segments to correct; the rest stay visible as context
SEGMENTS = [
    ("brainstem", "Brainstem", (197 / 255.0, 197 / 255.0, 206 / 255.0), 0.15),
    ("cerebellum", "Cerebellum", (1.0, 215 / 255.0, 0.0), 0.12),
    ("vein", "Vein", (65 / 255.0, 105 / 255.0, 225 / 255.0), 0.55),
    ("labyrinth_L", "Labyrinth_L", (144 / 255.0, 238 / 255.0, 144 / 255.0), 0.70),
    ("labyrinth_R", "Labyrinth_R", (255 / 255.0, 105 / 255.0, 180 / 255.0), 0.70),
    ("tumor_expert", "Tumor_expert", (1.0, 0.0, 0.0), 0.35),
]
# Later entries overwrite earlier ones in the exclusive preview map.
PREVIEW_ORDER = [name for name, _, _, _ in SEGMENTS]


def case_ids(directory):
    ids = []
    if not directory or not os.path.isdir(directory):
        return ids
    for name in sorted(os.listdir(directory)):
        case_dir = os.path.join(directory, name)
        if os.path.isdir(case_dir) and os.path.isfile(os.path.join(case_dir, "ciss.nii.gz")):
            ids.append(name)
    return ids


def discover_batches(root):
    batches = []
    if not os.path.isdir(root):
        return batches
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        ids = case_ids(path)
        if ids:
            batches.append((name, path, ids))
    return batches


def fill_batch_list(listing, paths, batches):
    listing.clear()
    del paths[:]
    for name, path, ids in batches:
        listing.addItem(f"{name}     {len(ids)} cases     {ids[0]}–{ids[-1]}")
        paths.append(path)
    if paths:
        listing.setCurrentRow(0)


def choose_batch_directory(parent=None):
    """Pick a local folder of cases, wherever the batches were saved."""
    dialog = qt.QDialog(parent)
    dialog.setWindowTitle("Choose cases")
    dialog.setMinimumWidth(560)
    layout = qt.QVBoxLayout(dialog)
    layout.addWidget(qt.QLabel(
        "Choose a local batch folder. Each batch is a directory of numbered cases "
        "(each case contains ciss.nii.gz). You can also choose a parent folder "
        "that holds several batches, then pick one from the list."
    ))
    listing = qt.QListWidget()
    paths = []
    fill_batch_list(listing, paths, discover_batches(SEED))
    layout.addWidget(listing)

    chosen = {"path": None}
    start_dir = SEED if paths or case_ids(SEED) else os.path.expanduser("~")

    def accept_selected():
        row = listing.currentRow
        if row < 0 or row >= len(paths):
            qt.QMessageBox.information(
                dialog,
                "Choose a folder",
                "Use Choose folder… and select the batch directory on this computer.",
            )
            return
        chosen["path"] = paths[row]
        dialog.accept()

    def browse_folder():
        path = qt.QFileDialog.getExistingDirectory(dialog, "Choose a folder of cases", start_dir)
        if not path:
            return
        if os.path.isfile(os.path.join(path, "ciss.nii.gz")):
            qt.QMessageBox.warning(
                dialog,
                "One case selected",
                "That folder is a single case. Choose the batch folder that contains it.",
            )
            return
        if case_ids(path):
            chosen["path"] = path
            dialog.accept()
            return
        found = discover_batches(path)
        if not found:
            qt.QMessageBox.warning(
                dialog,
                "No cases",
                "No numbered case folders with ciss.nii.gz were found there.",
            )
            return
        if len(found) == 1:
            chosen["path"] = found[0][1]
            dialog.accept()
            return
        fill_batch_list(listing, paths, found)

    buttons = qt.QHBoxLayout()
    browse = qt.QPushButton("Choose folder…")
    load = qt.QPushButton("Load")
    cancel = qt.QPushButton("Cancel")
    browse.setDefault(True)
    for button in (browse, load, cancel):
        buttons.addWidget(button)
    layout.addLayout(buttons)
    browse.clicked.connect(browse_folder)
    load.clicked.connect(accept_selected)
    listing.itemDoubleClicked.connect(lambda item: accept_selected())
    cancel.clicked.connect(dialog.reject)
    if dialog.exec_() != qt.QDialog.Accepted:
        return None
    return chosen["path"]


def load_state(path):
    if os.path.isfile(path):
        with open(path) as handle:
            return json.load(handle)
    return {"index": 0, "reviewed": []}


class CaseReviewer:
    def __init__(self, batch_dir):
        self.batch_dir = batch_dir
        self.state_path = os.path.join(batch_dir, "review_state.json")
        self.ids = case_ids(batch_dir)
        if not self.ids:
            raise RuntimeError(f"No cases under {batch_dir}")
        self.state = load_state(self.state_path)
        self.index = min(int(self.state.get("index", 0)), len(self.ids) - 1)
        self.dirty = False
        self.volume = None
        self.segmentation = None
        self._build_ui()
        self.load_current()

    def _build_ui(self):
        self.widget = qt.QWidget()
        self.widget.setWindowTitle("CISS seed review")
        self.widget.setMinimumWidth(420)
        layout = qt.QVBoxLayout(self.widget)

        batch_row = qt.QHBoxLayout()
        self.batchLabel = qt.QLabel(os.path.basename(self.batch_dir))
        self.batchLabel.setStyleSheet("font-weight: bold;")
        change = qt.QPushButton("Change batch")
        change.clicked.connect(self.change_batch)
        batch_row.addWidget(self.batchLabel)
        batch_row.addStretch()
        batch_row.addWidget(change)
        layout.addLayout(batch_row)

        self.title = qt.QLabel()
        self.title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.title)

        name_row = qt.QHBoxLayout()
        name_row.addWidget(qt.QLabel("Your name"))
        self.nameEdit = qt.QLineEdit()
        self.nameEdit.setPlaceholderText("Required before saving")
        self.nameEdit.setText(self.state.get("annotator", ""))
        self.nameEdit.editingFinished.connect(self._store_annotator)
        name_row.addWidget(self.nameEdit)
        layout.addLayout(name_row)

        self.detail = qt.QLabel()
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)

        hint = qt.QLabel(
            "Edit Vein, Labyrinth_L, and Labyrinth_R in Segment Editor. "
            "Brainstem, cerebellum, and tumor stay on as context. "
            "Save overwrites each mask and adds your name to the filename."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = qt.QHBoxLayout()
        self.prevButton = qt.QPushButton("Previous")
        self.saveButton = qt.QPushButton("Save")
        self.nextButton = qt.QPushButton("Save and next")
        self.skipButton = qt.QPushButton("Next without saving")
        for button in (self.prevButton, self.saveButton, self.nextButton, self.skipButton):
            row.addWidget(button)
        layout.addLayout(row)

        focus = qt.QHBoxLayout()
        focus.addWidget(qt.QLabel("Center on"))
        self.focusVein = qt.QPushButton("Vein")
        self.focusLeft = qt.QPushButton("Labyrinth L")
        self.focusRight = qt.QPushButton("Labyrinth R")
        self.focusTumor = qt.QPushButton("Tumor")
        for button in (self.focusVein, self.focusLeft, self.focusRight, self.focusTumor):
            focus.addWidget(button)
        layout.addLayout(focus)

        self.prevButton.clicked.connect(lambda: self._step(-1, save=True))
        self.saveButton.clicked.connect(self.save_current)
        self.nextButton.clicked.connect(lambda: self._step(1, save=True))
        self.skipButton.clicked.connect(lambda: self._step(1, save=False))
        self.focusVein.clicked.connect(lambda: self.center_on("Vein"))
        self.focusLeft.clicked.connect(lambda: self.center_on("Labyrinth_L"))
        self.focusRight.clicked.connect(lambda: self.center_on("Labyrinth_R"))
        self.focusTumor.clicked.connect(lambda: self.center_on("Tumor_expert"))

        self.widget.show()
        self.widget.raise_()

    def _step(self, delta, save):
        if save:
            if not self.save_current():
                return
        elif self.dirty and not self._confirm_discard():
            return
        nxt = self.index + delta
        if nxt < 0 or nxt >= len(self.ids):
            slicer.util.delayDisplay("No further cases." if delta > 0 else "Already at the first case.")
            return
        self.index = nxt
        self.state["index"] = self.index
        self.save_state()
        self.load_current()

    def change_batch(self):
        if self.dirty and not self._confirm_discard():
            return
        chosen = choose_batch_directory(self.widget)
        if not chosen or os.path.abspath(chosen) == os.path.abspath(self.batch_dir):
            return
        self.widget.close()
        global reviewer
        reviewer = CaseReviewer(chosen)

    def _annotator_slug(self):
        name = self.nameEdit.text.strip() if getattr(self, "nameEdit", None) else self.state.get("annotator", "")
        parts = []
        for character in name:
            if character.isalnum() or character in ("_", "-"):
                parts.append(character)
            elif character.isspace() and parts and parts[-1] != "_":
                parts.append("_")
        return "".join(parts).strip("_")

    def _store_annotator(self):
        name = self.nameEdit.text.strip()
        if name == self.state.get("annotator", ""):
            return
        self.state["annotator"] = name
        self.save_state()

    def _mask_names(self, directory, key):
        if not os.path.isdir(directory):
            return []
        plain = f"{key}.nii.gz"
        prefix = key + "_"
        names = []
        for name in os.listdir(directory):
            if name == plain or (name.startswith(prefix) and name.endswith(".nii.gz")):
                names.append(name)
        return names

    def _mask_path(self, directory, key):
        names = self._mask_names(directory, key)
        if not names:
            return None
        user = self._annotator_slug()
        preferred = f"{key}_{user}.nii.gz" if user else ""
        if preferred and preferred in names:
            return os.path.join(directory, preferred)
        named = [name for name in names if name != f"{key}.nii.gz"]
        if len(named) == 1:
            return os.path.join(directory, named[0])
        plain = f"{key}.nii.gz"
        if plain in names:
            return os.path.join(directory, plain)
        return os.path.join(directory, sorted(named)[-1])

    def _write_named_mask(self, labelmap, directory, key, user):
        os.makedirs(directory, exist_ok=True)
        dest_name = f"{key}_{user}.nii.gz"
        dest = os.path.join(directory, dest_name)
        if not slicer.util.saveNode(labelmap, dest):
            raise RuntimeError(f"Failed to write {dest}")
        for name in self._mask_names(directory, key):
            if name != dest_name:
                os.remove(os.path.join(directory, name))
        return dest

    def save_state(self):
        with open(self.state_path, "w") as handle:
            json.dump(self.state, handle, indent=2)
            handle.write("\n")

    def read_manifest(self, case_id):
        path = os.path.join(self.batch_dir, case_id, "manifest.json")
        if not os.path.isfile(path):
            return {}
        with open(path) as handle:
            return json.load(handle)

    def _confirm_discard(self):
        box = qt.QMessageBox(self.widget)
        box.setWindowTitle("Unsaved edits")
        box.setText(f"Discard unsaved edits on case {self.ids[self.index]}?")
        box.setStandardButtons(qt.QMessageBox.Discard | qt.QMessageBox.Cancel)
        return box.exec_() == qt.QMessageBox.Discard

    def load_current(self):
        case_id = self.ids[self.index]
        case_dir = os.path.join(self.batch_dir, case_id)
        manifest = self.read_manifest(case_id)
        slicer.mrmlScene.Clear(0)

        self.volume = slicer.util.loadVolume(os.path.join(case_dir, "ciss.nii.gz"))
        self.volume.SetName(f"{case_id}_CISS")

        self.segmentation = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentationNode", f"{case_id}_seg"
        )
        self.segmentation.CreateDefaultDisplayNodes()
        self.segmentation.SetReferenceImageGeometryParameterFromVolumeNode(self.volume)
        self.segmentation.GetSegmentation().SetSourceRepresentationName("Binary labelmap")

        logic = slicer.modules.segmentations.logic()
        segmentation = self.segmentation.GetSegmentation()
        for key, display_name, color, opacity in SEGMENTS:
            path = self._mask_path(os.path.join(case_dir, "segments"), key)
            if not path:
                continue
            segment_id = segmentation.AddEmptySegment("", display_name)
            segment = segmentation.GetSegment(segment_id)
            segment.SetColor(*color)
            segment.SetTag("segment_key", key)
            labelmap = slicer.util.loadLabelVolume(path)
            segment_ids = vtk.vtkStringArray()
            segment_ids.InsertNextValue(segment_id)
            if not logic.ImportLabelmapToSegmentationNode(labelmap, self.segmentation, segment_ids):
                raise RuntimeError(f"Could not import {path}")
            slicer.mrmlScene.RemoveNode(labelmap)
            display = self.segmentation.GetDisplayNode()
            display.SetSegmentOpacity2DFill(segment_id, opacity)
            display.SetSegmentOpacity2DOutline(segment_id, 1.0)

        display = self.segmentation.GetDisplayNode()
        display.SetVisibility2DFill(True)
        display.SetVisibility2DOutline(True)
        display.SetOpacity3D(0.45)

        slicer.util.setSliceViewerLayers(background=self.volume, fit=True)
        slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
        self._open_segment_editor()

        laterality = manifest.get("laterality", "")
        side = "Labyrinth_L" if laterality == "left" else "Labyrinth_R" if laterality == "right" else "Vein"
        self.center_on(side)
        self._select_segment("Vein")

        reviewed = case_id in self.state.get("reviewed", [])
        self.title.setText(f"Case {case_id}   {self.index + 1} / {len(self.ids)}")
        self.detail.setText(
            f"Laterality: {laterality or 'unknown'}"
            + ("   · saved" if reviewed else "")
        )
        self.dirty = False
        self.segmentation.AddObserver(
            vtk.vtkCommand.ModifiedEvent, lambda caller, event: self._mark_dirty()
        )
        slicer.util.resetThreeDViews()

    def _mark_dirty(self):
        self.dirty = True

    def _open_segment_editor(self):
        slicer.util.selectModule("SegmentEditor")
        slicer.app.processEvents()
        editor = slicer.modules.segmenteditor.widgetRepresentation().self()
        editor.parameterSetNode.SetAndObserveSegmentationNode(self.segmentation)
        editor.parameterSetNode.SetAndObserveSourceVolumeNode(self.volume)
        # Keep vein and labyrinth independent. The exclusive map is only the preview.
        editor.parameterSetNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)

    def _segment_id(self, display_name):
        return self.segmentation.GetSegmentation().GetSegmentIdBySegmentName(display_name)

    def _select_segment(self, display_name):
        segment_id = self._segment_id(display_name)
        if not segment_id:
            return
        editor = slicer.modules.segmenteditor.widgetRepresentation().self()
        editor.parameterSetNode.SetSelectedSegmentID(segment_id)

    def center_on(self, display_name):
        segment_id = self._segment_id(display_name)
        if not segment_id:
            return
        binary_name = slicer.vtkSegmentationConverter.GetBinaryLabelmapRepresentationName()
        binary = self.segmentation.GetSegmentation().GetSegment(segment_id).GetRepresentation(binary_name)
        if not binary or binary.GetExtent()[1] < binary.GetExtent()[0]:
            return
        bounds = [0.0] * 6
        binary.GetBounds(bounds)
        center = (
            (bounds[0] + bounds[1]) / 2.0,
            (bounds[2] + bounds[3]) / 2.0,
            (bounds[4] + bounds[5]) / 2.0,
        )
        slicer.vtkMRMLSliceNode.JumpAllSlices(
            slicer.mrmlScene, center[0], center[1], center[2], slicer.vtkMRMLSliceNode.CenteredJumpSlice
        )
        self._select_segment(display_name)

    def save_current(self):
        user = self._annotator_slug()
        if not user:
            qt.QMessageBox.warning(
                self.widget,
                "Name required",
                "Enter your name before saving. It is added to each segment filename.",
            )
            return False
        self._store_annotator()
        case_id = self.ids[self.index]
        case_dir = os.path.join(self.batch_dir, case_id)
        seg_dir = os.path.join(case_dir, "segments")
        logic = slicer.modules.segmentations.logic()
        segmentation = self.segmentation.GetSegmentation()

        for _key, display_name, _, _ in SEGMENTS:
            segment_id = segmentation.GetSegmentIdBySegmentName(display_name)
            if not segment_id:
                continue
            ids = vtk.vtkStringArray()
            ids.InsertNextValue(segment_id)
            labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
            try:
                logic.ExportSegmentsToLabelmapNode(
                    self.segmentation, ids, labelmap, self.volume, EXTENT_REFERENCE_GEOMETRY
                )
                self._write_named_mask(labelmap, seg_dir, _key, user)
            finally:
                slicer.mrmlScene.RemoveNode(labelmap)

        self._write_preview(case_dir, user)
        reviewed = self.state.setdefault("reviewed", [])
        if case_id not in reviewed:
            reviewed.append(case_id)
        self.state["index"] = self.index
        self.save_state()
        self.dirty = False
        self.detail.setText(self.detail.text.replace("   · saved", "") + "   · saved")
        slicer.util.delayDisplay(f"Saved case {case_id}", 800)
        return True

    def _write_preview(self, case_dir, user):
        """Exclusive labelmap. Later segments in PREVIEW_ORDER overwrite earlier ones."""
        logic = slicer.modules.segmentations.logic()
        ids = vtk.vtkStringArray()
        segmentation = self.segmentation.GetSegmentation()
        for key in PREVIEW_ORDER:
            display_name = next(label for seg_key, label, _, _ in SEGMENTS if seg_key == key)
            segment_id = segmentation.GetSegmentIdBySegmentName(display_name)
            if segment_id:
                ids.InsertNextValue(segment_id)
        if ids.GetNumberOfValues() == 0:
            return
        labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
        logic.ExportSegmentsToLabelmapNode(
            self.segmentation, ids, labelmap, self.volume, EXTENT_REFERENCE_GEOMETRY
        )
        try:
            self._write_named_mask(labelmap, case_dir, "labels", user)
        finally:
            slicer.mrmlScene.RemoveNode(labelmap)


def main():
    global reviewer
    if "reviewer" in globals() and reviewer is not None:
        reviewer.widget.close()
    chosen = choose_batch_directory()
    if not chosen:
        return
    reviewer = CaseReviewer(chosen)


if slicer.app.startupCompleted:
    main()
else:
    slicer.app.connect("startupCompleted()", main)
