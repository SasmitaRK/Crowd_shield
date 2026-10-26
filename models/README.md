# Model weights

The app downloads its two counting models the first time it needs them, from this repository's GitHub
releases, and checks each file's SHA-256 (`crowdshield/weights.py`):

| File | Model | Release |
|---|---|---|
| `pet_shab.pth` | PET point model, fine-tuned on ShanghaiTech A + B (the app's counter) | `pet-shab-v1` |
| `dmcount_shab.pth` | DM-Count density model (backup counter, and the second opinion) | `dmcount-shab-v1` |

The original app's YOLO detectors are no longer shipped. They were never used for counting once PET was in,
and their 110 MB made every deploy slower. To re-run the old YOLO baselines in `eval/evaluate_counting.py`,
install `ultralytics` and `dill`, and either let Ultralytics download `yolov8l.pt` by name or restore both
files from git history:

```
git checkout 04925a6 -- models/yolov8l.pt models/crowd_yolo.pt
```
