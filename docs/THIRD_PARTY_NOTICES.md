# Third-party components

Numerical computation uses NumPy, SciPy and OSQP; the local service uses FastAPI and Uvicorn. Test tools include pytest and httpx. The interface uses TypeScript and Vite. Exact tested Python versions are in `requirements-tested.txt`; UI dependency versions are recorded in `ui/package-lock.json`.

Instrument Sans and Lora are bundled through Fontsource. Their SIL Open Font License texts are in `docs/licenses/`.

The optional portable build uses PyInstaller and embeds the Python runtime, Tcl/Tk and numerical dependencies. The Windows build script collects installed distribution license files into `docs/dependency-licenses/` and copies the Python license. These notices do not relicense dependencies or provide a project license. Chrome/Edge are installed separately and are not bundled.

Project code is covered by the root MIT LICENSE. Dependency licenses and notices must be preserved in distributions.
