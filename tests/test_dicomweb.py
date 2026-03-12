import unittest
import os
import requests
import json

# DICOMweb endpoints
PROXY_DICOMWEB_URL = "https://proxy.imaging.datacommons.cancer.gov/current/viewer-only-no-downloads-see-tinyurl-dot-com-slash-3j3d9jyp/dicomWeb"

GHC_DICOMWEB_URL_TEMPLATE = (
    "https://healthcare.googleapis.com/v1/projects/nci-idc-data/locations/us-central1"
    "/datasets/idc/dicomStores/idc-store-v{version}/dicomWeb"
)

# IDC data version - update when IDC releases a new version
IDC_VERSION = "23"

# Known StudyInstanceUID from TCGA (stable, public)
KNOWN_STUDY_UID = "1.3.6.1.4.1.14519.5.2.1.6450.9002.307623500513044641407722230440"

DICOM_JSON_HEADERS = {"Accept": "application/dicom+json"}


def pretty(response):
    print(json.dumps(response.json(), sort_keys=True, indent=4))


def get_ghc_auth_headers():
    """Get OAuth2 Bearer token headers using Application Default Credentials."""
    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-healthcare"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {credentials.token}",
        "Accept": "application/dicom+json",
    }


class TestDICOMwebProxy(unittest.TestCase):
    """Test DICOMweb endpoints via the IDC public proxy (no auth required)."""

    @classmethod
    def setUpClass(cls):
        """Discover a series and instance UID from the known study."""
        cls.base_url = PROXY_DICOMWEB_URL

        # Find one instance in the known study
        resp = requests.get(
            f"{cls.base_url}/studies/{KNOWN_STUDY_UID}/instances",
            params={"limit": "1"},
            headers=DICOM_JSON_HEADERS,
        )
        resp.raise_for_status()
        instance = resp.json()[0]
        # DICOM JSON tag numbers: SeriesInstanceUID=0020000E, SOPInstanceUID=00080018
        cls.series_uid = instance["0020000E"]["Value"][0]
        cls.instance_uid = instance["00080018"]["Value"][0]
        print(f"Discovered SeriesInstanceUID: {cls.series_uid}")
        print(f"Discovered SOPInstanceUID: {cls.instance_uid}")

    def test_qido_search_studies(self):
        """QIDO-RS: search for studies returns results."""
        print("Testing QIDO-RS studies search (proxy)")
        resp = requests.get(
            f"{self.base_url}/studies",
            params={"limit": "1"},
            headers=DICOM_JSON_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}")
        studies = resp.json()
        self.assertIsInstance(studies, list)
        self.assertGreater(len(studies), 0)

    def test_qido_search_series(self):
        """QIDO-RS: search for series within a known study."""
        print("Testing QIDO-RS series search (proxy)")
        resp = requests.get(
            f"{self.base_url}/studies/{KNOWN_STUDY_UID}/series",
            headers=DICOM_JSON_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}")
        series = resp.json()
        self.assertIsInstance(series, list)
        self.assertGreater(len(series), 0)

    def test_qido_search_instances(self):
        """QIDO-RS: search for instances within a known series."""
        print("Testing QIDO-RS instances search (proxy)")
        resp = requests.get(
            f"{self.base_url}/studies/{KNOWN_STUDY_UID}/series/{self.series_uid}/instances",
            params={"limit": "5"},
            headers=DICOM_JSON_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}")
        instances = resp.json()
        self.assertIsInstance(instances, list)
        self.assertGreater(len(instances), 0)

    def test_wado_retrieve_instance_metadata(self):
        """WADO-RS: retrieve metadata for a specific instance."""
        print("Testing WADO-RS instance metadata retrieval (proxy)")
        resp = requests.get(
            f"{self.base_url}/studies/{KNOWN_STUDY_UID}/series/{self.series_uid}/instances/{self.instance_uid}/metadata",
            headers=DICOM_JSON_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}")
        metadata = resp.json()
        self.assertIsInstance(metadata, list)
        self.assertGreater(len(metadata), 0)


class TestDICOMwebGHC(unittest.TestCase):
    """Test DICOMweb endpoints via Google Healthcare API (authenticated)."""

    @classmethod
    def setUpClass(cls):
        """Authenticate and build the base URL."""
        cls.headers = get_ghc_auth_headers()
        cls.base_url = GHC_DICOMWEB_URL_TEMPLATE.format(version=IDC_VERSION)

    def test_qido_search_studies(self):
        """QIDO-RS: search for studies returns results (GHC)."""
        print("Testing QIDO-RS studies search (GHC)")
        resp = requests.get(
            f"{self.base_url}/studies",
            params={"limit": "1"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}")
        studies = resp.json()
        self.assertIsInstance(studies, list)
        self.assertGreater(len(studies), 0)

    def test_qido_search_series(self):
        """QIDO-RS: search for series within a known study (GHC)."""
        print("Testing QIDO-RS series search (GHC)")
        resp = requests.get(
            f"{self.base_url}/studies/{KNOWN_STUDY_UID}/series",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}")
        series = resp.json()
        self.assertIsInstance(series, list)
        self.assertGreater(len(series), 0)


if __name__ == "__main__":
    unittest.main()
