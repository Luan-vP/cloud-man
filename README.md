# The cloud man

A headless man in a tweed waistcoat whose head is weather. He lives here and
is pulled into the projects he appears in as a git submodule (first:
home-infra's admin-dash, a task board on a tiny TV). He's a rig, not a set of
finished sprites:

- **Bodies** are cut from sprite sheets with their drawn heads removed. Every
  frame records two points: the **neck** (where a head goes) and the
  **ground** (where his soles meet the floor, so airborne jump frames keep
  their height).
- **Heads** (`cloud`, `storm`, `sun`, `moon`) are cut once and composited over
  any body at runtime. Which one he wears is up to the page.

So a new action sheet works with every head, and a new head works with every
action, without N×M images.

```
manifest.toml     heads, sheets and actions (the only file you normally edit)
build.py          cuts sources/ into dist/
sources/          original art: cloud-portrait.jpg (the anvil head, idle pose),
                  walk-sheet.png, jump-sheet.png, and stills from the cloud
                  flipbook videos (sun, moon, kneel)
dist/             generated, committed, served by the pages that use him
  bodies.webp     every body frame used by an action
  heads.webp      every head
  character.json  frame boxes, neck/ground points, head anchors, actions
cloudman.js       runtime: loads dist/, runs his behaviours, draws him on a canvas
sprites/          the same animations as plain transparent frames, no rig needed
                  (plus the climb); see sprites/README.md
```

## Using him in a project

```sh
git submodule add https://github.com/Luan-vP/cloud-man.git static/cloud-man
```

Use the https URL, so machines that only have a deploy key for the parent
repo can still fetch it. After cloning the parent, `git submodule update --init`
(or `git config submodule.recurse true` once, so `git pull` keeps it in step).

Serve the submodule directory, then from a module script:

```js
import { load, CloudMan, rain } from "./cloud-man/cloudman.js";

const man = new CloudMan(await load("cloud-man/dist/"), {
  fps: 8,                                  // how often you call step()
  choose: () => "walk",                    // next behaviour when one ends
  onChange: m => console.log(m.state),     // e.g. give him a line to say
});

setInterval(() => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  man.bodyH = 200;                         // standing height in px: his scale
  man.step([0, canvas.width]);             // the x range he may roam, px
  const head = man.draw(ctx, 0, floorY, "cloud");
  // head = { x, y, top, bottom, halfWidth }: place speech or effects around it.
}, 1000 / 8);
```

Behaviours are `stand`, `think`, `walk`, `kneel`, `sleep`, `jump` and `hop`,
mapped to the manifest's actions in `ACTION` (`cloudman.js`). `man.play(state,
zone)` starts one immediately. Looping behaviours last `DURATION` ticks;
one-shot ones as long as they play; a walk ends when he reaches a random
target in the zone. `rain()` draws falling data under a cloud head for pages
laid out as a character grid.

Each project pins the commit it was tested with: to take new art or
behaviours, `git submodule update --remote`, check the page, and commit the
bump.

## Building

On a Mac (needs `uv`; the first run downloads a ~180 MB background-removal model):

```sh
uv run --python 3.12 --with "rembg[cpu]" --with pillow --with numpy \
    --with scipy --with scikit-image build.py --preview /tmp/cloudman.png
```

`--preview` renders every action with every head the way `cloudman.js`
composites them: check it before committing. `--dump DIR` writes every frame
of every sheet as `<sheet>.<row>.<col>.png`, used or not, for choosing frames.

## Adding an action

1. Put the sheet in `sources/`. Plain paper background, figures in rows.
2. Add a `[sheets.<name>]` entry: `layout` (`grid` if figures are separated by
   paper, `touching` if they overlap), `head` (`gap` if the drawn head floats
   above the collar, `vest` if it sits on the shoulders), `scale` (a standing
   frame, or `median`), `facing`.
3. `--dump` it and pick frames; add `[actions.<name>]` with the frame ids.
4. Map a behaviour to it in `ACTION` in `cloudman.js` (and `DURATION` if it
   loops), then have the pages that use him choose it.

## Adding a head

Add `[heads.<name>]` with a source and crop (or `derive` from another head with
a `tint`), a `width` and the `anchor` that sits on the neck. Pages wear it by passing its
name to `draw()`. A head can also have a `behind` layer, drawn behind the body:
the sun's rays are one (`cutout = "rays"`), so his collar sits in front of them
as it does in the video.

## Notes on the current art

- **Walk sheet:** it isn't a true cycle. Almost every frame is the same
  wide-stride pose, so the action is built from its phases: heel strike
  (row 1), push-off (row 2), toe-off (2.3) and passing (1.11, the only one).
  Several frames have grey trousers instead of khaki (1.6–1.9, 2.1, 2.2, 2.10,
  2.11) and 1.9 has a stray blob at the hip; those aren't used.
- **Jump sheet:** "takeoff" (x.2) is a sideways run in the other direction, so
  it's skipped. The drawn anvils vary frame to frame and the back-view recovery
  (2.7) has the vest showing through, which is why heads are replaced.
- **Kneel** is a still from the flipbook video, so its waistcoat is greener than
  the watercolour sheets. Replace it when there's a kneel sheet.
