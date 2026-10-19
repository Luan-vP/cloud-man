# Climb: jump up and grab a ledge

Eleven frames cut from `sources/climb-sheet.png`, drawn heads and all, on
transparent backgrounds. `preview.gif` plays them against a stand-in ledge.

| | | | |
|---|---|---|---|
| 01 prepare | 02 jump | 03 reach | 04 grab |
| 05 hang | 06 stabilise | 07 pull-up | 08 chest-over |
| 09 knee-up | 10 stand-up | 11 balance | |

Every frame is the same 420 × 634 px canvas, positioned so the ledge is in the
same place in all of them. Draw them at one spot and they play as a flipbook:

- **ledge corner** (top-left of the ledge he climbs): (215, 270)
- **floor**: y = 605, so the ledge is 335 px high
- frames 01–03 stand on the floor; from 04 he holds the ledge top; 11 stands on it

Scale the canvas uniformly to fit a page; the anchors scale with it. About
7 fps reads well.

The sheet changes viewpoint at frame 04 (side view to back view, in front of
the wall), so he steps sideways onto the ledge between 03 and 04. That's the
art, not the alignment.

`extract.py` is the one-off script that made them, kept so they can be
re-cut. Stone the background removal left in is cleared by hand-placed boxes
in it.
