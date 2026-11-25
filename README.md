# Granular Lab

**Experimental numerical prototype · v0.1.0**

An interactive workbench for synthetic 2D frictionless granular contact, with reproducible experiments and a portable Windows launcher.

Granular Lab computes damped grain motion around a prescribed rigid intruder. Inspect normal reactions, compare controls from identical initial states, branch from a paused frame, and export reproducible experiments. Computation runs locally, without an AI account or external AI service.

## Try it

- **[Download the replay demo](https://github.com/egormakarenkov/granular-contact-lab/releases/download/v0.1.0/GranularLab-v0.1.0-Demo.html):** one self-contained HTML file. Open locally and play or scrub a synthetic recording. It displays stored results; it does not compute new trajectories.
- **[Download the Windows app](https://github.com/egormakarenkov/granular-contact-lab/releases/download/v0.1.0/GranularLab-v0.1.0-Windows-x64.zip):** complete solver and workbench with the numerical runtime included.
- **[Download the source](https://github.com/egormakarenkov/granular-contact-lab/releases/download/v0.1.0/GranularLab-v0.1.0-Source.zip):** solver, UI, tests, generated examples, documentation and launcher/build source.

See the [three-minute showcase](SHOWCASE.md) or [all releases](https://github.com/egormakarenkov/granular-contact-lab/releases). Download the demo before opening it: viewing an HTML file in GitHub's code browser does not run the replay.

## What you can explore

| Feature | Purpose |
| --- | --- |
| Contact inspector | Examine gaps, normal reactions, relative velocities, impulses and residuals. |
| Synchronized comparisons | Compare two controls from identical initial arrays with reaction/work plots. |
| Paused-frame branches | Start new comparisons from recorded positions, velocities and intruder geometry. |
| Parameter maps | Compute a 3 × 3 amplitude/frequency grid from the same bed. |
| Bounded motion search | Select the best tested rigid motion, then inspect half-timestep and two additional-seed checks. |
| Force ambiguity and algebra | Inspect feasible force ranges, contact-matrix rank and singular values. |
| Reproducible exports | Save figures, CSV, standalone recordings, or bundles with initial arrays, settings, numerical source and a reproduction script. |

## Run the Windows app

1. Download and extract the **entire** Windows ZIP.
2. Double-click **Granular Lab.exe**.
3. Use the workbench in its app window, without browser tabs or an address bar.
4. Click **Quit** in the small solver controller before removing a USB drive.

Keep the executable and accompanying folders together, including `_internal`, `examples` and `ui`. Python and Node installations are unnecessary. Requires Windows x64 with Chrome or Edge installed. Windows 11 and the Chrome route are the checked platform; Windows 10 x64 is an intended compatibility target, and the Edge fallback is not separately verified.

The service binds loopback only. New experiments are saved in `experiments/` beside the app, so its folder must be writable. The installed browser uses a separate local profile/cache. After download, bundled operation requires no account or internet access.

## Run from source

Python 3.13 x64 is the tested source runtime. The built UI is included, so Node is needed only to rebuild it. On Windows, double-click `Launch Granular Lab.cmd`; first setup creates `.venv` and downloads pinned dependencies. Or use PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
.\.venv\Scripts\python.exe portable_launcher.py
```

For a headless service:

```powershell
.\.venv\Scripts\python.exe portable_launcher.py --serve-only --port 8765
```

Visit `http://127.0.0.1:8765`. Non-Windows desktop operation is unverified.

## Follow a first experiment

1. Play the supplied 36-disc synthetic run and select a grain/contact.
2. Leave **Lateral sway** as the main motion, choose **Translation only** as the alternative, and click **Compare two controls**.
3. Inspect reaction/work plots. Both branches share initial grain arrays, duration and net downward stroke.
4. Open **Check force ambiguity** or **Constraint matrix & rank** for the selected recorded state.
5. Export an **Experiment bundle**, or use **Fork frame** to compare new continuations.

All eight supplied recordings are generated examples. Translation and sway are compared on seeds 2027, 2028 and 2029; the first pair is repeated at half timestep. Sway uses more positive actuator work in these supplied cases. The examples explain the comparison method rather than a guaranteed improvement. The [example guide](docs/EXAMPLES.md) also describes analytic floor support and artificial redundant constraints.

## Model and scientific limits

The core is a dimensionless, two-dimensional frictionless normal-contact model. Each step solves a velocity quadratic program with positive damping and optional scaled inertia. Positions are checked against geometric gaps; excessive endpoint penetration or displacement triggers subdivision. A prescribed circular or elliptical rigid intruder holds, translates, or adds a windowed lateral sine motion.

- No Coulomb friction, grain rotation, pore fluid, physical calibration, arbitrary restitution model or freely responding intruder is included.
- Contact-force distributions may be nonunique. Displayed reactions are one numerical solution; force-range bounds use stated tolerances.
- Matrix rank, connectivity and loss of contact are diagnostics, not proofs of bulk fluidization.
- Equal endpoints do not imply equal path length, speed, acceleration or hardware cost.
- Search selects the best tested candidate in a finite family, not a global optimum.
- Software checks do not establish physical validation or a general convergence/vanishing-inertia theorem.

See [equations and interpretation](docs/MODEL.md) for the model, work definition and acceptance checks.

## Verification

Recorded checks include **26 passing automated tests**, a successful TypeScript/Vite build, local browser checks of comparisons and contact diagnostics, and a passing numerical self-test in the bundled Windows EXE with Python absent from PATH. Checks used the available Windows 11 host, not every target PC.

See the [verification record](docs/VERIFICATION.md) for dates, scope, warnings and unverified platforms. No CI result or experimental validation is claimed.

## Development and reproduction

After installing the pinned requirements, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/generate_examples.py
```

To rebuild the interface, with Node/npm installed:

```sh
cd ui
npm ci
npm run build
```

The generator creates synthetic initial packings, eight recordings, analytic examples and the offline demo. Full fixtures preserve exact initial arrays and full floating-point values; the compact demo rounds values to nine decimal places. Dependency/platform changes can affect numerical results.

Exported reproduction bundles include instructions and `reproduce.py`, starting from recorded arrays instead of an image.

To assemble a Windows distribution after building the UI:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
.\.venv\Scripts\python.exe scripts/build_windows.py
```

The app appears in `dist/GranularLab`. See [Windows packaging](docs/WINDOWS.md).

## Repository map

| Path | Contents |
| --- | --- |
| `granular/` | Solver and loopback HTTP service |
| `ui/src/`, `ui/dist/` | TypeScript source and built offline interface |
| `portable_launcher.py` | Native controller, service startup, app-window launcher and self-test |
| `tests/` | Numerical and service tests |
| `examples/` | Synthetic fixtures, settings, metrics and initial arrays |
| `demo/` | Standalone replay and generation template |
| `scripts/` | Example generation and Windows packaging |
| `docs/` | Model, examples, provenance, verification and notices |

Local environments, runtime logs, new experiment history, build intermediates and packaged binaries are excluded from Git. Windows downloads belong in Releases.

## Provenance and AI assistance

The solver, interface and packaging were developed with AI coding assistance; the runtime does not call an AI service. Examples are synthetic. No physical measurements, imported research conversations, supplied reference code, private experiment history, unpublished research text or personal endorsement are included. See [provenance](docs/PROVENANCE.md).

## Feedback and contributions

Use [Issues](https://github.com/egormakarenkov/granular-contact-lab/issues) for reproducible software problems, numerical interpretation questions and feature suggestions. Include settings, timestep, seed, versions, expected behavior and observed diagnostics. Share only material you have permission to publish. See [contribution guidance](CONTRIBUTING.md). This prototype has no guaranteed support schedule.

## License

Project code and original documentation use the [MIT License](LICENSE). Dependencies and fonts retain their own licenses; preserve [third-party notices](docs/THIRD_PARTY_NOTICES.md).
