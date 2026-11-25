# Windows packaging

The tested target is 64-bit Windows 11 using Python 3.13.1. Windows 10 x64 is the intended compatibility target, not a separately tested host. Chrome app mode has been exercised; Edge is a fallback path without a separate UI acceptance test. No macOS, Linux desktop or Windows ARM binary is supplied.

Install `requirements-tested.txt` and `pyinstaller==6.22.3` in a build environment, build `ui/dist` if needed, then run `python scripts/build_windows.py`. The script assembles `dist/GranularLab`, including the executable, bundled runtime, built UI, fresh fixtures and documentation. Copy the whole folder or ZIP it as one unit. Do not distribute the EXE alone.

The EXE starts a loopback HTTP service and a native Tk controller. The UI opens with Chrome's `--app` mode, using a separate profile under `%LOCALAPPDATA%/GranularLab/AppWindow`; it does not join a personal browser session. A suitable free local port is selected. The controller's Quit button cancels work and waits for workers before closing. The browser app window can remain open after the service stops.

The app folder must be writable. New runs and runtime logs are stored there, making USB use possible. The installed browser writes its own profile/cache to the host PC. No Python, Node, account or internet connection is needed to run the bundled version.

For a numerical runtime check:

```text
"Granular Lab.exe" --self-test "C:\temporary\report.json"
```

Use an existing writable report directory. The check exercises bundled NumPy/SciPy/OSQP, analytic support, force-range LPs, finite-inertia stepping and local assets. It does not constitute a test on every supported Windows PC.
