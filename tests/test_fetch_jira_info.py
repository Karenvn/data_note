from __future__ import annotations

import getpass
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch, sentinel

from data_note.fetch_jira_info import (
    JiraRequestError,
    _extract_jira_error_details,
    _yaml_ssh_target,
    fetch_and_parse_jira_data,
    fetch_jira_issue,
    get_yaml_for_ticket,
)


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


if __name__ == "__main__":
    unittest.main()
