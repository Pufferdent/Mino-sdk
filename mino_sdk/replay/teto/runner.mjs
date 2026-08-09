// TETR.IO replay reconstruction via the real @haelp/teto engine.
//
// Reads a JSON job on stdin:
//   { gamemode, options, events: [{ frame, type, data:{ key, subframe } }] }
// where `options` is the replay's `replay.options` block and `events` is the
// raw keydown/keyup stream. Reconstructs the game with the authentic TETR.IO
// engine and prints a JSON result on stdout:
//   { pieces, lines, clears:{1,2,3,4}, spins:{...}, perfectClears, board, events }
//
// This is the `engine="teto"` fallback path: the native Python engine is
// frame-accurate for most play but cannot match TETR.IO's exact sub-frame loop
// on demanding replays (PC loops, dense soft-drop tucks). teto IS that engine,
// so it reproduces a replay's final statistics exactly.
//
// Two TETR.IO behaviors live in the client (not the standalone engine) and are
// reapplied here:
//   * no-SZO start: leading S/Z/O of the first bag move to the back, including
//     the piece already spawned into `falling`.
//   * Blitz gravity: a per-level ramp (level<-lines) driving cell gravity,
//     which the engine's time-based g/gincrease/gmargin model does not express.

import { Classes } from "@haelp/teto";
const { Game } = Classes;

const SZO = new Set(["s", "z", "o"]);

// Defaults for ReadyOptions fields a solo .ttr omits (the mode supplies them at
// runtime). The replay's own options are layered on top.
const DEFAULTS = {
  version: 19, seed: 0, seed_random: false, are: 0, lineclear_are: 0,
  g: 0.02, gincrease: 0, gmargin: 0, gravitymay20g: false,
  hasgarbage: false, usebombs: false, garbagespeed: 20, garbagemultiplier: 0,
  garbagemargin: 0, garbageincrease: 0, garbageholesize: 1, garbagephase: 0,
  garbagequeue: false, garbageentry: "instant", garbageare: 0, garbagecap: 8,
  garbagecapincrease: 0, garbagecapmargin: 0, garbagecapmax: 40,
  garbageabsolutecap: 0, garbagetargetbonus: "none",
  garbageblocking: "combo blocking", garbagespecialbonus: false,
  passthrough: "zero", openerphase: 0, roundmode: "down",
  spinbonuses: "all-mini+", combotable: "multiplier", kickset: "SRS+",
  bagtype: "7-bag", messiness_change: 0, messiness_inner: 0,
  messiness_nosame: false, messiness_timeout: 0, messiness_center: false,
  boardwidth: 10, boardheight: 20, clutch: false, stock: 0,
  allclears: false, allclear_garbage: 0, allclear_b2b: 0,
  b2bchaining: true, b2bcharging: false, b2bcharge_at: 0, b2bcharge_base: 0,
  infinite_movement: false, lockresets: 15, locktime: 30,
  allow180: true, can_undo: false, can_retry: false,
  display_hold: true, allow_harddrop: true,
  infinite_hold: false, stride: false, nolockout: false,
};

function applyNoSzo(eng) {
  const bag = [eng.falling.symbol, ...eng.queue.slice(0, 6)];
  let n = 0;
  while (n < 7 && SZO.has(bag[n])) n++;
  if (n === 0) return;
  const re = bag.slice(n).concat(bag.slice(0, n));
  for (let i = 0; i < 6; i++) eng.queue[i] = re[i + 1];
  eng.initiatePiece(re[0]);
}

// Blitz: level advances with cleared lines (lines to reach level L is L^2-1,
// with the documented L11->L12 +3 step), gravity follows the guideline
// marathon curve from levelgbase/levelspeed.
function blitzLevel(lines) {
  let lvl = 1, cum = 0;
  for (;;) {
    const step = lvl === 11 ? 24 : 2 * lvl + 1;
    if (cum + step > lines) return lvl;
    cum += step; lvl++;
  }
}
function blitzGravity(L, gbase, speed) {
  const spr = Math.pow(gbase - (speed / 60) * (L - 1), L - 1);
  return spr <= 0 ? 20 : Math.min(20, 1 / (60 * spr));
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let buf = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (d) => (buf += d));
    process.stdin.on("end", () => resolve(buf));
    process.stdin.on("error", reject);
  });
}

function boardMatrix(eng) {
  // Bottom-row-first grid of mino letters ("" for empty), trimmed to filled.
  const state = eng.board.state;
  let top = -1;
  for (let y = state.length - 1; y >= 0; y--) {
    if (state[y].some((c) => c)) { top = y; break; }
  }
  const rows = [];
  for (let y = 0; y <= top; y++) {
    rows.push(state[y].map((c) => (c ? (c.length ? c[0] : "#") : "")));
  }
  return rows;
}

async function main() {
  const job = JSON.parse(await readStdin());
  const opt = Object.assign({}, DEFAULTS, job.options || {});
  const isBlitz = job.gamemode === "blitz" || opt.levels === true;
  const gbase = opt.levelgbase ?? 0.65;
  const speed = opt.levelspeed ?? 0.42;

  const eng = Game.createEngine(opt, opt.gameid || 0, []);
  if (opt.no_szo) applyNoSzo(eng);

  const locks = [];
  eng.events.on("falling.lock", (res) => {
    const empty = !eng.board.state.some((row) => row.some((c) => c));
    locks.push({
      mino: res.mino, lines: res.lines, spin: res.spin,
      b2b: res.stats.b2b, combo: res.stats.combo, pc: res.lines > 0 && empty,
    });
  });

  const byFrame = new Map();
  let last = 0;
  for (const e of job.events) {
    if (e.type === "start" || e.type === "end") continue;
    if (!byFrame.has(e.frame)) byFrame.set(e.frame, []);
    byFrame.get(e.frame).push(e);
    if (e.frame > last) last = e.frame;
  }

  for (let f = 0; f <= last && !eng.toppedOut; f++) {
    if (isBlitz) {
      eng.dynamic.gravity.set(blitzGravity(blitzLevel(eng.stats.lines), gbase, speed));
    }
    eng.tick(byFrame.get(f) || []);
  }

  const clears = { 1: 0, 2: 0, 3: 0, 4: 0 };
  const spins = { mini: 0, normal: 0 };
  let perfectClears = 0;
  for (const l of locks) {
    if (l.lines >= 1 && l.lines <= 4) clears[l.lines]++;
    if (l.spin && l.spin !== "none") spins[l.spin]++;
    if (l.pc) perfectClears++;
  }

  process.stdout.write(JSON.stringify({
    pieces: eng.stats.pieces,
    lines: eng.stats.lines,
    clears, spins, perfectClears,
    toppedOut: eng.toppedOut,
    board: boardMatrix(eng),
    locks,
  }));
}

main().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
