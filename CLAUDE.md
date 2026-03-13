# CLAUDE.md

## Project overview

Health monitoring tests for NCI Imaging Data Commons (IDC) services. Tests run as GitHub Actions on a daily cron schedule. This is a lightweight test suite, not a library — no package management beyond pip installs in CI.

## Development environment

Use `uv` for virtual environment and dependency management:

```bash
uv venv
source .venv/bin/activate
uv pip install requests google-cloud-bigquery google-auth
```

## Running tests

```bash
# All tests (needs GCP credentials)
python -m unittest -v tests/idc_tests.py tests/test_dicomweb.py

# DICOMweb proxy tests only (no credentials needed)
python -m unittest -v tests.test_dicomweb.TestDICOMwebProxy

# Using the JSON test runner (as CI does)
python scripts/run_tests_json.py --output results.json

# Run specific test class with label
python scripts/run_tests_json.py --output results.json --label whitelisted tests.test_dicomweb.TestDICOMwebGHC
```

## Project structure

- `tests/idc_tests.py` — BigQuery, IDC API (prod + dev), and portal health checks
- `tests/test_dicomweb.py` — DICOMweb QIDO-RS and WADO-RS health checks (proxy + Google Healthcare API)
- `scripts/run_tests_json.py` — test runner that outputs structured JSON (used by CI and dashboard). Supports `--label` for tagging results and positional args for filtering test classes.
- `.github/workflows/run_tests.yml` — CI workflow (daily cron, push, manual dispatch). Uses matrix strategy to run tests with two service accounts.
- `docs/index.html` — GitHub Pages dashboard (single-file HTML/CSS/JS). Tests are grouped into collapsible sections (IDC Services, DICOMweb Proxy, DICOMweb GHC).
- `docs/data/results.json` — historical test results (auto-updated by CI, last 90 entries)
- `docs/issue_*.txt` — Google Cloud support case transcripts for reference

## Git workflow

- Always ask for explicit permission before making any git commit or push. Never commit or push automatically.

## Conventions

- Test framework: `unittest` (stdlib). No pytest.
- HTTP requests: `requests` library. No DICOMweb-specific client libraries.
- Tests should print what they're doing (e.g., `print("Testing QIDO-RS studies search")`) for CI log readability.
- Keep tests lightweight — this is health monitoring, not comprehensive integration testing.
- GCP auth uses Application Default Credentials (`google.auth.default()`).
- When adding new tests, update the `DISPLAY_NAMES` map in `docs/index.html` with a human-readable short name.
- WADO-RS frame retrieval tests use `Accept: multipart/related; type="application/octet-stream"; transfer-syntax=*` to request native encoding (avoids transcoding bugs on GHC).

## CI architecture

- Two service accounts run in parallel via matrix strategy:
  - **default** (`BQ_SERVICE_ACCOUNT`) — runs all tests (IDC Services + DICOMweb Proxy + DICOMweb GHC)
  - **whitelisted** (`GHC_WHITELISTED_SA`) — runs only `tests.test_dicomweb.TestDICOMwebGHC` (GHC DICOMweb tests with a whitelisted SA that has Healthcare API access to `nci-idc-data`)
- Results are uploaded as artifacts, then merged into `docs/data/results.json` by a separate `update-dashboard` job.
- Labeled results appear as separate rows on the dashboard with `[whitelisted]` suffix.

## IDC-specific notes

- IDC data version is tracked as `IDC_VERSION` in `tests/test_dicomweb.py`. Update it when IDC releases a new version.
- The DICOMweb public proxy requires no auth and has 100% data coverage. The Google Healthcare API endpoint requires auth and covers ~96% of data.
- Public proxy URL: `https://proxy.imaging.datacommons.cancer.gov/current/viewer-only-no-downloads-see-tinyurl-dot-com-slash-3j3d9jyp/dicomWeb`
- Google Healthcare API URL pattern: `https://healthcare.googleapis.com/v1/projects/nci-idc-data/locations/us-central1/datasets/idc/dicomStores/idc-store-v{VERSION}/dicomWeb`
- IDC documentation: https://learn.canceridc.dev/
- Use the `imaging-data-commons` Claude skill for IDC domain knowledge.

## Known issues tracked by tests

- **Case 63795270 (fixed)**: High-numbered frame retrieval from SM instances was failing. Regression test: `test_wado_retrieve_sm_frame` fetches frame 33412.
- **Case 66908855 (open)**: Frame transcoding fails for certain SM instances and single-bit segmentations when using transcoding Accept headers. Workaround: request native transfer syntax. Regression tests: `test_wado_retrieve_sm_frame_native` and `test_wado_retrieve_seg_frame`.

## GitHub secrets needed for CI

- `BQ_SERVICE_ACCOUNT` — GCP service account JSON (needs BigQuery and Healthcare API access)
- `GHC_WHITELISTED_SA` — GCP service account JSON whitelisted for Healthcare API access to `nci-idc-data`
- `PROJECT_ID` — GCP project ID
