# Headless climb: the climb frames with their drawn anvil removed, so the rig's
# heads (sun, moon, ...) can be worn over them, plus each frame's neck point.
#
#   uv run --python 3.12 --with pillow --with numpy --with scipy --with scikit-image \
#       sprites/headless.py [--preview OUT.png]
#
# Writes sprites/climb-headless/NN-name.png (same canvas and anchor as climb/)
# and sprites/climb-headless/necks.json: {"frames": [...], "neck": [[x, y], ...]}
# in canvas px, where a head's anchor goes.
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.morphology import convex_hull_image, disk

HERE = Path(__file__).parent
SRC, OUT = HERE / "climb", HERE / "climb-headless"

# The anvil is grey-white with cool shading; the shirt is warm white and the
# skin and waistcoat are saturated. So: low saturation, not warmer than blue.
def cloudy(a):
    rgb = a[..., :3].astype(int)
    sat = rgb.max(-1) - rgb.min(-1)
    return (a[..., 3] > 40) & (sat < 45) & (rgb[..., 2] >= rgb[..., 0] - 6)


# Frames whose arms reach up past the anvil: growing into unsaturated paint
# there would take the white sleeves too, so only the cool core is cut.
ARMS_UP = {"02-jump.png", "03-reach.png", "04-grab.png", "05-hang.png", "06-stabilise.png"}


def anvil_mask(a, grow=True):
    m = cloudy(a)
    lab, n = ndimage.label(ndimage.binary_closing(m, disk(9)))
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    big = lab == (1 + int(np.argmax(sizes)))
    hull = ndimage.binary_dilation(convex_hull_image(big), disk(3))
    # The wing tips are warmer grey than the core: grow into any unsaturated
    # paint that touches the hull, but not below the neck, where the shirt is.
    rgb = a[..., :3].astype(int)
    sat = rgb.max(-1) - rgb.min(-1)
    ys, xs = np.nonzero(big)
    neck_y = np.percentile(ys[np.abs(xs - np.median(xs)) < 12], 95)
    grey = (a[..., 3] > 0) & (sat < 60)
    grey[int(neck_y) - 4:] = False
    if not grow:
        grey[:] = False
    lab, _ = ndimage.label(grey | hull)
    hull |= np.isin(lab, np.unique(lab[hull])) & (lab > 0)
    hull = ndimage.binary_dilation(hull, disk(1))
    # Inside the anvil's hull keep only clearly saturated paint: hands and
    # forearms that cross it. Thin warm specks in the cloud go with it.
    keep = ndimage.binary_opening(sat > 70, disk(2))
    return hull & ~keep, big


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    names, necks, frames = [], [], []
    for f in sorted(SRC.glob("[0-9][0-9]-*.png")):
        a = np.asarray(Image.open(f).convert("RGBA")).copy()
        cut, big = anvil_mask(a, grow=f.name not in ARMS_UP)
        ys, xs = np.nonzero(big)
        # Neck: the bottom middle of the anvil, where it met the collar.
        cx = float(np.median(xs))
        col = ys[np.abs(xs - cx) < 12]
        neck = [round(cx, 1), round(float(np.percentile(col, 95)), 1)]
        a[cut, 3] = 0
        # Drop specks the cut left floating.
        lab, n = ndimage.label(a[..., 3] > 0)
        if n > 1:
            sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
            for i, s in enumerate(sizes, 1):
                if s < 150:
                    a[lab == i, 3] = 0
        Image.fromarray(a).save(OUT / f.name)
        names.append(f.name); necks.append(neck); frames.append(a)
        print(f.name, neck)
    (OUT / "necks.json").write_text(json.dumps({"frames": names, "neck": necks}, indent=1) + "\n")

    if args.preview:
        heads = Image.open(HERE.parent / "dist" / "heads.webp").convert("RGBA")
        char = json.loads((HERE.parent / "dist" / "character.json").read_text())
        s = 215 / char["bodyHeight"]
        h, w = frames[0].shape[:2]
        sheet = Image.new("RGBA", (w * len(frames), h * 2), (225, 235, 250, 255))
        for row, name in enumerate(["sun", "moon"]):
            hd = char["heads"][name]
            bx, by, bw, bh = hd["box"]
            head = heads.crop((bx, by, bx + bw, by + bh))
            head = head.resize((round(bw * s), round(bh * s)), Image.LANCZOS)
            for i, (a, nk) in enumerate(zip(frames, necks)):
                im = Image.fromarray(a)
                im.alpha_composite(head, (round(nk[0] - hd["anchor"][0] * s), round(nk[1] - hd["anchor"][1] * s)))
                sheet.alpha_composite(im, (i * w, row * h))
        sheet.save(args.preview)


if __name__ == "__main__":
    main()
