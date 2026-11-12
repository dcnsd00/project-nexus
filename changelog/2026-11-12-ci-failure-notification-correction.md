# CI correction after GitHub failure notifications — 2026-11-12

The previous CI workflow intentionally exited with an error when application source was absent. Because the workflow also ran on documentation pushes to main, those pushes produced failed GitHub Actions notifications even though no application test had been run. This was a workflow design mistake: it made repository setup work look like a source-code test failure.

Correction:
- Added a source-detection job.
- When application source is absent, the Python test job is skipped with an explicit notice; documentation-only commits no longer fail the application test job.
- Once source is imported under application/ or repository root, compileall and pytest run normally and fail on real errors.

Commit: 418fa1fd03d2fbf522b252dbb5d06f5dc680989a.

This workflow correction does not import application source and does not retroactively prove that previous failed runs were all caused by the missing source. Exact per-run causes require inspecting the individual GitHub Actions logs.
