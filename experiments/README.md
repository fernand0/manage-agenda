# Experiments

One-off results from past model-comparison sessions, kept for reference.
Nothing in the application reads or writes this directory.

| File | What it is |
|---|---|
| `resultados_experimentos.csv` | Timing and extracted dates from the 2026-07/08 comparison (7 posts x 11 Ollama models) |
| `comparativa_modelos.csv`, `kk.csv`, `kk.txt`, `res.csv` | Intermediate snapshots of the same comparison |
| `validate.py` | Stale scratch copy of `manage_agenda.events._validate_event_dates_non_interactive`; superseded by `tests/test_events.py` |
| `tests.results` | A saved tinyllama reply that seeded the fixtures in `tests/fixtures/llm_responses/` |

Future experiment outputs belong in a git-ignored `scratch/` directory (see
`.gitignore`), not in the repository root.
