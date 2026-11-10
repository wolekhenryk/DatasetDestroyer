"""PolypsSet (Li et al., PLOS ONE 2021): 37,899 colonoscopy frames with Pascal-VOC XML boxes, split train2019 / val2019 / test2019.

Layout: <split>/Image/[<sub>/]<n>.jpg + <split>/Annotation/[<sub>/]<n>.xml (train flat, val/test one sub-folder per video). One image row per
JPEG that has an XML (`item_id` = path below the dataset folder without extension: stems repeat across splits and sub-folders).
The XML <path> field holds the authors' machine paths; it is parsed ONLY to derive the origin sub-set (6 sources), the video/case id and
the source frame number - the raw path (it contains user names) is never copied into the table.

Labels: <object><name> = polyp histology (adenomatous / hyperplastic, constant per case) -> finding polyps + finding_subtype; an XML without
<object> = frame of a polyp video without an annotated polyp -> category background / finding no-polyp-annotated (derived; annotated-empty
box list, n_boxes 0). Boxes are Pascal-VOC with HALF-OPEN max edges (xmax == W / ymax == H occur, never more) -> voc_to_box subtracts 1.
Orphans: XMLs whose JPEG is missing (798 in val/test) become no rows (ctx.warn).

Groups: group = video/case from <path>; cases that share >= MIN_SHARED_IDENTICAL byte-identical images are ONE video (merged into one group):
videos80 posttest/16 = pretest/11 and cvc300 case 11 = case 13. Both are flagged `duplicate-video`; every image that is byte-identical to
an image of another official split is flagged `split-leak-known` (7 cvc300 test images + their 7 train twins).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict

from .. import common as c

META = dict(
    dataset="polypsset",
    folder="PolypsSet",
    license="unknown",                      # no README / licence file shipped; the parts come from several public datasets
    procedure="colonoscopy",
    imaging="unknown",                      # NBI is known only for two sub-sets (set per row); not recorded per file
    region="lower-gi-tract",
    site="colon",
    location_source="dataset-constant",
    citation="Li K. et al., Colonoscopy polyp detection and classification: Dataset creation and comparative evaluations, PLOS ONE 2021",
    expected={"image": 37899},
)

SPLITS = {"train2019": "train", "val2019": "val", "test2019": "test"}
NBI_SUBSETS = {"nbi_adenoma", "set1_hyperplastic"}      # named NBI in the source folders (`NBI-Dataset`, `hyperplastic_NN_NBI`)
MIN_SHARED_IDENTICAL = 3                                # cases sharing >= this many identical images are one video

# <path> -> (sub-set, case id, source frame number). Group names are derived from these, never the raw path.
_PATH_RULES = [
    ("videos80", re.compile(r"/80_Videos_Frames/(pretest|posttest)/(\d+)/(\d+)\.jpg$"), lambda m: (f"videos80-{m[1]}-{int(m[2])}", int(m[3]))),
    ("miccai2017_train", re.compile(r"/MICCAI2017/train/(\d+)/Original/(\d+)\.bmp$"), lambda m: (f"miccai2017_train-{int(m[1])}", int(m[2]))),
    ("miccai2017_test", re.compile(r"/MICCAI2017_Test/test/(\d+)/(\d+)\.png$"), lambda m: (f"miccai2017_test-{int(m[1])}", int(m[2]))),
    ("nbi_adenoma", re.compile(r"/NBI-Frames/adenoma_(\d+)$"), lambda m: (f"nbi_adenoma-{int(m[1])}", None)),   # frame number is in <filename>
    ("set1_hyperplastic", re.compile(r"/Set1_Frames/hyperplastic/hyperplastic_(\d+)_NBI/(\d+)\.bmp$"),
     lambda m: (f"set1_hyperplastic-{int(m[1])}", int(m[2]))),
    ("cvc300", re.compile(r"/CVC-300/(\d+)/(\d+)\.bmp$"), lambda m: (f"cvc300-{int(m[1])}", int(m[2]))),
]
_NBI_FRAME = re.compile(r"^adenoma_(\d+)\.jpg$")


def _origin(path_text: str, filename: str):
    """(sub_set, case, frame_no) from the XML <path>/<filename>; None if no rule matches."""
    for subset, rx, fn in _PATH_RULES:
        m = rx.search(path_text or "")
        if m:
            case, frame = fn(m)
            if frame is None:
                mf = _NBI_FRAME.match(filename or "")
                frame = int(mf.group(1)) if mf else None
            return subset, case, frame
    return None


def _parse_xml(p):
    r = ET.parse(p).getroot()
    objs = []
    for o in r.findall("object"):
        bb = o.find("bndbox")
        objs.append((o.findtext("name", "").strip(), *(int(bb.findtext(k).strip()) for k in ("xmin", "ymin", "xmax", "ymax"))))
    sz = r.find("size")
    return dict(path=r.findtext("path", ""), filename=r.findtext("filename", ""), W=int(sz.findtext("width").strip()),
                H=int(sz.findtext("height").strip()), objs=objs)


def _merge_cases(case_pairs: dict[tuple[str, str], int]) -> dict[str, str]:
    """case -> merged group name; cases linked by >= MIN_SHARED_IDENTICAL identical images are joined (union-find), name = sorted members joined by '+'."""
    parent: dict[str, str] = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for (a, b), n in case_pairs.items():
        if n >= MIN_SHARED_IDENTICAL:
            parent[find(b)] = find(a)
    members = defaultdict(list)
    for k in list(parent):
        members[find(k)].append(k)
    return {k: "+".join(sorted(ms)) for ms in members.values() if len(ms) > 1 for k in ms}


def build(ctx):
    root = ctx.root
    # ---- 1. pair every XML with its JPEG (relative key = <split>/<sub>/<stem>)
    entries, orphan_xml, orphan_img = [], defaultdict(list), []
    for split in SPLITS:
        ann_dir, img_dir = root / split / "Annotation", root / split / "Image"
        xmls = {p.relative_to(ann_dir).with_suffix("").as_posix(): p for p in ann_dir.rglob("*.xml")}
        jpgs = {p.relative_to(img_dir).with_suffix("").as_posix(): p for p in img_dir.rglob("*.jpg")}
        for k in sorted(set(xmls) - set(jpgs), key=c.natural_key):
            orphan_xml[split].append(f"{split}/Annotation/{k}.xml")
        orphan_img += [f"{split}/{k}" for k in sorted(set(jpgs) - set(xmls), key=c.natural_key)]
        for k in sorted(set(xmls) & set(jpgs), key=c.natural_key):
            entries.append((split, k, xmls[k], jpgs[k]))
    if orphan_xml:
        ctx.warn(f"{sum(map(len, orphan_xml.values())):,} annotation XML(s) have no JPEG - no rows, their boxes are lost "
                 f"({', '.join(f'{s}: {len(v)}' for s, v in orphan_xml.items())}; e.g. {next(iter(orphan_xml.values()))[:3]})")
    if orphan_img:
        ctx.warn(f"{len(orphan_img)} JPEG(s) have no XML (no rows): {orphan_img[:3]}")

    # ---- 2. parse XMLs, real image sizes (header only), md5 (for duplicate videos / split leaks; cached)
    parsed = [_parse_xml(x) for _, _, x, _ in entries]
    sizes = c.image_sizes([j for *_, j in entries])
    md5 = ctx.md5([ctx.rel(j) for *_, j in entries])
    n_size = sum((p["W"], p["H"]) != s for p, s in zip(parsed, sizes))
    if n_size:
        ctx.warn(f"{n_size} XML(s) state a size different from the real JPEG (real size used)")

    # ---- 3. origin sub-set / case / frame number per image
    origin = []
    for p in parsed:
        o = _origin(p["path"], p["filename"])
        origin.append(o)
    n_unknown = sum(o is None for o in origin)
    if n_unknown:
        ctx.warn(f"{n_unknown} XML <path> value(s) match no known source pattern (no case / group for these rows)")

    # ---- 4. duplicate videos (cases sharing identical images) and split leaks (identical images in different official splits)
    by_md5 = defaultdict(list)
    for i, (split, k, _, j) in enumerate(entries):
        by_md5[md5[ctx.rel(j)]].append(i)
    case_pairs: dict[tuple[str, str], int] = defaultdict(int)
    leak = set()
    for idxs in by_md5.values():
        if len(idxs) < 2:
            continue
        cases = sorted({origin[i][1] for i in idxs if origin[i]})
        for a in range(len(cases)):
            for b in range(a + 1, len(cases)):
                case_pairs[(cases[a], cases[b])] += 1
        if len({entries[i][0] for i in idxs}) > 1:
            leak.update(idxs)
    merged = _merge_cases(case_pairs)
    if merged:
        ctx.log(f"   duplicate videos merged into one group: {sorted(set(merged.values()))}")

    # ---- 5. case-level histology (constant per case) and box-convention evidence
    case_classes = defaultdict(set)
    for p, o in zip(parsed, origin):
        if o:
            case_classes[o[1]].update(n for n, *_ in p["objs"])
    edge_w = edge_h = edge_w1 = edge_h1 = 0
    for p in parsed:
        for _, x0, y0, x1, y1 in p["objs"]:
            edge_w += x1 == p["W"]; edge_w1 += x1 == p["W"] - 1; edge_h += y1 == p["H"]; edge_h1 += y1 == p["H"] - 1
    ctx.log(f"   VOC max-edge evidence: xmax==W {edge_w} vs W-1 {edge_w1}; ymax==H {edge_h} vs H-1 {edge_h1} -> half-open edges (voc_to_box subtracts 1)")

    # ---- 6. rows
    rows = []
    for i, ((split, k, xml_p, jpg_p), p, (W, H), o) in enumerate(zip(entries, parsed, sizes, origin)):
        subset, case, frame = o if o else (None, None, None)
        img_rel, ann_rel = ctx.rel(jpg_p), ctx.rel(xml_p)
        item = f"{split}/Image/{k}"
        # labels + boxes
        boxes = []
        for name, x0, y0, x1, y1 in p["objs"]:
            lab_o = ctx.label(name)
            xmin, ymin, xmax, ymax = c.voc_to_box(x0, y0, x1, y1, W, H)
            boxes.append({"label": c.slugify(name), "finding": lab_o["finding_harmonized"], "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                          "_name": name})
        names = {}
        for b in boxes:
            names[b["_name"]] = names.get(b["_name"], 0) + 1
        if not boxes:
            lab, fields = ctx.label("no-object-in-xml"), dict(finding_raw="no-object-in-xml", annotation_types="bbox", class_counts_json="{}")
            desc = "no polyp annotated (XML without object)"
        else:
            if len(names) == 1:
                (name,) = names
                lab = ctx.label(name)
                fields = dict(finding_raw=name)
            else:                                                      # not present in the data; kept so a changed dataset is still correct
                lab, fields = ctx.multi_label_fields(names, raw={n: n for n in names}), {}
            hcount = {}
            for b in boxes:
                hcount[b["finding"]] = hcount.get(b["finding"], 0) + 1
            fields.update(annotation_types="class|bbox", class_counts_json=c.compact_json(dict(sorted(hcount.items()))))
            desc = f"{len(boxes)} {'/'.join(sorted(names))} polyp box(es)"
        box_cols = c.box_columns([{kk: vv for kk, vv in b.items() if kk != "_name"} for b in boxes], "annotator")

        group = merged.get(case, case) if case else None
        flags = []
        if case in merged:
            flags.append("duplicate-video")
        if i in leak:
            flags.append("split-leak-known")
        extra = {"case": case, "orig_filename": p["filename"] or None, "histology_case": "/".join(sorted(case_classes[case])) if case and case_classes[case] else None}
        if case in merged:
            extra["merged_group"] = merged[case]
        if not boxes:
            extra["negative_basis"] = "xml without object"
        rows.append(ctx.row(
            "image", item_id=item, source_subset=subset, file_path=img_rel, image_path=img_rel, label_source=ann_rel, label_level="image",
            annotation_format="voc-xml", annotation_path=ann_rel,
            imaging="nbi" if subset in NBI_SUBSETS else "unknown",
            video_id=case, frame_index=frame,
            group_id=f"{META['dataset']}:{group}" if group else None, group_kind="video" if group else "none", group_quality="exact" if group else "none",
            split_official=SPLITS[split], qa_flags=c.pipe_join(flags), width=W, height=H,
            extra_json=c.compact_json({kk: vv for kk, vv in extra.items() if vv is not None}),
            annotation_source="PolypsSet Pascal-VOC XML (Li et al., PLOS ONE 2021); voc max edges are half-open",
            row_description=f"PolypsSet colonoscopy frame ({subset}, case {case}, source frame {frame}), shipped in {split}: {desc}.",
            **{**lab, **fields}, **box_cols))
    return rows
