# IDC Health Monitor

Automated health checks for [NCI Imaging Data Commons](https://imaging.datacommons.cancer.gov/) services. Runs daily via GitHub Actions to verify that IDC infrastructure is operational.

**Live dashboard:** [imagingdatacommons.github.io/idc-health-monitor](https://imagingdatacommons.github.io/idc-health-monitor/)

## What's monitored

| Service | Test file | Auth required |
|---------|-----------|---------------|
| BigQuery (`idc_current.dicom_all`) | `tests/idc_tests.py` | Yes (GCP service account) |
| IDC API (prod + dev) | `tests/idc_tests.py` | No |
| IDC Portal | `tests/idc_tests.py` | No |
| DICOMweb public proxy (QIDO-RS, WADO-RS) | `tests/test_dicomweb.py` | No |
| DICOMweb Google Healthcare API | `tests/test_dicomweb.py` | Yes (GCP service account) |

## Local development

### Setup

```bash
uv venv
source .venv/bin/activate
uv pip install requests google-cloud-bigquery google-auth
```

### Running tests

Run all tests (requires GCP credentials for BigQuery and Healthcare API tests):

```bash
python -m unittest -v tests/idc_tests.py tests/test_dicomweb.py
```

Run only the DICOMweb proxy tests (no credentials needed):

```bash
python -m unittest -v tests.test_dicomweb.TestDICOMwebProxy
```

### GCP authentication for local runs

For tests that require Google Cloud credentials (BigQuery, Healthcare API):

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export PROJECT_ID=your-gcp-project-id
```

## GitHub Actions

The workflow (`.github/workflows/run_tests.yml`) runs on:
- Push to `main`
- Manual dispatch
- Daily schedule (7:30 AM UTC)

### Required secrets

| Secret | Purpose |
|--------|---------|
| `BQ_SERVICE_ACCOUNT` | GCP service account JSON for BigQuery and Healthcare API access |
| `PROJECT_ID` | GCP project ID for BigQuery client |

## Adding new tests

1. Create a new test file in `tests/` following the `unittest.TestCase` pattern
2. Add docstrings to test methods (displayed on the dashboard)
3. Import and load the new module in `scripts/run_tests_json.py`
4. Add any new pip dependencies to the workflow's install step

## Key constants to maintain

- **IDC data version** (`IDC_VERSION` in `tests/test_dicomweb.py`): Update when IDC releases a new data version. Current: v23.
- **Known StudyInstanceUID** (`KNOWN_STUDY_UID` in `tests/test_dicomweb.py`): Used for targeted DICOMweb queries. Should be a stable, public study unlikely to be removed.

## License

MIT
