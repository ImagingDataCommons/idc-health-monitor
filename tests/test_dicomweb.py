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

# SM instance for frame retrieval regression test (Case 63795270)
# High-numbered frame fetch was failing with "one of the frame indexes is not valid"
SM_FRAME_STUDY_UID = "1.2.826.0.1.3680043.8.498.41285422314130783242731156952699253473"
SM_FRAME_SERIES_UID = "1.2.826.0.1.3680043.8.498.66309775612720640014052379381817887378"
SM_FRAME_INSTANCE_UID = "1.2.826.0.1.3680043.8.498.13786005192541160658142740365978773162"
SM_FRAME_NUMBER = "33412"

# SM instance for transcoding regression test (Case 66908855)
# Frame retrieval with transcoding Accept header fails; workaround is Accept: */*
SM_TRANSCODE_STUDY_UID = "2.25.302737996345872783571112300080988167697"
SM_TRANSCODE_SERIES_UID = "1.3.6.1.4.1.5962.99.1.1250863857.1162905243.1637633436401.2.0"
SM_TRANSCODE_INSTANCE_UID = "1.3.6.1.4.1.5962.99.1.1250863857.1162905243.1637633436401.29.0"
SM_TRANSCODE_FRAME_NUMBER = "56"

# SEG instance for segmentation frame retrieval regression test (Case 66908855)
# Single-bit segmentations fail with "BitsAllocated non-divisible by 8" when transcoding
SEG_STUDY_UID = "2.25.248993378467861204438385724637135464855"
SEG_SERIES_UID = "1.2.826.0.1.3680043.10.511.3.24961123847878421867357977308384691"
SEG_INSTANCE_UID = "1.2.826.0.1.3680043.10.511.3.93572833693803919744901431204780845"
SEG_FRAME_NUMBER = "1"

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
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
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
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
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
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
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
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
        metadata = resp.json()
        self.assertIsInstance(metadata, list)
        self.assertGreater(len(metadata), 0)


    def test_wado_retrieve_sm_frame(self):
        """WADO-RS: retrieve a high-numbered frame from an SM instance (Case 63795270 regression)."""
        print("Testing WADO-RS SM frame retrieval (proxy)")
        resp = requests.get(
            f"{self.base_url}/studies/{SM_FRAME_STUDY_UID}/series/{SM_FRAME_SERIES_UID}"
            f"/instances/{SM_FRAME_INSTANCE_UID}/frames/{SM_FRAME_NUMBER}",
            headers={"Accept": "*/*"},
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}")
        self.assertGreater(len(resp.content), 0, "Frame response body is empty")

    def test_wado_retrieve_sm_frame_native(self):
        """WADO-RS: retrieve an SM frame in native transfer syntax (Case 66908855 regression)."""
        print("Testing WADO-RS SM frame native transfer syntax (proxy)")
        resp = requests.get(
            f"{self.base_url}/studies/{SM_TRANSCODE_STUDY_UID}/series/{SM_TRANSCODE_SERIES_UID}"
            f"/instances/{SM_TRANSCODE_INSTANCE_UID}/frames/{SM_TRANSCODE_FRAME_NUMBER}",
            headers={"Accept": 'multipart/related; type="application/octet-stream"; transfer-syntax=*'},
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}")
        self.assertGreater(len(resp.content), 0, "Frame response body is empty")

    def test_wado_retrieve_seg_frame(self):
        """WADO-RS: retrieve a frame from a segmentation instance (Case 66908855 regression)."""
        print("Testing WADO-RS SEG frame retrieval (proxy)")
        resp = requests.get(
            f"{self.base_url}/studies/{SEG_STUDY_UID}/series/{SEG_SERIES_UID}"
            f"/instances/{SEG_INSTANCE_UID}/frames/{SEG_FRAME_NUMBER}",
            headers={"Accept": 'multipart/related; type="application/octet-stream"; transfer-syntax=*'},
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}")
        self.assertGreater(len(resp.content), 0, "Frame response body is empty")


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
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
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
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
        series = resp.json()
        self.assertIsInstance(series, list)
        self.assertGreater(len(series), 0)


    def test_wado_retrieve_sm_frame(self):
        """WADO-RS: retrieve a high-numbered frame from an SM instance (Case 63795270 regression, GHC)."""
        print("Testing WADO-RS SM frame retrieval (GHC)")
        resp = requests.get(
            f"{self.base_url}/studies/{SM_FRAME_STUDY_UID}/series/{SM_FRAME_SERIES_UID}"
            f"/instances/{SM_FRAME_INSTANCE_UID}/frames/{SM_FRAME_NUMBER}",
            headers={**self.headers, "Accept": "*/*"},
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}")
        self.assertGreater(len(resp.content), 0, "Frame response body is empty")

    def test_wado_retrieve_sm_frame_native(self):
        """WADO-RS: retrieve an SM frame in native transfer syntax (Case 66908855 regression, GHC)."""
        print("Testing WADO-RS SM frame native transfer syntax (GHC)")
        resp = requests.get(
            f"{self.base_url}/studies/{SM_TRANSCODE_STUDY_UID}/series/{SM_TRANSCODE_SERIES_UID}"
            f"/instances/{SM_TRANSCODE_INSTANCE_UID}/frames/{SM_TRANSCODE_FRAME_NUMBER}",
            headers={**self.headers, "Accept": 'multipart/related; type="application/octet-stream"; transfer-syntax=*'},
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}")
        self.assertGreater(len(resp.content), 0, "Frame response body is empty")

    def test_wado_retrieve_seg_frame(self):
        """WADO-RS: retrieve a frame from a segmentation instance (Case 66908855 regression, GHC)."""
        print("Testing WADO-RS SEG frame retrieval (GHC)")
        resp = requests.get(
            f"{self.base_url}/studies/{SEG_STUDY_UID}/series/{SEG_SERIES_UID}"
            f"/instances/{SEG_INSTANCE_UID}/frames/{SEG_FRAME_NUMBER}",
            headers={**self.headers, "Accept": 'multipart/related; type="application/octet-stream"; transfer-syntax=*'},
        )
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}")
        self.assertGreater(len(resp.content), 0, "Frame response body is empty")


if __name__ == "__main__":
    unittest.main()
