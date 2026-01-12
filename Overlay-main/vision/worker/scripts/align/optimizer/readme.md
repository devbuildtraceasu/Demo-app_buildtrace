
# Drawing Alignment Tool

This tool aligns two versions of the same drawing using computer vision. It detects features using SIFT, matches them between images, and applies a constrained affine transformation to align the drawings.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Or install from the core directory:

```bash
pip install -r core/requirements.txt
```

## Usage
Using the command line tool:

```bash
python -m core.main --old_path drawings/inputs/test1_old.pdf --new_path drawings/inputs/test1_new.pdf --overlay_path drawings/outputs/test1_overlay.pdf
python -m core.main --old_path drawings/inputs/test2_old.pdf --new_path drawings/inputs/test2_new.pdf --overlay_path drawings/outputs/test2_overlay.pdf
python -m core.main --old_path drawings/inputs/test3_old.pdf --new_path drawings/inputs/test3_new.pdf --overlay_path drawings/outputs/test3_overlay.pdf

python -m core.main_img --old_path drawings/inputs/test1_old.pdf --new_path drawings/inputs/test1_new.pdf --overlay_path drawings/outputs/test1_overlay.png
python -m core.main_img --old_path drawings/inputs/test2_old.pdf --new_path drawings/inputs/test2_new.pdf --overlay_path drawings/outputs/test2_overlay.png
python -m core.main_img --old_path drawings/inputs/test3_old.pdf --new_path drawings/inputs/test3_new.pdf --overlay_path drawings/outputs/test3_overlay.png

python -m core.main_img --old_path drawings/images/test1_old.png --new_path drawings/images/test1_new.png --overlay_path drawings/outputs/test1_overlay.png
python -m core.main_img --old_path drawings/images/test2_old.png --new_path drawings/images/test2_new.png --overlay_path drawings/outputs/test2_overlay.png
python -m core.main_img --old_path drawings/images/test3_old.png --new_path drawings/images/test3_new.png --overlay_path drawings/outputs/test3_overlay.png
```
