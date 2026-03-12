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
```

## Project structure

- `tests/idc_tests.py` — BigQuery, IDC API (prod + dev), and portal health checks
- `tests/test_dicomweb.py` — DICOMweb QIDO-RS and WADO-RS health checks (proxy + Google Healthcare API)
- `.github/workflows/run_tests.yml` — CI workflow (daily cron, push, manual dispatch)

## Git workflow

- Always ask for explicit permission before making any git commit or push. Never commit or push automatically.

## Conventions

- Test framework: `unittest` (stdlib). No pytest.
- HTTP requests: `requests` library. No DICOMweb-specific client libraries.
- Tests should print what they're doing (e.g., `print("Testing QIDO-RS studies search")`) for CI log readability.
- Keep tests lightweight — this is health monitoring, not comprehensive integration testing.
- GCP auth uses Application Default Credentials (`google.auth.default()`).

## IDC-specific notes

- IDC data version is tracked as `IDC_VERSION` in `tests/test_dicomweb.py`. Update it when IDC releases a new version.
- The DICOMweb public proxy requires no auth and has 100% data coverage. The Google Healthcare API endpoint requires auth and covers ~96% of data.
- Public proxy URL: `https://proxy.imaging.datacommons.cancer.gov/current/viewer-only-no-downloads-see-tinyurl-dot-com-slash-3j3d9jyp/dicomWeb`
- Google Healthcare API URL pattern: `https://healthcare.googleapis.com/v1/projects/nci-idc-data/locations/us-central1/datasets/idc/dicomStores/idc-store-v{VERSION}/dicomWeb`
- IDC documentation: https://learn.canceridc.dev/
- Use the `imaging-data-commons` Claude skill for IDC domain knowledge.

## GitHub secrets needed for CI

- `BQ_SERVICE_ACCOUNT` — GCP service account JSON (needs BigQuery and Healthcare API access)
- `PROJECT_ID` — GCP project ID
