# Analysis: @haelp/teto (Triangle.js)

**What it is:** A TypeScript library — npm `@haelp/teto`, repo [Genius6942/triangle](https://github.com/Genius6942/triangle), docs at <https://triangle.haelp.dev> — that is a **programmatically controllable TETR.IO client**. Latest examined version **4.2.7**. Powers community projects like MochBot and ZZZTOJ.

> Not officially supported/endorsed by TETR.IO. Main-game API requires an **official bot account**; malformed messages risk bans (hence "TypeScript highly recommended"). Pinned to TETR.IO Beta v1.7.8 / Node 22.x LTS. The Tetra Channel API and the **engine** are open to anyone.

## Two halves

```
@haelp/teto            ← the networked CLIENT (Ribbon protocol)
@haelp/teto/engine     ← the standalone GAME ENGINE (deterministic sim)
```

### 1. The Client — TETR.IO protocol layer
Speaks TETR.IO's **"Ribbon"** WebSocket protocol using `ws` + **`msgpackr`** (MessagePack) for serialization.

```ts
const client = await Client.create({
  username, password,        // or { token }
});

await client.rooms.create("private");
client.rooms.list();
client.rooms.join(roomId);
room.chat("gg", pinned);
room.start();
```

**Async/event bridge** over TETR.IO's raw event model:
- `client.emit(event, data)` — send to server
- `client.wait(event)` — await a single event
- `client.wrap(send, data, recv)` — request/response
- `client.on/off/once`, `client.hook()` — listeners (hook has `.destroy()` cleanup)
- Synthetic aggregate events, e.g. `client.room.players`

**Gameplay loop** is frame/tick based:
```ts
const [tick, engine] = await client.wait("client.game.round.start");
tick(async (data) => {
  // data.frame = current frame
  // return key inputs to issue on the next frame
});
```
Inputs are **frame-stamped key commands** (keydown/keyup with subframe timing) — i.e. you drive the game by emitting the same input events a human keyboard would, in sync with the server's frame clock.

### 2. The Engine (`@haelp/teto/engine`)
A standalone, **deterministic** TypeScript reimplementation of TETR.IO's game logic. This is the part most relevant to an SDK because it is:
- **Open** (usable without a bot account / network),
- **Frame-accurate** to the real client (same RNG/bag, SRS+kicks, garbage/attack model, B2B/combo/spin scoring, DAS/ARR/SDF handling),
- **Replay-capable** — feed a frame-stamped input stream and it reproduces the exact game state, enabling replay verification and headless simulation.

## How the three pieces relate

```
        live multiplayer            deterministic sim        static analysis
        ────────────────            ─────────────────        ───────────────
        @haelp/teto Client   ──►    @haelp/teto/engine        sfinder.jar
        (Ribbon / websocket)        (frame replay)            (PC search)
                                          ▲
                                          │ same SRS / bag / rules
                                          ▼
                                     Techmino (Lua, full game, open source)
```

## Relevance to this SDK

- **The engine is the closest analog to what this SDK is becoming**: a portable, deterministic stacker game model. It's a strong reference (or even an interop/validation target) for the SDK's `Board`, `Piece`, `RotationSystem`, and any future live-play simulation.
- **Replay/frame-input model** (frame-stamped keys → deterministic state) is a clean design to mirror if the SDK adds gameplay simulation, and enables cross-checking SDK output against a known-good engine.
- **Protocol layer is TETR.IO-specific** (Ribbon/msgpack, bot-account gated) — useful only if the SDK ever needs to connect to live TETR.IO; otherwise the `engine` submodule is the part to study.
- **Language gap:** TypeScript/Node vs this SDK's Python. No direct import; value is as a *behavioral reference* and potential subprocess/JSON-bridge oracle, similar to how sfinder is used.

**Limitations:** Tied to a specific TETR.IO beta version (mechanics drift between versions); unofficial and ban-risky for live use; TypeScript-only; engine fidelity is to TETR.IO specifically, which differs in details from guideline/Techmino/sfinder rulesets.
