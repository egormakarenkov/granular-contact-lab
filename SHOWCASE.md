# Granular Lab — a three-minute showcase

**An experimental workbench for synthetic 2D frictionless contact.**

## 1. Start with the picture — 30 seconds
Open demo/index.html. Play the recording or scrub the timeline. The grains and contact reactions come from a numerical solve; this small page is an offline replay.

Say: “This began as a simulation idea. The finished tool includes a solver, an interactive workbench, reproducible experiments, and a portable Windows app.”

## 2. Show the full tool — 90 seconds
Extract the Windows package and double-click Granular Lab.exe. Its UI opens in an app window.

- Play or step the supplied synthetic run.
- Select a contact and show its computed normal reaction, gap and numerical diagnostics.
- Choose Translation only as the alternative and click Compare two controls. Both branches start from the same saved grain arrays.
- Show Fork frame, the parameter map and motion search as ways to investigate a question. There is no need to run every feature live.
- Show Experiment bundle: settings, exact initial conditions, numerical source and a reproduction script travel with the result.

## 3. Explain the significance — 30 seconds
Say: “The useful step beyond generating code is turning it into a working, inspectable tool: computing results, testing basic cases, comparing experiments fairly, and making the result easy for another person to run.”

## 4. State the science clearly — 30 seconds
Say: “These are synthetic, dimensionless examples of frictionless normal contact. The tool has numerical checks, but is not calibrated to real soil. Force distributions can be nonunique, and a lower-work trial or a changed contact network is not a general proof about granular materials.”

The fresh examples compare straight translation with a rigid lateral sway. Sway uses more positive work in these three supplied packings; this is a useful controlled comparison, not a promised improvement.

**Status:** Experimental numerical prototype. Project code: MIT license. Private research conversations, supplied reference code and existing research-related experiment history are excluded.

