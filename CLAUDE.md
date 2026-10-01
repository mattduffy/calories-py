# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`calories-py` — a **dependency-free** (Python stdlib only) package that estimates calories burned during walking/hiking/rucking. It offers a simple MET-based estimate plus three GPS-based predictive models (Pandolf-Santee, LCDA, Minimum Mechanics) and an ensemble that runs all three over one dataset.

Requires Python >= 3.9. All published dependencies are empty on purpose — do not add third-party runtime dependencies.

## Repo layout gotcha

**The repo root is itself a Python virtualenv.** `bin/`, `include/`, `lib/`, `share/`, and `pyvenv.cfg` are venv artifacts, not project source — ignore them. Activate with `source bin/activate`. `dist/` holds built wheels/sdists. The actual package lives entirely under `src/calories/`.

`.ipynb_checkpoints/` and `__pycache__/` dirs are scattered throughout — ignore them.

## Commands

```bash
source bin/activate                 # activate the in-repo venv
python -m calories                  # (no CLI; import the package instead)

# Build (uses hatchling + hatch-vcs)
hatch build                         # produces dist/*.whl and dist/*.tar.gz
```

There is **no pytest suite and no linter configured.** Tests are Jupyter notebooks:
- `src/tests/test-calories.ipynb` — exercises the public functions
- `src/tests/point-decimator.ipynb` — WIP for cross-track-distance / Ramer-Douglas-Peucker point reduction
- `calories.ipynb` (repo root, ~1.3MB) — the primary development scratchpad
- `setup.ipynb` — one-off env/tooling setup (installing hatch, twine, pypistats)

To "run tests," execute the notebook cells. Notebooks add the parent dir to `sys.path` and import from `calories`.

## Debug output

All `print()` in `src/calories/calories.py` is wrapped by `print_decorator`, which suppresses output unless the env var `CALORIES_DEBUG=true` is set. Set it (e.g. `os.environ["CALORIES_DEBUG"] = 'true'` in a notebook) to see internal prints; otherwise the code is silent.

## Versioning

Version is derived from git tags via `hatch-vcs` and written to `src/calories/_version.py` at build time. **`_version.py` is git-ignored — never commit it or hand-edit the version.** `no-guess-dev` is set in `pyproject.toml` to keep the version string clean. `__init__.py` falls back to `"0.0.0.dev0"` in an unbuilt tree.

## Architecture

Essentially all logic is in one module: `src/calories/calories.py` (~1000 lines). `__init__.py` re-exports the public API: `simpleCalories`, `pandolfCalories`, `lcdaCalories`, `minimumMechanicsCalories`, `calorieEnsemble`, `load_sample_data`, `models`, `__version__`.

**GPS coordinate format** (the array each model consumes):
`[longitude, latitude, heading, altitude_m, accuracy_m, timestamp_ms]`
Only longitude, latitude, altitude (meters), and timestamp (ms) are used; heading and accuracy may be `None`.

**The segment pipeline.** Each GPS model walks consecutive pairwise points ("segments"), computes energy for each segment, then aggregates. The shape is consistent across all three models:
- A per-segment processor: `processPandolfSegment`, `processLcdaSegment`, `processMinimumMechanicsSegment` — each returns a segment dict or `None` (segment is dropped if duration <= 0 or horizontal distance < `MIN_SEGMENT_DIST_M`).
- A public wrapper: `pandolfCalories` / `lcdaCalories` / `minimumMechanicsCalories` that validates args, optionally smooths altitude, maps the processor over segments, and reduces to `{totalKcal, totalDistanceM, totalDurationSec, avgSpeedMs}`.
- `calorieEnsemble` runs all three processors in a single pass over the segments and returns `{lcda, pandolf, minMech}`.

**Shared helpers** (top of the module): `pointDistance` (haversine), `calculateSlopeGrade`, `calculateVerticalInterval`, `smoothAltitude` (rolling average for jittery GPS elevation), unit converters `m2s`/`m2m`/`rads`.

**Key constants** (top of module) — change model behavior here, not inline:
`TERRAIN_COEFFICIENTS`, `SMOOTH_DEFAULT`/`SMOOTH_DEFAULT_WINDOW` (=5), `MAX_SPEED_MS` (=4.0, speeds clamped), `MIN_SEGMENT_DIST_M` (=0.5), `JOULES_PER_KCAL` (=4184), `MM_COEFFICIENTS` (Ludlow & Weyland 2017), `DEFAULT_RESTING_VO2` (=3.05), `KCAL_PER_ML_O2` (=0.005).

**Options contract.** GPS models take an `options` dict: required `bodyWeightKg`; optional `loadKg`, `waterKg`, `terrain` (Pandolf/LCDA only), `smooth`, `smoothWindow`, `returnSegments`. LCDA and Minimum Mechanics additionally require a `BMR` dict (`height` cm, `weight` kg, `age` yr, `sex` 'm'/'f') to compute resting metabolic rate via Mifflin-St Jeor (`mResting`). For `calorieEnsemble`, `BMR` is nested inside `options`. All public functions raise `ValueError` on missing/wrong-type required args.

**Sample data.** `load_sample_data()` reads the bundled `src/calories/sample_data.json` (GeoJSON LineString) via `importlib.resources`. `sample_data.json` is included in wheel/sdist builds (see `[tool.hatch.build.targets.sdist]`). Extra hike datasets live in `src/data/` (not bundled).

`models()` returns a catalog of the available functions (name, shortName, function, desc, authors) plus the ensemble collection — keep it in sync when adding/renaming a model.

## Docs

User-facing documentation is `Readme.md` (note the casing — `pyproject.toml` sets `readme = "Readme.md"`). Every public function is documented with docstrings; the README directs users to `help(<function>)`. When changing a model's signature, return shape, or `models()` output, update `Readme.md` to match.
