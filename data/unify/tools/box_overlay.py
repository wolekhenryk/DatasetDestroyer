"""Draw the boxes of a unified-table CSV on their images - a visual check that box conversion (YOLO / VOC -> inclusive pixel corners)
and the label columns are right.

    cd data_to_merge
    ../.venv/bin/python -m unify.tools.box_overlay --table <merged-labels.csv> --dataset see-ai --n 12 --seed 1 --out overlay.png
    ../.venv/bin/python -m unify.tools.box_overlay ... --edge        # only images that have a box touching the image border

Boxes are inclusive: the rectangle is drawn from xmin to xmax+1 so that it encloses the last pixel. Colour = harmonised finding, text = native label.
Also prints, for the selected rows, the box count, the classes and how many boxes touch each border (convention check)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from ..build import DATA_ROOT, read_csv

PALETTE = [(255, 64, 64), (64, 255, 64), (80, 140, 255), (255, 220, 0), (255, 0, 255), (0, 255, 255), (255, 140, 0), (160, 100, 255),
           (255, 255, 255), (150, 255, 150), (255, 150, 150), (150, 150, 255)]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m unify.tools.box_overlay")
    ap.add_argument("--table", type=Path, required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--edge", action="store_true", help="only images with a box touching the border")
    ap.add_argument("--cell", type=int, default=360, help="cell size of the montage in pixels")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    df = read_csv(a.table)
    df = df[(df["dataset"] == a.dataset) & (df["source_type"] == "image") & df["has_bbox"]]
    if a.edge:
        def touches(r):
            return any(b["xmin"] == 0 or b["ymin"] == 0 or b["xmax"] == r.width - 1 or b["ymax"] == r.height - 1 for b in json.loads(r.bboxes_json))
        df = df[[touches(r) for r in df.itertuples()]]
    sel = df.sample(min(a.n, len(df)), random_state=a.seed)
    cols = 4
    rows_n = (len(sel) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * a.cell, rows_n * a.cell))
    findings: dict[str, int] = {}
    for i, r in enumerate(sel.itertuples()):
        im = Image.open(DATA_ROOT / r.file_path).convert("RGB")
        scale = a.cell / max(im.size)
        im = im.resize((round(im.width * scale), round(im.height * scale)))
        d = ImageDraw.Draw(im)
        touch = [0, 0, 0, 0]
        for b in json.loads(r.bboxes_json):
            col = PALETTE[findings.setdefault(b["finding"], len(findings)) % len(PALETTE)]
            d.rectangle([b["xmin"] * scale, b["ymin"] * scale, (b["xmax"] + 1) * scale, (b["ymax"] + 1) * scale], outline=col, width=2)
            d.text((b["xmin"] * scale + 3, b["ymin"] * scale + 2), b["label"], fill=col)
            touch = [touch[0] + int(b["xmin"] == 0), touch[1] + int(b["ymin"] == 0), touch[2] + int(b["xmax"] == r.width - 1), touch[3] + int(b["ymax"] == r.height - 1)]
        d.text((4, im.height - 12), r.item_id, fill=(255, 255, 0))
        sheet.paste(im, ((i % cols) * a.cell, (i // cols) * a.cell))
        print(f"{r.item_id}: {r.n_boxes} boxes, classes {r.findings_all}, boxes touching left/top/right/bottom border {touch}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
