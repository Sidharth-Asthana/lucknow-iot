# Chrysalis — Project Brief

> Master context for Claude. Read this fully when opening the project.
> Renamed **2026-06-14** from "Cradle" / "Lucknow Smart Residence". "cradle" now
> only labels the local folder + workspace; the project is **Chrysalis**.

## What this is

A smart, self-sufficient single-family residence at **B-274 DLF Garden City,
Lucknow, UP**. West-facing plot ~43 × 90 ft, three levels (Ground / First / Roof).
Scope spans architecture (SketchUp model + interactive floor plans), a local-first
IoT / Home-Assistant stack, rooftop solar + storage, and passive cooling.

## How to work on this project

- **Voice:** Scientist + Architect + Engineer. Be rigorous, pressure-test ideas,
  and call out blind spots, weak assumptions, and the most important consideration
  of the moment directly — even when not asked, even when Sid sounds confident.
- **Cover all bases** — account for every relevant consideration before presenting.
- **Make it look good** — renders and dashboards are the first impression. Substance
  *and* style.
- **Track across all platforms** — local device, GitHub, the SketchUp model, and
  renderings must stay in sync (SketchUp page: https://app.sketchup.com/app).
- **Verify before shipping**, and **preserve tokens** (batch SketchUp edits into one
  session; don't re-read unchanged files).

## Orientation & terminology (LOCKED 2026-06-14)

- All floor-plan sketches: **top = East, bottom = West, left = North, right = South.**
  Plot is **west-facing** (main gate on the west).
- **"terrace"** = the **1st-floor east extension** (silk workshop + open terrace),
  projecting ~20 ft east over the GF back lawn on a column grid.
- **"roof"** = the **rooftop level** (garden, secret room, viewing room, lift/stair/storage).

## Current design state (summary)

Authoritative detail lives in the project memory (`cradle-design-decisions-2026-06`).
**NOTE:** `floor_plans.html` SVGs and the `.skp` model still show **pre-overhaul**
geometry — the 2026-06-14 redraw is *pending*.

- **Ground floor:** west front lawn + main gate; east back lawn + back gate; south
  canopy driveway with **garage (10×15) + servant's quarters (10×10) stacked above**
  at the SE end. Interior: stair/lift core NE, kitchen + island, dining, **sunken
  living "well"** (2 steps / 1–2 ft down), guest BR en-suite, powder room,
  utility/laundry — which now also houses the **LFP battery bank**.
- **First floor (terrace):** 30×40 block + east extension. **Workshop = covered NE
  corner 20×15 ft (300 sqft)**; the rest of the 20 × ~37–40 ft extension is open
  terrace. North wall **blank**, **3 ft service gap** to the boundary. Workshop:
  south **full low-e glass + glass door + awning shade + small AC**; east **two
  openable bay windows**; **north roof monitor** for diffuse studio light (roof level
  does NOT extend over the extension); cool/insulated filler-slab roof. Entry only
  from the open terrace. Plus 3 en-suite bedrooms (incl. master SW), den, linen.
- **Roof:** lift/stair/storage in a 15×15 room (10×10 core + storage overflow).
  **Secret room** = Sid's hidden space + the home "brain" (Mac minis + admin PC in a
  sealed cabinet) + a partitioned grow zone + hangout; windowless → needs
  **mechanical fresh-air ventilation (CO₂ safety) + mini-split + dehumidifier**;
  **full-spectrum LED grow lights, NOT UV**. **Viewing room** (AC). **Rooftop garden**
  (5–6 raised beds, ~4 in soil for grass/herbs; proper waterproof **membrane + root
  barrier** — bamboo decorative only).
- **Solar:** target **15 × 550 W ≈ 8.25 kWp + 15 kWh LFP**, justified by the 24/7
  home-brain baseload. Mount on the roof-room + secret/viewing roofs + workshop roof;
  east wall of the roof-room only as last-resort vertical overflow. Battery in the GF
  utility (cool), DC run up to the roof inverter.
- **Passive thermal (whole house):** thermally reflective paint + **filler-slab
  roofs/ceilings** (terracotta pots + straw air pockets; straw must be encapsulated
  against monsoon moisture/pests/fire).
- **Cooling tower:** scaled DOWN to cool the workshop only, and **DEFERRED**
  ("discuss later"). Whole-house concept dropped.

## Files

- `floor_plans.html` — interactive plan + systems sheets. **Source of truth for plans**
  (pending the overhaul redraw). Title/heading now "Chrysalis".
- `lucknow_smart_home_v6_5.skp` — SketchUp model. **Do NOT rename the file** — it is
  hard-wired into `sync_v65.bat`. In-model title rename to "Chrysalis" is pending the
  next geometry build.
- `iot/` — **NESTED git repo** (own remote), Home-Assistant / IoT stack. See `iot/CLAUDE.md`.
- `iot.md`, `render_and_deliverables.md`, `verification.md` — supporting docs.
- `sync_v65.bat` — one-click: download latest `.skp` + commit + push both repos.

## Repos & sync constraints

- Outer: `github.com/Sidharth-Asthana/lucknow-smart-home` — rename → `chrysalis` is
  **PENDING** (Sid's manual GitHub action; then `git remote set-url`).
- Nested: `iot/` → `github.com/Sidharth-Asthana/lucknow-iot`.
- **Git push must be done by Sid** — no credentials in the sandbox.
- **SketchUp MCP** = cloud session, expires ~15–30 min idle; the sandbox cannot
  download from api.sketchup.com — give Sid the URL or use `sync_v65.bat`.

## Pending

1. Rename GitHub repo + SketchUp in-model title.
2. Redraw `floor_plans.html` SVGs + rebuild the SketchUp model to the 2026-06-14 overhaul.
3. IoT: legacy `beehive` → cooling-tower entity/topic refactor; reflect the scaled-down,
   deferred workshop cooling.
4. Resolve open design questions: workshop east-glazing extent, rooftop farm
   water/drainage/load, secret-room services load (into the Lovelace/IoT plan).
