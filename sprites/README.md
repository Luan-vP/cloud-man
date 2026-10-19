# Sprites

The cloud man as plain frames: transparent PNGs, one folder per animation,
ready to drop into a page or a game without the rig. Every set is scaled so
his standing body (collar to soles) is 215 px, so sets can be mixed at the
same size.

Within a set every frame shares one canvas and one **anchor**, a pixel that
stays put in the world. Draw each frame with its anchor at the same spot and
the set plays as a flipbook. Scale the canvas uniformly and the anchor scales
with it. `preview.gif` in each animated set plays it.

| set | frames | canvas | anchor | at the anchor |
|---|---|---|---|---|
| `climb/` | 11 | 388 × 642 | (219, 274) | the ledge's top-left corner |
| `climb-headless/` | 11 | 388 × 642 | (219, 274) | the ledge's top-left corner |
| `walk/` | 10, looping | 186 × 366 | (92, 338) | the floor, under his neck |
| `jump/` | 6 | 224 × 460 | (114, 429) | the floor, under his neck |
| `jump-away/` | 6 | 228 × 433 | (112, 401) | the floor, under his neck |
| `kneel/` | 1 | 331 × 331 | (103, 291) | the floor, under his neck |

About 7–8 fps reads well throughout.

## climb

Jumps up to a ledge, grabs it, pulls himself up and stands on it:
prepare, jump, reach, grab, hang, stabilise, pull-up, chest-over, knee-up,
stand-up, balance. The floor is at y = 609, so the ledge is 335 px high.
Frames 01–03 are on the floor, 04–10 hold the ledge, 11 stands on top. From
`sources/climb-sheet.png`, drawn heads kept.

The sheet turns from a side view (01–03) to a back view in front of the wall
(04 on), so 04–11 are shifted 40 sheet px left to bring his grab to the corner.

## climb-headless

The climb with its drawn anvil cut away, so the rig's other heads (sun, moon)
can be worn while climbing. `necks.json` lists each frame's neck: the canvas
px where a head's `anchor` goes, the same as a rig frame's `neck`. Heads from
`dist/heads.webp` are in rig px, so draw them at `bodyH / bodyHeight` (215 /
340 at this set's scale). The cloud head should wear `climb/` instead, whose
drawn anvils match.

Where an arm crosses the anvil (02–06) only its cool grey core is cut, so the
sleeves under it stay; a little of the wings is left there and a worn head
covers most of it. Made by `headless.py` (no background removal needed):

    uv run --python 3.12 --with pillow --with numpy --with scipy --with scikit-image \
        sprites/headless.py --preview /tmp/climb-heads.png

## walk

One step on each foot: load, toe-off, passing, swing, reach, twice. He walks
in place: to walk right, move him forward by this many px as each frame
appears (at 215 px scale), which keeps the planted shoe still:

    9.0, 10.0, 13.9, 21.0, 31.6, 17.7, 5.9, 13.9, 21.0, 28.5

Frames 02/07, 03/08 and 04/09 are the same drawings: the sheet has only one
passing pose. Flip horizontally to walk left. From `sources/walk-sheet.png`,
which isn't a true cycle (see the main README), so this is the rig's cycle
built from its phases. The sheet draws a puffy cumulus head; these wear his
anvil from `cloud-portrait.jpg` instead.

## jump, jump-away

A jump on the spot, side view (`jump/`) and from behind (`jump-away/`):
prepare, rising, peak, falling, landing, recovery. Airborne frames keep
their height above the floor. The sheet's "takeoff" frames are left out (a
sideways run the wrong way). From `sources/jump-sheet.png`, drawn heads kept.

## kneel

A single still from the cloud flipbook video (`sources/video-kneel.png`),
so its waistcoat is greener than the watercolour sheets', and it's upscaled
from a small source.

## Re-cutting

`extract.py` made all of these, once, from `sources/`. It reuses
`build.py`'s cutting helpers (the walk is cut exactly as the rig cuts it) and
hand-placed boxes clear the stone that background removal kept in the climb.

```sh
uv run --python 3.12 --with "rembg[cpu]" --with pillow --with numpy --with scipy \
    --with scikit-image sprites/extract.py [climb walk jump jump-away kneel] --preview /tmp
```
