"""Build the cloud man's sprite atlases from manifest.toml and sources/.

    uv run --python 3.12 --with "rembg[cpu]" --with pillow --with numpy \
        --with scipy --with scikit-image build.py [--dump DIR]

--dump writes every cut frame of every sheet (used or not) to DIR as PNGs
with their ids, for choosing frames for an action. --preview FILE renders
every action with every head, composited the way cloudman.js does it.
"""

import json
import sys
import tomllib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from rembg import new_session, remove
from scipy import ndimage
from skimage.segmentation import watershed

HERE = Path(__file__).resolve().parent
OUT = HERE / "dist"
OUTLINE = 4            # px of cream paper edge around each cut-out (atlas scale)
SHADOW = (5, 6)        # px baked drop shadow, so the TV doesn't filter per frame
PAD = OUTLINE + max(SHADOW) + 4
PAPER = (244, 238, 224)

session = None


def cut_out(img):
    """RGBA cut-out of the figure in an RGB image (background removal)."""
    global session
    session = session or new_session("isnet-general-use")
    return np.array(remove(img, session=session))


def largest(mask):
    labels, n = ndimage.label(mask)
    if n <= 1:
        return mask
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
    return labels == 1 + int(np.argmax(sizes))


def paper_mask(rgb, thresh=60):
    bg = np.median(rgb[5:40, 5:200].reshape(-1, 3), 0)
    return np.abs(rgb.astype(int) - bg).sum(2) > thresh


def bands(mask, min_height=80):
    """Vertical extents of the rows of figures (bodies, not floating heads)."""
    rows, out, start = mask.sum(1), [], None
    for y, v in enumerate(rows):
        if v > 3 and start is None:
            start = y
        if v <= 3 and start is not None:
            if y - start > min_height:
                out.append((start, y))
            start = None
    return out


# ---- slicing sheets into frames ----------------------------------------------------

def frames_grid(rgb):
    """Frames separated by clear paper: [(row, col, box)]."""
    mask = ndimage.binary_opening(paper_mask(rgb), iterations=1)
    out = []
    for r, (y0, y1) in enumerate(bands(mask), 1):
        cols, start, c = mask[y0:y1].sum(0), None, 0
        for x, v in enumerate(cols):
            if v > 2 and start is None:
                start = x
            if v <= 2 and start is not None:
                if x - start > 25:
                    c += 1
                    out.append((r, c, (start, y0, x, y1), None))
                start = None
    return out


def frames_touching(rgb):
    """Figures whose feet overlap: flood out from each torso, so every shoe goes
    to the body it's attached to. Returns (row, col, box, region mask)."""
    mask = ndimage.binary_opening(paper_mask(rgb, 70), iterations=1)
    out = []
    for r, (y0, y1) in enumerate(bands(mask), 1):
        band = mask[y0:y1]
        h = y1 - y0
        # Seeds: one per figure, from the chest strip (torso + arms). Runs of
        # columns closer than 20px are the same figure (an arm beside its torso).
        s0, s1 = int(h * 0.12), int(h * 0.3)
        cols = band[s0:s1].sum(0) > 0
        runs, start = [], None
        for x, on in enumerate(np.append(cols, False)):
            if on and start is None:
                start = x
            elif not on and start is not None:
                if runs and start - runs[-1][1] < 20:
                    runs[-1] = (runs[-1][0], x)
                else:
                    runs.append((start, x))
                start = None
        markers = np.zeros(band.shape, int)
        for i, (a, b) in enumerate(runs, 1):
            markers[s0:s1, a:b] = np.where(band[s0:s1, a:b], i, 0)
        regions = watershed(np.zeros(band.shape), markers, mask=band)
        c = 0
        for label in range(1, len(runs) + 1):
            region = np.zeros(mask.shape, bool)
            region[y0:y1] = regions == label
            ys, xs = np.nonzero(region)
            if len(xs) < 2000:
                continue
            c += 1
            out.append((r, c, (xs.min(), y0, xs.max() + 1, y1), region))
    return out


def frames_single(rgb):
    return [(1, 1, (0, 0, rgb.shape[1], rgb.shape[0]), None)]


# ---- cutting one frame ---------------------------------------------------------------

def cut_frame(rgb, box, region, head_mode):
    """Headless body cut-out of one frame, in sheet px, plus its neck point."""
    m = 24
    x0, y0 = max(0, box[0] - m), max(0, box[1] - (m if head_mode == "vest" else 140))
    x1, y1 = min(rgb.shape[1], box[2] + m), min(rgb.shape[0], box[3] + m)
    crop = rgb[y0:y1, x0:x1]
    rgba = cut_out(Image.fromarray(crop))
    alpha = rgba[:, :, 3].astype(int)
    if region is not None:
        keep = ndimage.binary_dilation(region[y0:y1, x0:x1], iterations=3)
        alpha = np.where(keep, alpha, 0)
    alpha = np.where(alpha < 60, 0, alpha)

    if head_mode == "gap":
        # The drawn head floats above the collar: drop everything above the widest
        # empty band of rows in the upper half.
        rows = (alpha > 128).sum(1)
        best, run, cut = 0, None, None
        for y in range(len(rows) // 2):
            if rows[y] < 3:
                run = y if run is None else run
                if y - run + 1 > best:
                    best, cut = y - run + 1, y
            else:
                run = None
        if cut is not None:
            alpha[:cut] = 0
    else:
        # The drawn head sits on the shoulders: cut just above the waistcoat.
        hsv = np.array(Image.fromarray(crop).convert("HSV")).astype(int)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        vest = (h > 8) & (h < 30) & (s > 110) & (v > 60) & (v < 175) & (alpha > 128)
        vest[int(len(vest) * 0.75):] = False  # not the shoes
        vest = largest(ndimage.binary_opening(vest, iterations=2))
        top = np.nonzero(vest.any(1))[0][0]
        alpha[:top + 3] = 0  # a little into the waistcoat, so no cloud is left behind

    body = largest(alpha > 100)
    alpha = np.where(body | (ndimage.binary_dilation(body, iterations=2) & (alpha > 0)), alpha, 0)
    # Bright white shirt sometimes reads as background: fill enclosed holes and
    # small bites out of the outline.
    closed = ndimage.binary_closing(np.pad(body, 8), iterations=5)[8:-8, 8:-8]
    holes = ndimage.binary_fill_holes(closed) & ~body
    alpha[holes] = 255
    rgba[holes, :3] = crop[holes]
    rgba[:, :, 3] = alpha.astype(np.uint8)
    ys, xs = np.nonzero(alpha > 100)
    top = ys.min()
    neck_rows = alpha[top:top + max(3, (ys.max() - top) // 30)] > 100
    neck_x = np.nonzero(neck_rows.any(0))[0].mean()
    return rgba, (x0, y0), (neck_x, top), ys.max()  # cut-out, its sheet origin, neck, soles


def trousers(rgba):
    """Mask of the trousers: the lower body, minus the dark leather shoes."""
    a = rgba[:, :, 3] > 150
    ys = np.nonzero(a.any(1))[0]
    hsv = np.array(Image.fromarray(rgba[:, :, :3]).convert("HSV")).astype(int)
    shoe = (hsv[:, :, 2] < 150) | ((hsv[:, :, 1] > 120) & (hsv[:, :, 2] < 185))
    m = a & ~shoe
    m[:ys.min() + int((ys.max() - ys.min()) * 0.45)] = False
    return m


def recolour(rgba, ref):
    """Match a frame's trousers to a reference frame's (mean/spread per Lab channel),
    for frames the sheet drew in grey instead of khaki."""
    def lab(x):
        return np.array(Image.fromarray(x[:, :, :3]).convert("LAB")).astype(float)
    src_m, ref_m = trousers(rgba), trousers(ref)
    s, r = lab(rgba), lab(ref)
    out = s.copy()
    for c in range(3):
        sv, rv = s[:, :, c][src_m], r[:, :, c][ref_m]
        out[:, :, c][src_m] = (sv - sv.mean()) / (sv.std() + 1e-6) * rv.std() + rv.mean()
    rgb = np.array(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "LAB").convert("RGB"))
    rgba = rgba.copy()
    rgba[src_m, :3] = rgb[src_m]
    return rgba


def feet(st):
    """Back and front shoe of a sticker (walking right): [(x, sole y), ...] by x."""
    a = np.array(st)
    alpha = a[:, :, 3] > 150
    ys = np.nonzero(alpha.any(1))[0]
    hsv = np.array(Image.fromarray(a[:, :, :3]).convert("HSV")).astype(int)
    shoe = alpha & (hsv[:, :, 2] < 170) & (hsv[:, :, 1] > 90)
    shoe[:ys.max() - int((ys.max() - ys.min()) * 0.14)] = False
    labels, n = ndimage.label(ndimage.binary_opening(shoe, iterations=1))
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
    best = sorted(np.argsort(sizes)[-2:] + 1)
    out = []
    for lb in best:
        yy, xx = np.nonzero(labels == lb)
        out.append((float(xx.mean()), float(yy.max())))
    return sorted(out)


def advances(frames, plant):
    """Per-frame travel (atlas px) that keeps the weight-bearing shoe still.
    plant[i] is "back", "front" or "low" (the lower shoe) for frames[i]; a switch
    from "back" to "front" is a new step, landing the previous front foot."""
    def pos(f, which):
        b, fr = f["feet"]
        if which == "low":
            which = "back" if b[1] >= fr[1] else "front"
        return (b if which == "back" else fr)[0] - f["ground"][0]
    out = []
    for i, f in enumerate(frames):
        prev, pp = frames[i - 1], plant[i - 1]
        was = "front" if (pp == "back" and plant[i] == "front") else pp
        out.append(round(pos(prev, was) - pos(f, plant[i]), 1))
    return out


def sticker(rgba):
    """Add a cream paper edge and a soft baked drop shadow."""
    img = ImageOps.expand(Image.fromarray(rgba), PAD, fill=(0, 0, 0, 0))
    alpha = img.getchannel("A").point(lambda v: 255 if v > 100 else 0)
    edge = alpha.filter(ImageFilter.MaxFilter(OUTLINE * 2 + 1)).filter(ImageFilter.GaussianBlur(0.8))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 90), SHADOW, edge.filter(ImageFilter.GaussianBlur(3)))
    paper = Image.new("RGBA", img.size, PAPER + (0,))
    paper.putalpha(edge)
    return Image.alpha_composite(Image.alpha_composite(shadow, paper), img)


# ---- heads --------------------------------------------------------------------------------

def build_head(spec, heads):
    if "derive" in spec:
        base = heads[spec["derive"]]["img"]
        cloud, rain = base if isinstance(base, tuple) else (base, None)
        rgb = Image.merge("RGB", [c.point(lambda v, k=k: int(v * k))
                                  for c, k in zip(cloud.convert("RGB").split(), spec["tint"])])
        img = rgb.convert("RGBA")
        img.putalpha(cloud.getchannel("A"))
        return (img, rain) if rain else img
    src = Image.open(HERE / spec["source"]).convert("RGB")
    if "crop" in spec:
        src = src.crop(spec["crop"])
    a = cut_out(src)
    rain = None
    if spec.get("rain"):
        # Background removal drops the thin rain streaks under the cloud: key
        # them out of the paper instead, as a translucent layer without a paper
        # edge (see head_sticker).
        solid = largest(a[:, :, 3] > 128)
        base = np.nonzero(solid.any(1))[0].max() - 6
        rgb = np.array(src).astype(int)
        paper = np.median(rgb[:8].reshape(-1, 3), 0)
        dark = np.clip((paper.sum() - rgb.sum(2)) / 3, 0, None)
        # Streaks only: darkness above its horizontal neighbourhood, not shading.
        streak = dark - ndimage.uniform_filter1d(dark, 9, axis=1)
        ra = np.clip((streak - 2) * 12, 0, 170).astype(np.uint8)
        ra[:base] = 0
        rain = np.zeros_like(a)
        rain[:, :, :3] = (176, 188, 206)
        rain[:, :, 3] = ra
    if spec.get("cutout") == "disc":
        # Keep just the disc: fit a circle to the largest blob by its area.
        blob = largest(a[:, :, 3] > 200)
        cy, cx = ndimage.center_of_mass(blob)
        r = np.sqrt(blob.sum() / np.pi) * 0.98
        yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]
        a[:, :, 3] = np.where((yy - cy) ** 2 + (xx - cx) ** 2 <= r * r, 255, 0)
    else:
        a[:, :, 3] = np.where(a[:, :, 3] < 40, 0, a[:, :, 3])
    img = Image.fromarray(a)
    if rain is None:
        return img.crop(img.getbbox())
    box = Image.fromarray(np.maximum(a[:, :, 3], rain[:, :, 3])).getbbox()
    return img.crop(box), Image.fromarray(rain).crop(box)


def head_sticker(img):
    """Sticker for a head; a (cloud, rain) pair gets its edge round the cloud only."""
    if not isinstance(img, tuple):
        return sticker(np.array(img))
    cloud, rain = img
    st = sticker(np.array(cloud))
    layer = ImageOps.expand(rain, PAD, fill=(0, 0, 0, 0))
    return Image.alpha_composite(layer, st)


# ---- atlas -----------------------------------------------------------------------------------

def pack(images, width=2048):
    """Shelf-pack {name: image} into one atlas: (atlas, {name: (x, y, w, h)})."""
    x = y = shelf = 0
    boxes = {}
    for name, im in sorted(images.items(), key=lambda kv: -kv[1].height):
        if x + im.width > width:
            x, y, shelf = 0, y + shelf + 2, 0
        boxes[name] = (x, y, im.width, im.height)
        x += im.width + 2
        shelf = max(shelf, im.height)
    atlas = Image.new("RGBA", (width, y + shelf), (0, 0, 0, 0))
    for name, (bx, by, _, _) in boxes.items():
        atlas.paste(images[name], (bx, by))
    return atlas, boxes


def main():
    dump = Path(sys.argv[sys.argv.index("--dump") + 1]) if "--dump" in sys.argv else None
    cfg = tomllib.loads((HERE / "manifest.toml").read_text())
    H = cfg["body_height"]
    wanted = {f for a in cfg["actions"].values() for f in a["frames"]}
    wanted |= {g for sp in cfg["sheets"].values() for g in sp.get("recolour", {}).values()}

    bodies, frames = {}, {}
    for sheet, spec in cfg["sheets"].items():
        rgb = np.array(Image.open(HERE / spec["source"]).convert("RGB"))
        slicer = {"grid": frames_grid, "touching": frames_touching, "single": frames_single}[spec["layout"]]
        cuts = {}
        for r, c, box, region in slicer(rgb):
            fid = f"{sheet}.{r}.{c}"
            if fid not in wanted and not dump:
                continue
            cuts[fid] = (r,) + cut_frame(rgb, box, region, spec["head"])
            print("cut", fid, flush=True)
        if not cuts:
            continue
        # Each row of a sheet shares a ground line: the lowest soles in that row.
        ground = {}
        for fid, (r, _, origin, _, soles) in cuts.items():
            ground[r] = max(ground.get(r, 0), origin[1] + soles)
        heights = {fid: origin[1] + soles - (origin[1] + neck[1])
                   for fid, (r, _, origin, neck, soles) in cuts.items()}
        if spec["scale"] == "median":
            ref = float(np.median(list(heights.values())))
        elif isinstance(spec["scale"], str):
            ref = heights[spec["scale"]]
        else:  # a fraction: this sheet's (only) frame is that much of a standing height
            ref = list(heights.values())[0] / spec["scale"]
        k = H / ref
        for bad, good in spec.get("recolour", {}).items():
            r, rgba, *rest = cuts[bad]
            cuts[bad] = (r, recolour(rgba, cuts[good][1]), *rest)
        for fid, (r, rgba, origin, neck, soles) in cuts.items():
            img = Image.fromarray(rgba)
            img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
            bbox = img.getbbox()
            img = img.crop(bbox)
            st = sticker(np.array(img))
            ox, oy = bbox[0] - PAD, bbox[1] - PAD  # sticker origin in the scaled cut-out
            neck_xy = (neck[0] * k - ox, neck[1] * k - oy)
            ground_y = (ground[r] - origin[1]) * k - oy
            bodies[fid] = st
            # Where the drawn anvil sat on the shoulders, draping heads (the cloud)
            # hang lower so their rain falls over the shoulders, as drawn.
            frames[fid] = {"neck": [round(neck_xy[0], 1), round(neck_xy[1], 1)],
                           "drop": round(spec.get("neck_drop", 0) * H, 1),
                           "ground": [round(neck_xy[0], 1), round(ground_y, 1)],
                           "facing": spec["facing"]}
            if spec["facing"]:
                frames[fid]["feet"] = [[round(x, 1), round(y, 1)] for x, y in feet(st)]
            if dump:
                dump.mkdir(parents=True, exist_ok=True)
                st.save(dump / f"{fid}.png")

    heads, head_meta = {}, {}
    for name, spec in cfg["heads"].items():
        base = spec.get("derive")
        img = build_head(spec, heads)
        heads[name] = {"img": img}
        src = cfg["heads"][base] if base else spec
        w = round(src["width"] * H)
        first = img[0] if isinstance(img, tuple) else img
        size = (w, round(first.height * w / first.width))
        img = tuple(i.resize(size, Image.LANCZOS) for i in img) if isinstance(img, tuple) \
            else img.resize(size, Image.LANCZOS)
        st = head_sticker(img)
        ax, ay = src["anchor"]
        head_meta[name] = {"anchor": [round(PAD + ax * size[0], 1), round(PAD + ay * size[1], 1)],
                           "drape": bool(src.get("drape"))}
        heads[name]["sticker"] = st

    OUT.mkdir(parents=True, exist_ok=True)
    body_atlas, body_boxes = pack({f: bodies[f] for f in frames if f in wanted})
    head_atlas, head_boxes = pack({n: h["sticker"] for n, h in heads.items()}, width=1024)
    body_atlas.save(OUT / "bodies.webp", quality=88, method=6)
    head_atlas.save(OUT / "heads.webp", quality=90, method=6)
    actions = {}
    for name, a in cfg["actions"].items():
        a = dict(a)
        if "plant" in a:
            a["advance"] = advances([frames[f] for f in a["frames"]], a.pop("plant"))
        actions[name] = a
    meta = {
        "bodyHeight": H,
        "frames": {f: {"box": body_boxes[f], **frames[f]} for f in body_boxes},
        "heads": {n: {"box": head_boxes[n], **head_meta[n]} for n in head_boxes},
        "actions": actions,
    }
    (OUT / "character.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"bodies.webp {body_atlas.size}, heads.webp {head_atlas.size}, "
          f"{len(body_boxes)} frames, {len(head_boxes)} heads")
    if "--preview" in sys.argv:
        preview(sys.argv[sys.argv.index("--preview") + 1])


def preview(path):
    """Contact sheet: one row per (action, head), frames composited like cloudman.js."""
    meta = json.loads((OUT / "character.json").read_text())
    bodies, heads = Image.open(OUT / "bodies.webp"), Image.open(OUT / "heads.webp")
    H = meta["bodyHeight"]
    cell_w, cell_h = int(H * 0.9), int(H * 1.75)
    rows = [(a, h) for a in meta["actions"] for h in meta["heads"]]
    ncols = max(len(a["frames"]) for a in meta["actions"].values())
    sheet = Image.new("RGB", (ncols * cell_w, len(rows) * cell_h), (14, 30, 18))
    for r, (action, head) in enumerate(rows):
        for c, fid in enumerate(meta["actions"][action]["frames"]):
            f, hd = meta["frames"][fid], meta["heads"][head]
            bx, by, bw, bh = f["box"]
            gx, gy = c * cell_w + cell_w / 2, (r + 1) * cell_h - 20  # ground point
            ox, oy = gx - f["ground"][0], gy - f["ground"][1]
            body = bodies.crop((bx, by, bx + bw, by + bh))
            sheet.paste(body, (round(ox), round(oy)), body)
            hx, hy, hw, hh = hd["box"]
            hi = heads.crop((hx, hy, hx + hw, hy + hh))
            drop = f["drop"] if hd["drape"] else 0
            sheet.paste(hi, (round(ox + f["neck"][0] - hd["anchor"][0]),
                             round(oy + f["neck"][1] + drop - hd["anchor"][1])), hi)
    sheet.save(path)
    print("preview", path, sheet.size)


if __name__ == "__main__":
    if "--preview" in sys.argv and "--only-preview" in sys.argv:
        preview(sys.argv[sys.argv.index("--preview") + 1])
        sys.exit()
    main()
