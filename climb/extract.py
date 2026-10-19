"""One-off: cut sources/climb-sheet.png into transparent, ledge-aligned frames.

    uv run --python 3.12 --with "rembg[cpu]" --with pillow --with numpy --with scipy \\
        climb/extract.py sources/climb-sheet.png climb /tmp

The last argument is where the preview contact sheet and GIF go.
"""
import sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
from scipy import ndimage
from rembg import new_session, remove

sheet = Image.open(sys.argv[1]).convert("RGB"); out = Path(sys.argv[2]); prev = Path(sys.argv[3])
rgb_all = np.array(sheet)
RISE = 335  # ledge height above the floor, sheet px (frame 3: floor 442, wall top 107)
F = [  # name, panel, hold (ledge point at his grip) or (x, floor y) for floor frames, erase boxes
 ("prepare",    (0,70,267,465),     ("floor", 215, 442), []),
 ("jump",       (268,70,517,465),   ("floor", 483, 442), []),
 ("reach",      (517,70,790,465),   ("floor", 722, 442), []),
 ("grab",       (790,70,1031,465),  ("ledge", 850, 101), [(812,80,968,136), ("dark", 845,110,925,140, 165), ("all", 851,115,874,139)]),
 ("hang",       (1032,70,1289,465), ("ledge", 1116, 112), [(1080,80,1240,140)]),
 ("stabilise",  (1290,70,1536,465), ("ledge", 1380, 110), [(1340,80,1505,138), ("all", 1398,80,1452,136), ("dark", 1390,115,1460,146, 165)]),
 ("pull-up",    (38,545,325,945),   ("ledge", 124, 686), [(250,655,325,705), (236,688,262,725, 85),
     ("poly", (196,708),(214,716),(238,714),(242,705),(270,700),(270,790),(225,790),(223,760),(229,742),(224,729),(196,727))]),
 ("chest-over", (326,545,623,945),  ("ledge", 448, 705), []),
 ("knee-up",    (624,545,917,945),  ("ledge", 733, 765), []),
 ("stand-up",   (918,545,1232,945), ("ledge", 1027, 785), []),
 ("balance",    (1233,545,1536,945),("ledge", 1352, 815), [(1233,800,1536,822), ("all", 1233,822,1536,945)]),
]
sess = new_session("isnet-general-use")
cuts = []
for name, (x0,y0,x1,y1), anchor, erase in F:
    crop = rgb_all[y0:y1, x0:x1]
    a = np.array(remove(Image.fromarray(crop), session=sess))[:, :, 3].astype(float)
    # Firm up what background removal half-kept (white sleeves over white paper).
    a = np.clip((a - 30) * 255 / 90, 0, 255)
    sat = np.array(Image.fromarray(crop).convert("HSV"))[:, :, 1]
    for box in erase:  # stone left in: clear its greys (or "all" of it), keep skin and shoes
        if box[0] == "poly":  # wall seen between his limbs: clear it all
            m = Image.new("L", (x1 - x0, y1 - y0)); ImageDraw.Draw(m).polygon([(x - x0, y - y0) for x, y in box[1:]], fill=255)
            a[np.array(m) > 0] = 0
            continue
        if box[0] == "dark":  # stone touching the cloud: both grey, but stone is darker
            bx0, by0, bx1, by1, vmax = box[1:]
            sl = (slice(max(0,by0-y0), by1-y0), slice(max(0,bx0-x0), bx1-x0))
            v = np.array(Image.fromarray(crop).convert("HSV"))[:, :, 2]
            a[sl] = np.where((v[sl] < vmax) & (sat[sl] < 85), 0, a[sl])
            continue
        clear_all = box[0] == "all"
        bx0, by0, bx1, by1, *lim = box[1:] if clear_all else box  # optional 5th: saturation limit
        sl = (slice(max(0,by0-y0), by1-y0), slice(max(0,bx0-x0), bx1-x0))
        a[sl] = 0 if clear_all else np.where(sat[sl] < (lim[0] if lim else 85), 0, a[sl])
    solid = a > 128
    labels, n = ndimage.label(solid)
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
    keep = np.isin(labels, 1 + np.nonzero(sizes >= sizes.max() * 0.02)[0])
    near = ndimage.binary_dilation(keep, iterations=3)
    a = np.where(near, a, 0)
    # Fill pinholes where white shirt read as paper, not real gaps (between legs).
    holes = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(keep, 8), iterations=4)[8:-8, 8:-8]) & ~keep
    hl, hn = ndimage.label(holes)
    hs = ndimage.sum(np.ones_like(hl), hl, range(1, hn + 1))
    a[np.isin(hl, 1 + np.nonzero(hs < 300)[0])] = 255
    rgba = np.dstack([crop, a.astype(np.uint8)])
    kind, hx, hy = anchor
    hold = (hx - x0, (hy - RISE if kind == "floor" else hy) - y0)  # the ledge corner, panel px
    cuts.append((name, Image.fromarray(rgba), hold))

# One canvas for all, the ledge corner at the same pixel in each.
L = max(h[0] for _, _, h in cuts); T = max(h[1] for _, _, h in cuts)
W = max(L - h[0] + im.width for _, im, h in cuts); H = max(T - h[1] + im.height for _, im, h in cuts)
out.mkdir(parents=True, exist_ok=True)
frames = []
for i, (name, im, (hx, hy)) in enumerate(cuts, 1):
    c = Image.new("RGBA", (W, H)); c.paste(im, (L - hx, T - hy))
    bb = c.getbbox(); frames.append(c)
    c.save(out / f"{i:02d}-{name}.png", optimize=True)
print("canvas", W, H, "ledge corner", L, T, "floor y", T + RISE)

# previews: contact sheet + flipbook with a ledge drawn in
def bg():
    b = Image.new("RGBA", (W + 40, H + 20), (24, 28, 24, 255)); d = ImageDraw.Draw(b)
    d.rectangle([L, T, W + 40, T + RISE], fill=(110, 110, 104, 255))
    d.line([0, T + RISE, W + 40, T + RISE], fill=(150, 200, 140, 255), width=3)
    return b
tiles = []
for f in frames:
    b = bg(); b.alpha_composite(f); tiles.append(b)
cs = Image.new("RGBA", (tiles[0].width * 6, tiles[0].height * 2))
for i, t in enumerate(tiles): cs.paste(t, ((i % 6) * t.width, (i // 6) * t.height))
cs.convert("RGB").save(prev / "climb-contact.png")
tiles[0].save(prev / "climb.gif", save_all=True, append_images=tiles[1:] + [tiles[-1]] * 6, duration=140, loop=0)
