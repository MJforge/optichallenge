# OGC 2026 Optimization Challenge

Participant toolkit for the OGC 2026 optimization challenge (2D block-packing +
scheduling with an overhead crane). Everything runs locally in Python; there are
no network services, databases, or web servers.

Components:
- `alg_tester/` — PyQt6 desktop GUI to load a problem instance, run an algorithm
  (as a subprocess) and visualize/validate the result (Problem tab, Solution tab,
  bay layout, Gantt chart). Entry point: `alg_tester/alg_tester_app.py`.
- `baseline/` — algorithm template (`myalgorithm.py`), a reference greedy
  implementation (`baseline_greedy.py`), the shared feasibility checker
  (`utils.py`, do not modify), and a headless CLI runner (`run_local_test.py`).
- `prob_*.json` / `alg_tester/example/*.json` — problem instance data.
- `ogc2026_env.yml` — the conda environment definition (env name `ogc2026`).

See `README.txt`, `baseline/README.txt`, and `alg_tester/README.txt` for the
official usage instructions.

## Cursor Cloud specific instructions

Environment: a Miniforge conda install lives at `~/miniforge3` and the project
env `ogc2026` (Python 3.12) is already created. `conda init bash` has been run,
so a new interactive `bash` shell can `conda activate ogc2026` directly. The
startup update script keeps the env in sync with `ogc2026_env.yml` (it runs
`conda env update -n ogc2026 -f ogc2026_env.yml`, which is a no-op / fast when
nothing changed).

Always activate the env before running anything:
`conda activate ogc2026`.

Running the code (non-obvious caveats):
- Scripts import sibling modules by folder (`myalgorithm`, `utils`), so run them
  from inside the folder. Headless end-to-end smoke test / "run the app":
  `cd baseline && python run_local_test.py ../prob_1.json 15`
  (prints `Feasible : True` and objective values). Reference solver:
  `cd baseline && python baseline_greedy.py ../prob_1.json --timelimit 15`.
- GUI (`alg_tester/alg_tester_app.py`) is a real desktop app and needs a
  display. This VM runs an xfce desktop on `DISPLAY=:1` (used by computer-use),
  so launch it with `export DISPLAY=:1` before `python alg_tester_app.py`. For a
  non-interactive smoke check without a screen, use `QT_QPA_PLATFORM=offscreen`.
  The tester runs the selected algorithm folder as a subprocess and shows the
  feasibility result / objective in the Solution tab.

Lint / test / build:
- There is no build step, no configured linter, and no automated test suite
  (no pytest/unittest, no CI). The de-facto correctness check is the feasibility
  checker in `utils.py` exercised via `run_local_test.py` or the GUI tester.

Optional heavy dependencies: the env pins `torch`, `tensorflow`, `keras`,
`gymnasium`, `ortools`, `gurobipy`, and `xpress` for participants who want them.
The baseline uses none of these. `gurobipy`/`xpress` import fine but need
licenses to actually solve.
