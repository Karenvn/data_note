from __future__ import annotations

import getpass
import tempfile
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch, sentinel

import requests

from data_note.fetch_jira_info import (
    JiraRequestError,
    _extract_jira_error_details,
    _jira_get,
    _yaml_ssh_target,
    fetch_and_parse_jira_data,
    fetch_jira_issue,
    get_yaml_for_ticket,
    parse_yaml_attachment,
)


def make_response(
    *,
    status_code: int = 200,
    text: str = "",
    content_type: str | None = "application/json",
    url: str = "https://jira.example/rest/api/2/issue/GRIT-1124",
    headers: dict[str, str] | None = None,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.url = url
    response._content = text.encode("utf-8")
    response.encoding = "utf-8"
    if content_type:
        response.headers["content-type"] = content_type
    if headers:
        response.headers.update(headers)
    return response


class FetchJiraInfoTests(unittest.TestCase):
    def test_yaml_ssh_target_defaults_to_local_user_and_tol22(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            ssh_user, ssh_host = _yaml_ssh_target()

        self.assertEqual(ssh_user, getpass.getuser())
        self.assertEqual(ssh_host, "tol22")

    def test_extract_jira_error_details_from_xml(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<status>
  <status-code>500</status-code>
  <message>org.ofbiz.core.entity.GenericDataSourceException: Unable to establish a connection with the database.</message>
  <stack-trace>Please contact your admin passing attached Log's referral number: 84de793b-4464-43f9-b3b9-b96686cc907a</stack-trace>
</status>
"""

        details = _extract_jira_error_details(xml)

        self.assertIn("Unable to establish a connection with the database", details or "")
        self.assertIn("84de793b-4464-43f9-b3b9-b96686cc907a", details or "")

    @patch("data_note.fetch_jira_info.requests.get")
    def test_jira_get_reports_portal_redirect_without_following_it(self, mock_get) -> None:
        mock_get.return_value = make_response(
            status_code=302,
            text='<a href="https://portal.sanger.ac.uk/web/launch/jira.sanger.ac.uk">Found</a>',
            content_type="text/html; charset=utf-8",
            headers={
                "Location": "https://portal.sanger.ac.uk/web/launch/jira.sanger.ac.uk?path=%2Frest%2Fapi%2F2%2Fissue%2FRC-1685"
            },
        )

        with self.assertRaises(JiraRequestError) as ctx:
            _jira_get("https://jira.sanger.ac.uk/rest/api/2/issue/RC-1685", auth=sentinel.auth)

        self.assertIn("redirected to https://portal.sanger.ac.uk", str(ctx.exception))
        self.assertFalse(ctx.exception.retryable)
        self.assertEqual(mock_get.call_count, 1)
        self.assertFalse(mock_get.call_args.kwargs["allow_redirects"])

    @patch("data_note.fetch_jira_info.get_auth", return_value=sentinel.auth)
    @patch(
        "data_note.fetch_jira_info._jira_get",
        side_effect=JiraRequestError(
            "HTTP 500: Unable to establish a connection with the database; "
            "log reference: 84de793b-4464-43f9-b3b9-b96686cc907a"
        ),
    )
    def test_fetch_jira_issue_reports_clean_error(
        self,
        _mock_jira_get,
        _mock_get_auth,
    ) -> None:
        with self.assertLogs("data_note.fetch_jira_info", level="WARNING") as logs:
            issue = fetch_jira_issue("GRIT-1124")

        self.assertIsNone(issue)
        output = "\n".join(logs.output)
        self.assertIn("Failed to fetch JIRA issue GRIT-1124", output)
        self.assertIn("log reference: 84de793b-4464-43f9-b3b9-b96686cc907a", output)

    @patch("data_note.fetch_jira_info.get_auth", return_value=sentinel.auth)
    @patch("data_note.fetch_jira_info._jira_get")
    def test_fetch_jira_issue_reports_non_json_portal_response(
        self,
        mock_jira_get,
        _mock_get_auth,
    ) -> None:
        mock_jira_get.return_value = make_response(
            text="<!DOCTYPE html><html><body>Portal login</body></html>",
            content_type="text/html; charset=utf-8",
            url="https://portal.sanger.ac.uk/web/launch/jira.sanger.ac.uk?path=%2Frest%2Fapi%2F2%2Fissue%2FRC-1685",
        )

        with self.assertLogs("data_note.fetch_jira_info", level="WARNING") as logs:
            issue = fetch_jira_issue("RC-1685")

        self.assertIsNone(issue)
        output = "\n".join(logs.output)
        self.assertIn("JIRA REST API did not return JSON for issue RC-1685", output)
        self.assertIn("Sanger Portal/SSO", output)

    @patch("data_note.fetch_jira_info._yaml_ssh_target", return_value=("ssh-user", "tol22"))
    @patch("data_note.fetch_jira_info.fetch_or_copy_yaml", return_value=Path("yaml_cache/GRIT-1124.yaml"))
    @patch("data_note.fetch_jira_info.fetch_jira_issue")
    def test_get_yaml_for_ticket_ignores_attachment_and_uses_remote_path(
        self,
        mock_fetch_jira_issue,
        mock_fetch_or_copy_yaml,
        _mock_yaml_ssh_target,
    ) -> None:
        mock_fetch_jira_issue.return_value = {
            "key": "GRIT-1124",
            "fields": {
                "attachment": [
                    {"filename": "run.yaml", "content": "https://jira.example/attachment/2"},
                ],
                "customfield_13408": "/nfs/path/run.yaml",
            },
        }

        result = get_yaml_for_ticket("GRIT-1124", auth=sentinel.auth)

        self.assertEqual(result, Path("yaml_cache/GRIT-1124.yaml"))
        mock_fetch_or_copy_yaml.assert_called_once_with(
            local_base="yaml_cache",
            tolid="GRIT-1124",
            remote_path="/nfs/path/run.yaml",
            ssh_user="ssh-user",
            ssh_host="tol22",
        )

    @patch("data_note.fetch_jira_info.fetch_or_copy_yaml")
    @patch("data_note.fetch_jira_info.fetch_jira_issue")
    def test_get_yaml_for_ticket_reuses_existing_cache_before_remote_lookup(
        self,
        mock_fetch_jira_issue,
        mock_fetch_or_copy_yaml,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cached_yaml = Path(tmpdir) / "GRIT-1124.yaml"
            cached_yaml.write_text("pipeline:\n  - hifiasm (version 1.0.0)\n")

            with patch.dict("os.environ", {"YAML_CACHE_DIR": tmpdir}):
                result = get_yaml_for_ticket("GRIT-1124", auth=sentinel.auth)

        self.assertEqual(result, cached_yaml)
        mock_fetch_jira_issue.assert_not_called()
        mock_fetch_or_copy_yaml.assert_not_called()

    @patch("data_note.fetch_jira_info.get_auth", return_value=sentinel.auth)
    @patch("data_note.fetch_jira_info.get_yaml_for_ticket")
    @patch("data_note.fetch_jira_info._jira_get")
    @patch("data_note.fetch_jira_info.fetch_jira_issue")
    def test_fetch_and_parse_jira_data_uses_remote_yaml_even_when_attachment_exists(
        self,
        mock_fetch_jira_issue,
        mock_jira_get,
        mock_get_yaml_for_ticket,
        _mock_get_auth,
    ) -> None:
        mock_fetch_jira_issue.return_value = {
            "fields": {
                "attachment": [
                    {"filename": "notes.txt", "content": "https://jira.example/attachment/1"},
                    {"filename": "run.yaml", "content": "https://jira.example/attachment/2"},
                ],
                "customfield_11608": "",
                "customfield_11648": "",
            }
        }
        mock_get_yaml_for_ticket.return_value = Path("yaml_cache/GRIT-1124.yaml")

        with patch("builtins.open", mock_open(read_data="pipeline:\n  - hifiasm (version 1.0.0)\n")):
            jira_dict = fetch_and_parse_jira_data("GRIT-1124")

        self.assertEqual(jira_dict["hifiasm_version"], "1.0.0")
        mock_get_yaml_for_ticket.assert_called_once_with("GRIT-1124", sentinel.auth)
        mock_jira_get.assert_not_called()

    def test_parse_yaml_attachment_ignores_quality_metrics(self) -> None:
        yaml_content = """\
busco_lineage: eudicots_odb10
pipeline:
  - hifiasm (version 0.16.1-r375)
  - purge_dups (version 1.2.3)
stats: |
  merqury QV (CCS): 59.4
  merqury KMER completeness (CCS): 99.00
  BUSCO: C:98.2%[S:93.4%,D:4.8%],F:0.8%,M:1.0%,n:2326
"""

        parsed = parse_yaml_attachment(yaml_content)

        self.assertEqual(parsed["hifiasm_version"], "0.16.1-r375")
        self.assertEqual(parsed["purge_dups_version"], "1.2.3")
        self.assertNotIn("yaml_BUSCO_lineage", parsed)
        self.assertNotIn("yaml_BUSCO_n", parsed)
        self.assertNotIn("yaml_BUSCO_string", parsed)
        self.assertNotIn("yaml_merqury_QV", parsed)
        self.assertNotIn("yaml_merqury_kmer_completeness", parsed)

    @patch("data_note.fetch_jira_info.get_auth", return_value=sentinel.auth)
    @patch("data_note.fetch_jira_info.get_yaml_for_ticket", return_value=None)
    @patch("data_note.fetch_jira_info.fetch_jira_issue")
    def test_fetch_and_parse_jira_data_tolerates_null_chromosome_result(
        self,
        mock_fetch_jira_issue,
        _mock_get_yaml_for_ticket,
        _mock_get_auth,
    ) -> None:
        mock_fetch_jira_issue.return_value = {
            "fields": {
                "customfield_11608": "",
                "customfield_11645": None,
                "customfield_11648": "",
            }
        }

        jira_dict = fetch_and_parse_jira_data("GRIT-1124")

        self.assertNotIn("jira_perc_assem", jira_dict)


if __name__ == "__main__":
    unittest.main()
