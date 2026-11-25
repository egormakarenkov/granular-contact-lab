# Contributing

Focus contributions on reproducible numerical behavior, clear interpretation, and useful local workflows.

For problems, include a small synthetic reproduction, expected and actual behavior, settings, timestep, seed, dependency versions, and relevant diagnostics. Remove private paths from logs. Do not post private data or unpublished research. Distinguish force nonuniqueness and floating-point variation from implementation bugs.

For patches, explain the problem and resulting behavior. Run affected checks: `python -m pytest -q` for solver/service changes, and `npm run build` from `ui/` for UI changes. Add meaningful regression coverage where useful. Keep model assumptions and documentation aligned.

Do not commit environments, dependency folders, new experiment history, logs, build intermediates or packaged EXEs. Generated examples must use documented synthetic recipes. Add no research-specific material or attribution without the relevant permission.

Contributions are proposed under the repository's MIT license. Dependencies retain their own terms. Submission does not establish scientific validation or guarantee acceptance.
