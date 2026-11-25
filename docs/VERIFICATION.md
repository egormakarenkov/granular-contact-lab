# Verification record for the curated draft

Prepared 2026-11-24. Experimental numerical prototype; not physically calibrated.

- 26 automated tests passed in the existing isolated Python environment (11.58 seconds). Coverage includes analytic force balance, inertial drift, packing, exact gap checks, rigid sway, comparisons, forks, exports, maps, bounded search, refinement, extra seeds, and the fresh fixtures.
- TypeScript checking and the Vite production build passed.
- Eight full recordings were generated afresh using synthetic seeds 2027, 2028 and 2029; the first pair includes half-timestep repeats. Analytic support and artificial redundant-constraint examples were also generated.
- The local UI loaded the fresh default, computed a comparison, and displayed force bounds and matrix diagnostics in the in-app browser. An inherited stale-diagnostic display was corrected; advancing the timeline was observed to clear both results.
- A new PyInstaller Windows build completed. Its bundled numerical self-test passed with only Windows directories on PATH, exercising NumPy/SciPy/OSQP, support forces, LP bounds, finite inertia and assets.
- The self-contained demo loaded in the in-app browser.

These are bounded software checks on the available Windows 11 host. Recipient-PC operation, Windows 10, Edge fallback and physical-material behavior have not been separately validated for this curated draft. See MODEL.md for the scientific limits. The desktop workbench is intended for a wide desktop window.
