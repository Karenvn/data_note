from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from data_note.fetch_btk_info import fetch_and_parse_summary, fetch_software_versions


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    response.url = "https://blobtoolkit.genomehubs.org/api/v1/summary/GCA_missing.1"
    return requests.exceptions.HTTPError(f"{status_code} Client Error", response=response)


class FetchBtkInfoTests(unittest.TestCase):
    def test_missing_secondary_summary_is_informational(self) -> None:
        response = requests.Response()
        response.raise_for_status = Mock(side_effect=_http_error(404))

        with patch("data_note.fetch_btk_info.requests.get", return_value=response), self.assertLogs(
            "data_note.fetch_btk_info",
            level="INFO",
        ) as logs:
            result = fetch_and_parse_summary("GCA_missing.1", prefix="hap2_")

        self.assertEqual(result, {})
        output = "\n".join(logs.output)
        self.assertIn("Optional BTK summary is not available for haplotype 2 GCA_missing.1", output)
        self.assertNotIn("WARNING", output)

    def test_missing_primary_summary_remains_warning(self) -> None:
        response = requests.Response()
        response.raise_for_status = Mock(side_effect=_http_error(404))

        with patch("data_note.fetch_btk_info.requests.get", return_value=response), self.assertLogs(
            "data_note.fetch_btk_info",
            level="WARNING",
        ) as logs:
            result = fetch_and_parse_summary("GCA_missing.1")

        self.assertEqual(result, {})
        output = "\n".join(logs.output)
        self.assertIn("Failed to fetch BTK summary for GCA_missing.1", output)

    def test_software_versions_exposes_btk_busco_version(self) -> None:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {
            "release": "1.6.0",
            "software_versions": {
                "busco": "5.8.0",
                "blobtoolkit": "4.2.1",
            },
        }

        with patch("data_note.fetch_btk_info.requests.get", return_value=response):
            versions = fetch_software_versions("GCA_1.1")

        self.assertEqual(versions["busco_version"], "5.8.0")
        self.assertEqual(versions["btk_busco_version"], "5.8.0")


if __name__ == "__main__":
    unittest.main()
