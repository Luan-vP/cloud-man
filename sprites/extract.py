"""One-off: cut the cloud man's sheets into sets of transparent, aligned frames.

    uv run --python 3.12 --with "rembg[cpu]" --with pillow --with numpy --with scipy \\
        --with scikit-image sprites/extract.py [climb walk jump-right jump-left ...] [--preview DIR]

Writes sprites/<set>/NN-<name>.png (all sets by default). Every frame of a set
shares one canvas, aligned so the set plays as a flipbook drawn at one spot,
and every set is scaled so his body is the same size. --preview DIR also writes
<set>.gif and <set>-contact.png there for checking. See sprites/README.md.
"""

import functools
import sys
import tomllib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build as B  # noqa: E402  (its cutting helpers; build.py itself isn't run)

OUT = ROOT / "sprites"
BODY = 215   # standing body height, collar to soles, px: the climb sheet's own
PAD = 4


# ---- cutting -------------------------------------------------------------------------

def firm(alpha):
    """Background removal leaves white sleeves over white paper half transparent:
    firm up anything it half kept."""
    return np.clip((alpha.astype(float) - 30) * 255 / 90, 0, 255)


def tidy(a):
    """Keep every sizeable piece (a raised forearm can come loose), drop specks
    and drawn floor shadows, and fill pinholes where white shirt read as paper."""
    labels, n = ndimage.label(a > 128)
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
    keep = np.isin(labels, 1 + np.nonzero(sizes >= sizes.max() * 0.02)[0])
    a = np.where(ndimage.binary_dilation(keep, iterations=3), a, 0)
    holes = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(keep, 8), iterations=4)[8:-8, 8:-8]) & ~keep
    hl, hn = ndimage.label(holes)
    hs = ndimage.sum(np.ones_like(hl), hl, range(1, hn + 1))
    a[np.isin(hl, 1 + np.nonzero(hs < 60)[0])] = 255
    return a


def erase(a, crop, x0, y0, boxes):
    """Clear scenery background removal kept, by hand-placed boxes in sheet px:
    (x0, y0, x1, y1[, sat]) clears greys (stone), keeping skin, khaki and shoes;
    ("dark", ..., vmax) clears only darker greys (stone touching the cloud);
    ("all", ...) clears everything; ("poly", (x, y), ...) clears inside a polygon."""
    hsv = np.array(Image.fromarray(crop).convert("HSV")).astype(int)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    for box in boxes:
        if box[0] == "poly":
            m = Image.new("L", (crop.shape[1], crop.shape[0]))
            ImageDraw.Draw(m).polygon([(x - x0, y - y0) for x, y in box[1:]], fill=255)
            a[np.array(m) > 0] = 0
            continue
        kind, rest = (box[0], box[1:]) if isinstance(box[0], str) else ("grey", box)
        bx0, by0, bx1, by1, *lim = rest
        sl = (slice(max(0, by0 - y0), max(0, by1 - y0)), slice(max(0, bx0 - x0), max(0, bx1 - x0)))
        if kind == "all":
            a[sl] = 0
        elif kind == "dark":
            a[sl] = np.where((val[sl] < lim[0]) & (sat[sl] < 85), 0, a[sl])
        else:
            a[sl] = np.where(sat[sl] < (lim[0] if lim else 85), 0, a[sl])
    return a


def cut(rgb, box, boxes=()):
    """Transparent cut-out of a sheet region, drawn head and all."""
    x0, y0, x1, y1 = box
    crop = rgb[y0:y1, x0:x1]
    a = firm(B.cut_out(Image.fromarray(crop))[:, :, 3])
    a = tidy(erase(a, crop, x0, y0, boxes))
    return Image.fromarray(np.dstack([crop, a.astype(np.uint8)]))


def scaled(img, anchor, k):
    if k == 1:
        return img, anchor
    return (img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS),
            (anchor[0] * k, anchor[1] * k))


# ---- sets ------------------------------------------------------------------------------

def climb():
    """sources/climb-sheet.png: anchored on the ledge corner. Frames 01-03 stand
    on the floor, RISE below it; from 04 he holds the ledge top."""
    rgb = np.array(Image.open(ROOT / "sources/climb-sheet.png").convert("RGB"))
    RISE = 335   # ledge height, sheet px (frame 3: floor 442, wall top 107)
    SHIFT = 40   # the sheet turns from side to back view at 04: bring him to the corner
    frames = [  # name, panel, (on, hold x, y): the ledge point at his grip, or the floor's y
        ("prepare",    (0, 70, 267, 465),      ("floor", 215, 442), []),
        ("jump",       (268, 70, 517, 465),    ("floor", 483, 442), []),
        ("reach",      (517, 70, 790, 465),    ("floor", 722, 442), []),
        ("grab",       (790, 70, 1031, 465),   ("ledge", 850, 101),
         [(812, 80, 968, 136), ("dark", 845, 110, 925, 140, 165), ("all", 851, 115, 874, 139)]),
        ("hang",       (1032, 70, 1289, 465),  ("ledge", 1116, 112), [(1080, 80, 1240, 140)]),
        ("stabilise",  (1290, 70, 1536, 465),  ("ledge", 1380, 110),
         [(1340, 80, 1505, 138), ("all", 1398, 80, 1452, 136), ("dark", 1390, 115, 1460, 146, 165)]),
        ("pull-up",    (38, 545, 325, 945),    ("ledge", 124, 686),
         [(250, 655, 325, 705), (236, 688, 262, 725, 85),
          ("poly", (196, 708), (214, 716), (238, 714), (242, 705), (270, 700), (270, 790),
           (225, 790), (223, 760), (229, 742), (224, 729), (196, 727))]),
        ("chest-over", (326, 545, 623, 945),   ("ledge", 448, 705), []),
        ("knee-up",    (624, 545, 917, 945),   ("ledge", 733, 765), []),
        ("stand-up",   (918, 545, 1232, 945),  ("ledge", 1027, 785), []),
        ("balance",    (1233, 545, 1536, 945), ("ledge", 1352, 815),
         [(1233, 800, 1536, 822), ("all", 1233, 822, 1536, 945)]),
    ]
    out = []
    for name, box, (on, hx, hy), boxes in frames:
        img = cut(rgb, box, boxes)
        if on == "ledge":
            hx += SHIFT
        out.append((name, img, (hx - box[0], (hy - RISE if on == "floor" else hy) - box[1])))
    return out, {"rise": RISE}


def walk():
    """sources/walk-sheet.png, as the rig's walk cycle (manifest.toml): the sheet's
    puffy cumulus heads swapped for his anvil, from cloud-portrait.jpg. Anchored
    on the ground under his neck; he walks in place (travel in the README)."""
    cfg = tomllib.loads((ROOT / "manifest.toml").read_text())
    spec, cycle = cfg["sheets"]["walk"], cfg["actions"]["walk"]["frames"]
    rgb = np.array(Image.open(ROOT / spec["source"]).convert("RGB"))
    wanted = set(cycle) | set(spec["recolour"].values())
    cuts = {}
    for r, c, box, region in B.frames_touching(rgb):
        fid = f"walk.{r}.{c}"
        if fid in wanted:
            # The sheet's figures only touch at the feet, but the split between
            # them can bite into a swinging sleeve: split below the hips only.
            region = region.copy()
            x0, y0, x1, y1 = box
            region[y0:y0 + int((y1 - y0) * 0.55), max(0, x0 - 24):x1 + 24] = True
            cuts[fid] = (r,) + B.cut_frame(rgb, box, region, "gap")
            print("cut", fid, flush=True)
    for bad, good in spec["recolour"].items():
        r, rgba, *rest = cuts[bad]
        cuts[bad] = (r, B.recolour(rgba, cuts[good][1]), *rest)
    ground = {}
    for r, _, origin, _, soles in cuts.values():
        ground[r] = max(ground.get(r, 0), origin[1] + soles)
    k = BODY / float(np.median([soles - neck[1] for _, _, _, neck, soles in cuts.values()]))

    head_spec = cfg["heads"]["cloud"]
    cloud, rain = B.build_head(head_spec, {})
    head = Image.alpha_composite(rain, cloud)
    w = round(head_spec["width"] * BODY)
    head = head.resize((w, round(head.height * w / head.width)), Image.LANCZOS)
    ax, ay = head_spec["anchor"][0] * head.width, head_spec["anchor"][1] * head.height

    out = []
    for i, fid in enumerate(cycle):
        r, rgba, origin, neck, soles = cuts[fid]
        a = rgba[:, :, 3]
        rgba = rgba.copy()
        # build.py fills small gaps between the legs as if they were shirt;
        # clear whatever there is still the sheet's paper. Below the hips only:
        # the shirt's highlights are paper-coloured too.
        paper = np.abs(rgba[:, :, :3].astype(int) - np.median(rgb[5:40, 5:200].reshape(-1, 3), 0)).sum(2) < 18
        paper[:round(neck[1] + (soles - neck[1]) * 0.45)] = False
        rgba[:, :, 3] = tidy(firm(np.where(paper, 0, a))).astype(np.uint8)
        body, (nx, ny) = scaled(Image.fromarray(rgba), neck, k)
        top, left = round(max(0, ay - ny)) + PAD, round(max(0, ax - nx)) + PAD
        frame = Image.new("RGBA", (left + max(body.width, round(nx - ax + head.width)) + PAD, body.height + top))
        frame.alpha_composite(body, (left, top))
        frame.alpha_composite(head, (round(left + nx - ax), round(top + ny - ay)))
        phase = ["load", "toe-off", "passing", "swing", "reach"][i % 5]  # the manifest's gait order
        out.append((phase, frame, (left + nx, (ground[r] - origin[1]) * k + top)))
    advance = [round(v * BODY / cfg["body_height"], 1) for v in
               __import__("json").loads((ROOT / "dist/character.json").read_text())["actions"]["walk"]["advance"]]
    return out, {"advance": advance}


@functools.cache   # each row is cut once, for its -right and -left sets
def jump(row):
    """sources/jump-sheet.png, one row: 1 side view, 2 back view. Drawn heads kept.
    Anchored on the row's floor under his neck, so airborne frames keep their height.
    Takeoff (x.2) is skipped: it's a sideways run the wrong way. The back view's
    recovery (2.7) is mirrored to face the way the rest of its row does."""
    rgb = np.array(Image.open(ROOT / "sources/jump-sheet.png").convert("RGB"))
    names = {1: "prepare", 3: "rising", 4: "peak", 5: "falling", 6: "landing", 7: "recovery"}
    cuts, ground, ref = [], 0, None
    for r, c, box, _ in B.frames_grid(rgb):
        if c not in names or r not in (1, 2):
            continue
        _, origin, neck, soles = B.cut_frame(rgb, box, None, "vest")  # for his neck
        x0, y0 = origin
        x1, y1 = min(rgb.shape[1], box[2] + 24), min(rgb.shape[0], box[3] + 24)
        img = cut(rgb, (x0, y0, x1, y1))
        if r == 2 and c == 7:   # mirrored about his neck, so the anchor stays put
            img, neck = img.transpose(Image.FLIP_LEFT_RIGHT), (img.width - neck[0], neck[1])
        if r == 1 and c == 7:
            ref = soles - neck[1]   # the rig's standing frame (manifest: scale = "jump.1.7")
        if r == row:
            ground = max(ground, y0 + soles)
            cuts.append((names[c], img, origin, neck))
        print("cut", f"jump.{r}.{c}", flush=True)
    k = BODY / ref
    return [(name, *scaled(img, (neck[0], ground - origin[1]), k)) for name, img, origin, neck in cuts], {}


def kneel():
    """sources/video-kneel.png, a still from the cloud flipbook video: one frame,
    drawn head kept, on the ground under his neck."""
    rgb = np.array(Image.open(ROOT / "sources/video-kneel.png").convert("RGB"))
    box = (0, 0, rgb.shape[1], rgb.shape[0])
    _, origin, neck, soles = B.cut_frame(rgb, box, None, "gap")
    img = cut(rgb, box)
    k = BODY * 0.8 / (soles - neck[1])   # kneeling: 0.8 of a standing height, as in the rig
    return [("kneel", *scaled(img, (neck[0], soles), k))], {}


def mirror(made):
    """A set flipped left to right, each anchor with it: travelling the other way."""
    frames, extra = made
    return [(name, img.transpose(Image.FLIP_LEFT_RIGHT), (img.width - a[0], a[1]))
            for name, img, a in frames], extra


SETS = {"climb": climb, "walk": walk,
        "jump-right": lambda: jump(1), "jump-left": lambda: mirror(jump(1)),
        "jump-away-right": lambda: jump(2), "jump-away-left": lambda: mirror(jump(2)),
        "kneel": kneel}


# ---- output -------------------------------------------------------------------------

def save(name, frames, preview):
    """One canvas for the set, every frame's anchor at the same pixel."""
    L = max(round(a[0]) for _, _, a in frames) + PAD
    T = max(round(a[1]) for _, _, a in frames) + PAD
    W = max(L - round(a[0]) + im.width for _, im, a in frames) + PAD
    H = max(T - round(a[1]) + im.height for _, im, a in frames) + PAD
    d = OUT / name
    for old in d.glob("*.png"):
        old.unlink()
    d.mkdir(parents=True, exist_ok=True)
    canvases = []
    for i, (fname, im, a) in enumerate(frames, 1):
        c = Image.new("RGBA", (W, H))
        c.alpha_composite(im, (L - round(a[0]), T - round(a[1])))
        c = c.crop((0, 0, W, H))
        c.save(d / f"{i:02d}-{fname}.png", optimize=True)
        canvases.append(c)
    print(f"{name}: {len(frames)} frames, canvas {W}x{H}, anchor ({L}, {T})")
    if preview:
        tiles = []
        for c in canvases:
            bg = Image.new("RGBA", c.size, (24, 28, 24, 255))
            dr = ImageDraw.Draw(bg)
            if name == "climb":
                dr.rectangle([L, T, W, T + 335], fill=(110, 110, 104, 255))
                dr.line([0, T + 335, W, T + 335], fill=(150, 200, 140, 255), width=3)
            else:
                dr.line([0, T, W, T], fill=(150, 200, 140, 255), width=3)
            bg.alpha_composite(c)
            tiles.append(bg)
        cols = min(6, len(tiles))
        sheet = Image.new("RGBA", (W * cols, H * -(-len(tiles) // cols)))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * W, (i // cols) * H))
        sheet.convert("RGB").save(Path(preview) / f"{name}-contact.png")
        hold = [tiles[-1]] * (6 if name != "walk" else 0)
        tiles[0].save(Path(preview) / f"{name}.gif", save_all=True, append_images=tiles[1:] + hold,
                      duration=125 if name == "walk" else 140, loop=0)
    return W, H, L, T


if __name__ == "__main__":
    args = sys.argv[1:]
    preview = args[args.index("--preview") + 1] if "--preview" in args else None
    if preview:
        args = [a for a in args if a not in ("--preview", preview)]
    for name in args or SETS:
        frames, extra = SETS[name]()
        save(name, frames, preview)
        if extra:
            print(f"{name}: {extra}")
