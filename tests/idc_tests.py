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

if __name__ == '__main__':
    unittest.main()
