// The cloud man at runtime: loads the atlases build.py writes to dist/, runs
// his behaviours and draws him onto a 2D canvas. What he does and which head
// he wears are up to the page; this only knows how to animate them.
//
//   import { load, CloudMan } from "./cloud-man/cloudman.js";
//   const man = new CloudMan(await load("cloud-man/dist/"), { choose: () => "walk" });
//   // every tick:
//   man.bodyH = 200; man.step([0, canvas.width]); man.draw(ctx, 0, floorY, "cloud");
//
// x, the zone and the draw origin are all canvas px; bodyH is a standing
// body's height (collar to soles) in px, which sets his scale.

const image = src => new Promise((ok, fail) => {
  const im = new Image(); im.onload = () => ok(im); im.onerror = fail; im.src = src;
});

// base: the URL of dist/, with a trailing slash.
export async function load(base = "dist/") {
  const [meta, bodyAtlas, headAtlas] = await Promise.all([
    fetch(base + "character.json").then(r => r.json()),
    image(base + "bodies.webp"), image(base + "heads.webp")]);
  return { ...meta, bodyAtlas, headAtlas };
}

// Behaviours, each played with one of the rig's actions (manifest.toml).
export const ACTION = { stand: "idle", think: "idle", walk: "walk", kneel: "kneel", sleep: "kneel",
                        jump: "jump", hop: "jump-away" };
// Ticks a looping behaviour lasts; one-shot actions last as long as they play.
// A walk ends early when he reaches his target.
export const DURATION = { walk: 400, sleep: 200, think: 40, kneel: 48, stand: 32 };

export class CloudMan {
  // char: from load(). opts: fps (ticks per second step() is called at),
  // x and dir (1 = right, -1 = left) to start, choose() returning the next
  // behaviour, and onChange(man) called after each new behaviour starts.
  constructor(char, { fps = 8, x = 0, dir = -1, choose = () => "stand", onChange = () => {} } = {}) {
    Object.assign(this, { char, fps, x, dir, choose, onChange });
    this.state = "stand"; this.t = 0; this.until = 30; this.target = x; this.walkFrame = -1;
    this.bodyH = 100;
  }

  get scale() { return this.bodyH / this.char.bodyHeight; }
  // Half his width in px, for keeping him inside a zone.
  get halfWidth() { return this.bodyH * 0.3; }

  // Start a behaviour now. In zone [x0, x1] a walk picks a target to walk to.
  play(state, zone) {
    this.state = state; this.t = 0; this.walkFrame = -1;
    const a = this.char.actions[ACTION[state]];
    this.until = a && !a.loop ? Math.ceil(a.frames.length * this.fps / a.fps) : DURATION[state] ?? 32;
    if (state === "walk" && zone) {
      const span = Math.max(0, zone[1] - zone[0] - this.halfWidth * 2);
      this.target = zone[0] + this.halfWidth + Math.random() * span;
    }
    this.onChange(this);
  }

  // One tick, inside zone [x0, x1].
  step(zone) {
    this.x = Math.min(Math.max(this.x, zone[0] + this.halfWidth), zone[1] - this.halfWidth);
    if (++this.t >= this.until) this.play(this.choose(), zone);
    if (this.state !== "walk") return;
    // Move by each frame's own travel (from the build), which keeps the
    // weight-bearing shoe planted, so his feet don't skate.
    const a = this.char.actions.walk, i = Math.floor(this.t * a.fps / this.fps);
    if (i === this.walkFrame) return;
    this.walkFrame = i;
    const stride = a.advance[i % a.advance.length] * this.scale, d = this.target - this.x;
    if (Math.abs(d) < stride) this.until = this.t; // arrived, pick something new
    else { this.dir = Math.sign(d) || this.dir; this.x += this.dir * stride; }
  }

  // Draw him with his soles on y = floorY, x measured from ox, wearing `head`.
  // Returns where the head landed: its neck point, top, bottom and half
  // width, in canvas px, for placing speech or effects around it.
  draw(ctx, ox, floorY, head, now = Date.now()) {
    const { char } = this, s = this.scale;
    const action = char.actions[ACTION[this.state]];
    const i = Math.floor(this.t * action.fps / this.fps);
    const fid = action.frames[action.loop ? i % action.frames.length : Math.min(i, action.frames.length - 1)];
    const f = char.frames[fid];
    const flip = f.facing && f.facing !== this.dir ? -1 : 1;
    const gx = ox + this.x, gy = floorY;
    const [bx, by, bw, bh] = f.box;
    ctx.save();
    ctx.translate(gx, gy);
    ctx.scale(flip * s, s);
    ctx.drawImage(char.bodyAtlas, bx, by, bw, bh, -f.ground[0], -f.ground[1], bw, bh);
    ctx.restore();

    // Head over the neck: draping heads (the cloud) sit lower where the sheet's
    // anvil rested on the shoulders; all of them bob a little.
    const hd = char.heads[head];
    const drop = hd.drape ? f.drop : 0;
    const nx = gx + (f.neck[0] - f.ground[0]) * s * flip;
    const ny = gy + (f.neck[1] + drop - f.ground[1]) * s + Math.sin(now / 600) * this.bodyH * 0.012;
    const [hx, hy, hw, hh] = hd.box;
    ctx.save();
    ctx.translate(nx, ny);
    ctx.scale(s, s);
    if (head === "sun") {  // slow spin about the disc's centre
      const cy = hh / 2 - hd.anchor[1];
      ctx.translate(0, cy); ctx.rotate(now / 4000); ctx.translate(0, -cy);
    } else if (this.state === "sleep") ctx.rotate(0.3);
    ctx.drawImage(char.headAtlas, hx, hy, hw, hh, -hd.anchor[0], -hd.anchor[1], hw, hh);
    ctx.restore();

    return { x: nx, y: ny, top: ny - hd.anchor[1] * s, bottom: ny + (hh - hd.anchor[1]) * s, halfWidth: hw * s / 2 };
  }
}

// Data rain falling from a cloud head (draw()'s return) to the floor, in a
// character grid: cells cw × lh px from (ox, oy), the floor at row floorRow.
// Drawn on the canvas so it falls in front of his body.
export function rain(ctx, head, { cw, lh, ox, oy, floorRow, font, storm = false, now = Date.now() }) {
  const r0 = Math.ceil((head.bottom - oy) / lh), seed = Math.floor(now / 140);
  const col = (head.x - ox) / cw, half = head.halfWidth / cw;
  ctx.save();
  ctx.font = font;
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillStyle = storm ? "#b4c0d4" : "#4fc46a";
  ctx.shadowColor = "rgba(140, 220, 120, 0.35)"; ctx.shadowBlur = 6;
  for (let c = Math.ceil(col - half * 0.6); c <= col + half * 0.6; c++) {
    for (let r = r0; r < floorRow; r++) {
      const n = (c * 7919 + r * 104729 + seed * 31) % 97;
      if (n < (storm ? 22 : 15)) ctx.fillText("╎:'10"[n % 5], ox + (c + 0.5) * cw, oy + (r + 0.5) * lh);
    }
  }
  ctx.restore();
}
