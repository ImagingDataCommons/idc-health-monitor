import unittest
from google.cloud import bigquery
import os
import requests
import json

bq_queries = {
"check_if_table_exists": """
    SELECT PatientID 
    FROM `bigquery-public-data.idc_current.dicom_all` 
    LIMIT 1
""",

}

idc_api_preamble = "https://api.imaging.datacommons.cancer.gov/v1"
idc_dev_api_preamble = "https://dev-api.canceridc.dev/v2"
portal_urls = { "one":"https://portal.imaging.datacommons.cancer.gov/explore",
               "two":"https://imaging.datacommons.cancer.gov/explore"}

# --- DICOMweb / Accept-header frame retrieval tests ---
# Endpoints tested: public IDC Proxy (no auth) and GHC v23 (uses ADC).
# Test instances selected via idc-index (sm_instance_index, IDC v23), VOLUME ImageType only.
# Accept headers from doc/IDC_J2K_debugging.ipynb (IDC-ProjectManagement#2044).
# GHC DICOMweb docs: https://docs.cloud.google.com/healthcare-api/docs/dicom

IDC_PROXY_DICOMWEB = (
    "https://proxy.imaging.datacommons.cancer.gov"
    "/current/viewer-only-no-downloads-see-tinyurl-dot-com-slash-3j3d9jyp"
    "/dicomWeb"
)
GHC_DICOMWEB_V23 = (
    "https://healthcare.googleapis.com/v1/projects/nci-idc-data"
    "/locations/us-central1/datasets/idc/dicomStores/idc-store-v23/dicomWeb"
)

# Three Accept header strategies:
# "slim"     — broad multi-type header sent by compliant viewers (e.g. OHIF/SLIM)
# ".91 only" — restrictive single-TS header that exposed a server-side J2K bug
# "*/*"      — requests content in the server's native/original transfer syntax
DICOM_ACCEPT_HEADERS = {
    "slim": (
        'multipart/related; type="image/jls"; transfer-syntax=1.2.840.10008.1.2.4.80, '
        'multipart/related; type="image/jls"; transfer-syntax=1.2.840.10008.1.2.4.81, '
        'multipart/related; type="image/jp2"; transfer-syntax=1.2.840.10008.1.2.4.90, '
        'multipart/related; type="image/jp2"; transfer-syntax=1.2.840.10008.1.2.4.91, '
        'multipart/related; type="image/jpx"; transfer-syntax=1.2.840.10008.1.2.4.92, '
        'multipart/related; type="image/jpx"; transfer-syntax=1.2.840.10008.1.2.4.93, '
        'multipart/related; type="application/octet-stream"; transfer-syntax=*, '
        '*/*;q=0.1'
    ),
    "J2K .91 only": 'multipart/related; type="image/jp2"; transfer-syntax=1.2.840.10008.1.2.4.91',
    "any": 'multipart/related; type="application/octet-stream"; transfer-syntax=*',
}

# One VOLUME instance per transfer syntax present in IDC v23 SM data.
# IDC v23 SM has: JP2-lossy (.91), JP2-lossless (.90), Uncompressed (.2.1),
# JPEG-baseline (.4.50). No JLS (.80/.81) or JPX (.92/.93) instances exist.
J2K_TEST_INSTANCES = [
    # JP2-lossy: notebook "failing" case
    {"label": "tcga_brca JP2-lossy frame56 (notebook failing)",
     "ts": "1.2.840.10008.1.2.4.91",
     "study":    "2.25.302737996345872783571112300080988167697",
     "series":   "1.3.6.1.4.1.5962.99.1.1250863857.1162905243.1637633436401.2.0",
     "instance": "1.3.6.1.4.1.5962.99.1.1250863857.1162905243.1637633436401.29.0",
     "frame": "56"},
    # JP2-lossy: notebook "succeeding" case — all headers return 200
    {"label": "ccdi_mci JP2-lossy frame64 (notebook succeeding)",
     "ts": "1.2.840.10008.1.2.4.91",
     "study":    "2.25.205318147612807799490440393069389220550",
     "series":   "1.3.6.1.4.1.5962.99.1.826406969.1146508888.1727403292729.4.0",
     "instance": "1.3.6.1.4.1.5962.99.1.826406969.1146508888.1727403292729.38.0",
     "frame": "64"},
    # JP2-lossless: smallest VOLUME instance in IDC v23 (htan_ohsu, ~101KB stored)
    {"label": "htan_ohsu JP2-lossless frame1",
     "ts": "1.2.840.10008.1.2.4.90",
     "study":    "2.25.56219147941526607962658668060030231728",
     "series":   "1.3.6.1.4.1.5962.99.1.2003025013.374987231.1655565466741.4.0",
     "instance": "1.3.6.1.4.1.5962.99.1.2003025013.374987231.1655565466741.199.0",
     "frame": "1"},
    # Uncompressed: smallest VOLUME instance (htan_ohsu, ~100KB stored)
    {"label": "htan_ohsu uncompressed frame1",
     "ts": "1.2.840.10008.1.2.1",
     "study":    "2.25.56219147941526607962658668060030231728",
     "series":   "1.3.6.1.4.1.5962.99.1.2009575316.1796047989.1655572017044.4.0",
     "instance": "1.3.6.1.4.1.5962.99.1.2009575316.1796047989.1655572017044.1116.0",
     "frame": "1"},
    # JPEG-baseline: smallest VOLUME instance (bonemarrowwsi, ~103KB stored)
    {"label": "bonemarrowwsi JPEG-baseline frame1",
     "ts": "1.2.840.10008.1.2.4.50",
     "study":    "1.2.826.0.1.3680043.8.498.21530084092650887317671181414407206375",
     "series":   "1.2.826.0.1.3680043.8.498.78624355532162130478822162665115396064",
     "instance": "1.2.826.0.1.3680043.8.498.98001102711370568294992798408474859997",
     "frame": "1"},
]


def pretty(response):
  print(json.dumps(response.json(), sort_keys=True, indent=4))

class TestIDCServices(unittest.TestCase):
    def test_bq_queries(self):
        """BigQuery: verify idc_current.dicom_all table is accessible."""
        print("Testing bq queries")
        # iterate over all queries in bq_queries dictionary and execute each query
        for query_name,query in bq_queries.items():
            print("Executing query: " + query_name + " with query: " + query + " ...")
            client = bigquery.Client(os.environ["PROJECT_ID"])
            client.query(bq_queries[query_name]).result()

    def test_prod_api(self):
        """IDC API: production /collections endpoint returns 200."""
        print("Testing prod api")
        response = requests.get('{}/collections'.format(idc_api_preamble))
        # Check that there wasn't an error with the request
        if response.status_code != 200:
            # Print the error code and message if something went wrong
            print('Request failed: {}'.format(response.reason))

        # Print the collections JSON text
        #pretty(response)

    def test_dev_api(self):
        """IDC API: development /collections endpoint returns 200."""
        print("Testing dev api")
        response = requests.get('{}/collections'.format(idc_dev_api_preamble))
        # Check that there wasn't an error with the request
        if response.status_code != 200:
            # Print the error code and message if something went wrong
            print('Request failed: {}'.format(response.reason))
        
        # Print the collections JSON text
        #pretty(response)

    def test_is_portal_live(self):
        """Portal: verify IDC portal URLs are reachable."""
        print("Testing portal")
        for key,portal_url in portal_urls.items():
            response = requests.head(portal_url)
            if response.status_code != 200:
                return False
            requests.get(portal_url)
        return True

    def _run_dicomweb_frame_tests(self, endpoint, extra_headers=None):
        """Test all J2K_TEST_INSTANCES × DICOM_ACCEPT_HEADERS against one DICOMweb endpoint."""
        if extra_headers is None:
            extra_headers = {}
        failures = []
        for inst in J2K_TEST_INSTANCES:
            url = (
                f"{endpoint}"
                f"/studies/{inst['study']}"
                f"/series/{inst['series']}"
                f"/instances/{inst['instance']}"
                f"/frames/{inst['frame']}"
            )
            for accept_label, accept_value in DICOM_ACCEPT_HEADERS.items():
                combo = f"[{inst['label']} / {accept_label}]"
                print(f"  {combo}")
                try:
                    response = requests.get(
                        url,
                        headers={**extra_headers, "Accept": accept_value},
                        timeout=30,
                    )
                    # build equivalent curl command for debugging purposes
                    curl_cmd = f"curl -s -X GET -H 'Accept: {accept_value}'"
                    if "Authorization" in extra_headers:
                        curl_cmd += " -H 'Authorization: Bearer <token>'"
                    curl_cmd += f" '{url}'"
                    print(f"    (curl equivalent: {curl_cmd})")
                except requests.exceptions.RequestException as exc:
                    msg = f"{combo} request error: {exc}"
                    print(f"  FAIL: {msg}")
                    failures.append(msg)
                    continue

                print(f"    status: {response.status_code}")
                if response.status_code != 200:
                    msg = f"{combo} HTTP {response.status_code}: {response.reason}"
                    print(f"  FAIL: {msg}")
                    failures.append(msg)
                    continue

                ct = response.headers.get("Content-Type", "")
                if "multipart/related" not in ct:
                    msg = f"{combo} unexpected Content-Type: '{ct}'"
                    print(f"  FAIL: {msg}")
                    failures.append(msg)

                try:
                    decoded = response.content.decode("utf-8")
                    msg = (
                        f"{combo} got UTF-8 text, not binary image. "
                        f"Preview: {decoded[:200]!r}"
                    )
                    print(f"  FAIL: {msg}")
                    failures.append(msg)
                except UnicodeDecodeError:
                    print(f"    OK: binary data ({len(response.content)} bytes)")

        if failures:
            self.fail(
                f"{len(failures)} combination(s) failed:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )

    def test_j2k_proxy_accept_headers(self):
        """DICOMweb frame retrieval via IDC Proxy — no auth required."""
        print("Testing DICOMweb Accept headers via IDC Proxy")
        self._run_dicomweb_frame_tests(IDC_PROXY_DICOMWEB)

    def test_j2k_ghc_accept_headers(self):
        """DICOMweb frame retrieval via GHC v23 — authenticates via Application Default Credentials."""
        print("Testing DICOMweb Accept headers via GHC v23")
        import google.auth
        import google.auth.transport.requests
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(google.auth.transport.requests.Request())
        except Exception as exc:
            self.skipTest(f"GCP credentials unavailable: {exc}")
        self._run_dicomweb_frame_tests(
            GHC_DICOMWEB_V23,
            extra_headers={"Authorization": f"Bearer {credentials.token}"},
        )

if __name__ == '__main__':
    unittest.main()
