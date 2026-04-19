#!/usr/bin/env python3


import requests
from netrc import netrc
import getpass
import os
import re
import xml.etree.ElementTree as ET
from .grit_jira_auth import GritJiraAuth
from .formatting_utils import percentage_change_from_a_to_b, format_with_nbsp
import yaml
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from .yaml_utils import fetch_or_copy_yaml
from num2words import num2words
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from tol.sources.defaults import Defaults
    DEFAULT_JIRA_BASE_URL = Defaults.JIRA_URL
except Exception:
    DEFAULT_JIRA_BASE_URL = "https://jira.sanger.ac.uk"

YAML_FIELD_ID = "customfield_13408"
JIRA_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
JIRA_TIMEOUT_SECONDS = int(os.getenv("JIRA_TIMEOUT_SECONDS", "30"))


def _jira_base_url():
    base_url = os.getenv("JIRA_BASE_URL")
    if base_url:
        return base_url.rstrip("/")

    domain = os.getenv("JIRA_DOMAIN")
    if not domain:
        return DEFAULT_JIRA_BASE_URL

    parsed = urlparse(domain if "://" in domain else f"https://{domain}")
    resolved_domain = parsed.netloc or parsed.path
    return f"https://{resolved_domain}" if resolved_domain else DEFAULT_JIRA_BASE_URL


def _jira_domain():
    base_url = _jira_base_url()
    if not base_url:
        return None

    parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
    return parsed.netloc or parsed.path or None


def _yaml_cache_dir() -> Path:
    return Path(os.getenv("YAML_CACHE_DIR", "yaml_cache"))


def _yaml_ssh_target() -> tuple[str, str]:
    return (
        os.getenv("YAML_SSH_USER") or getpass.getuser(),
        os.getenv("YAML_SSH_HOST") or "tol22",
    )


class JiraRequestError(requests.exceptions.RequestException):
    """Raised when Jira returns an HTTP or transport failure."""


def _extract_jira_error_details(response_text: str) -> str | None:
    if not response_text:
        return None

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError:
        return None

    message = root.findtext("message")
    stack_trace = root.findtext("stack-trace") or ""
    referral_match = re.search(r"referral number:\s*([0-9a-f\-]+)", stack_trace, re.IGNORECASE)
    referral = referral_match.group(1) if referral_match else None

    details = []
    if message:
        details.append(message.strip())
    if referral:
        details.append(f"log reference: {referral}")
    return "; ".join(details) if details else None


def _format_jira_error(response: requests.Response) -> str:
    details = _extract_jira_error_details(response.text)
    if details:
        return details

    snippet = response.text.strip().replace("\n", " ")
    if snippet:
        return snippet[:300]
    return response.reason or "Unknown Jira error"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.exceptions.RequestException,)),
)
def _jira_get(url: str, *, auth, timeout: int = JIRA_TIMEOUT_SECONDS) -> requests.Response:
    response = requests.get(
        url,
        auth=auth,
        timeout=timeout,
        headers={"Accept": "application/json"},
    )

    if response.status_code in JIRA_RETRY_STATUS_CODES:
        details = _format_jira_error(response)
        print(f"Retryable JIRA HTTP error {response.status_code}: {details}")
        raise JiraRequestError(f"HTTP {response.status_code}: {details}")

    if response.status_code >= 400:
        details = _format_jira_error(response)
        raise JiraRequestError(f"HTTP {response.status_code}: {details}")

    return response


#-------------------------------- utilities-----------------

def get_auth():
    """Set up and return authentication for JIRA."""
    jira_domain = _jira_domain()
    if not jira_domain:
        raise RuntimeError("No JIRA domain could be resolved.")

    netrc_path = os.path.join(os.path.expanduser('~'), '.netrc')
    auth_credentials = netrc(netrc_path).authenticators(jira_domain)

    if not auth_credentials:
        raise Exception("No credentials found for JIRA domain in .netrc file")

    return GritJiraAuth(auth_credentials[0], auth_credentials[2])

def download_jira_attachment_http(url: str, local_path: str, auth) -> str:
    """
    Fetch a JIRA attachment by HTTP GET (using basic auth),
    save to `local_path`, and return that path.
    """
    r = _jira_get(url, auth=auth)
    with open(local_path, "wb") as fh:
        fh.write(r.content)
    return local_path


def parse_yaml_info(issue):  # this is a terrible name for a function that is actually organising a fallback
    """
    Look first for a .yaml attachment on the JIRA issue.
    If found, return (kind="attachment", url=<download-url>).
    Otherwise, look for the server‐path field and return
    (kind="server", path=<lustre‑path>).
    If neither, return (None, None).
    """
    # 1) attachments
    for att in issue["fields"].get("attachment", []):
        if att.get("filename", "").endswith(".yaml"):
            return "attachment", att["content"]  # JIRA download URL

    # 2) fallback to custom‑field
    server_path = issue["fields"].get(YAML_FIELD_ID)
    if server_path:
        return "server", server_path

    return None, None

def get_yaml_for_ticket(ticket, auth):
    """
    Return a Path to the YAML file for the given JIRA ticket:
    - if a .yaml attachment exists, download it via HTTP
    - otherwise fall back to the server path via SCP
    """
    issue = fetch_jira_issue(ticket)
    if not issue:
        return None

    # parse_yaml_info now returns (kind, data)
    kind, data = parse_yaml_info(issue)

    if kind == "attachment" and data:
        local_path = _yaml_cache_dir() / f"{ticket}.yaml"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        download_jira_attachment_http(data, str(local_path), auth)
        return local_path

    if kind == "server" and data:
        ssh_user, ssh_host = _yaml_ssh_target()

        return fetch_or_copy_yaml(
            local_base  = str(_yaml_cache_dir()),
            tolid       = ticket,
            remote_path = data,
            ssh_user    = ssh_user,
            ssh_host    = ssh_host
        )

    print(f"[error] No YAML available for ticket {ticket}")
    return None



def get_change_direction_and_value(change_value):
    if abs(change_value) < 0.5:
        return None
    direction = 'increased' if change_value > 0 else 'reduced'
    value = f"{abs(change_value):.1f}%"
    return (direction, value)


def text_num(n: int) -> str:
    return num2words(n) if n <= 10 else str(n)

# -------------------------------- core functions---------------

def fetch_jira_issue(jira_ticket_id):
    """ Fetch a JIRA issue using the ticket ID from ToLA spreadsheet. """
    jira_base_url = _jira_base_url()
    if not jira_base_url:
        print("JIRA is not configured; skipping JIRA lookup.")
        return None

    url = f"{jira_base_url}/rest/api/2/issue/{jira_ticket_id}"

    try:
        auth = get_auth()
    except Exception as exc:
        print(f"JIRA authentication unavailable: {exc}")
        return None

    try:
        response = _jira_get(url, auth=auth)
    except requests.exceptions.RequestException as exc:
        print(f"Failed to fetch JIRA issue {jira_ticket_id}: {exc}")
        return None

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        print(f"Error parsing JSON for JIRA issue {jira_ticket_id}: {e}")
        print("Response content:", response.text)
        return None


def fetch_and_parse_jira_data(jira_ticket_id):
    """ Fetch and process JIRA issue data based on specified field IDs within the JSON data. """
    if not _jira_base_url():
        print("JIRA is not configured; skipping JIRA enrichment.")
        return {}

    try:
        auth = get_auth()
    except Exception as exc:
        print(f"JIRA authentication unavailable: {exc}")
        return {}

    response_data = fetch_jira_issue(jira_ticket_id)

    if not response_data:
        return {}

    id_for_custom_field_name = {
        'chromosome_naming': 11607,
        'assembly_type': 11624,
        'manual_breaks': 11615,
        'manual_joins': 11681,
        'manual_haplotig_removals': 11632,
        'manual_inversions': 11610,
        'assembly_statistics': 11608,
        'chromosome_result': 11645,
        'curator_note': 11614,
        'autosomes': 11659,
        'jira_sex_chromosomes': 11617,
        'synteny_source': 11622,
        'observed_sex':11601,
        'gfastats':11648,
        'yaml_path':13408
    }

    jira_dict = {}

    for field_name, field_id in id_for_custom_field_name.items():
        full_field_id = f'customfield_{field_id}'
        if full_field_id in response_data['fields']:
            jira_dict[field_name] = response_data['fields'][full_field_id]

    for key, value in jira_dict.items():
        if isinstance(value, dict) and 'value' in value:
            jira_dict[key] = value['value']

    # Ensure `chromosome_naming` value is lowercase if it exists
    if isinstance(jira_dict.get('chromosome_naming'), str):
        jira_dict['chromosome_naming'] = jira_dict['chromosome_naming'].lower()

    assembly_statistics = jira_dict.get('assembly_statistics') or ""
    gfastats = jira_dict.get('gfastats') or ""

    stats_lines = assembly_statistics.split('\n')
    contig_data_found = False

    for line in stats_lines:
        if contig_data_found:
            if 'count' in line:
                count_parsing_result = re.match(r'count \d+ (\d+)', line)
                if count_parsing_result:
                    jira_dict['jira_contig_count'] = int(count_parsing_result.group(1))
                    jira_contig_count = int(count_parsing_result.group(1))
                    formatted_jira_contig_count = format_with_nbsp(jira_contig_count, as_int = True)
                    jira_dict['jira_contig_count'] = formatted_jira_contig_count
                break 
        if 'contigs' in line:
            contig_data_found = True  
        stats_parsing_result = re.match(r'^(\S+)\s+(\d+)\s+(\d+)', line)
        if stats_parsing_result:
            label = stats_parsing_result.group(1).lower() + '_before_curation'
            jira_dict[label] = int(stats_parsing_result.group(2))
            label = stats_parsing_result.group(1).lower() + '_after_curation'
            jira_dict[label] = int(stats_parsing_result.group(3))

    if gfastats:
        gfastats_lines = gfastats.split('\n')
        results_dict = {}
        key_count = {}

        key_name_mapping = {
            '# gaps in scaffolds': 'gap_count',
            'Total gap length in scaffolds': 'total_gap_length',
            'Average gap length in scaffolds': 'av_gap_length'
        }

        for line in gfastats_lines:
    
            parts = line.split('\t')
            if len(parts) == 2:
                original_key, value = parts[0].strip(), parts[1].strip()

                if original_key in key_name_mapping:
                    if original_key in key_count:
                        key_count[original_key] += 1
                    else:
                        key_count[original_key] = 1
                    if key_count[original_key] == 2:  # Only keep post-curation statistics
                        # Remove commas and convert to float
                        value = float(value.replace(',', ''))
                        results_dict[key_name_mapping[original_key]] = value

# Format the values in results_dict to have nbsp separators for thousands
        formatted_results_dict = {key: format_with_nbsp(value, as_int=(key == 'gap_count')) for key, value in results_dict.items()}
        #print("gaps_dict for debugging:", formatted_results_dict)

        jira_dict.update(formatted_results_dict)

    jira_dict['scaffold_total_length_change'] = percentage_change_from_a_to_b(
        int(jira_dict.get('total_before_curation', 0)), int(jira_dict.get('total_after_curation', 0))
    )
    jira_dict['scaffold_count_change'] = percentage_change_from_a_to_b(
        int(jira_dict.get('count_before_curation', 0)), int(jira_dict.get('count_after_curation', 0))
    )
    jira_dict['scaffold_N50_change'] = percentage_change_from_a_to_b(
        int(jira_dict.get('n50_before_curation', 0)), int(jira_dict.get('n50_after_curation', 0))
    )

    # Convert all manual edit fields to safe integers
    jira_dict['manual_breaks'] = int(jira_dict.get('manual_breaks') or 0)
    jira_dict['manual_joins'] = int(jira_dict.get('manual_joins') or 0)
    jira_dict['manual_haplotig_removals'] = int(jira_dict.get('manual_haplotig_removals') or 0)
    jira_dict['manual_breaks_and_joins'] = jira_dict['manual_breaks'] + jira_dict['manual_joins']

    # Format edit strings for use in the Jinja template
    def format_edit(n, label):
        return f"{text_num(n)} {label}{'s' if n > 1 else ''}" if n > 0 else ''

    jira_dict['breaks_text'] = format_edit(jira_dict['manual_breaks'], 'break')
    jira_dict['joins_text'] = format_edit(jira_dict['manual_joins'], 'join')
    haplotig_n = jira_dict.get('manual_haplotig_removals', 0)
    jira_dict['removals_text'] = (
        f"removal of {text_num(haplotig_n)} haplotypic duplication{'s' if haplotig_n > 1 else ''}"
        if haplotig_n > 0 else ''
    )


    jira_dict['scaffold_length_change'] = get_change_direction_and_value(jira_dict['scaffold_total_length_change'])
    jira_dict['scaffold_count_change'] = get_change_direction_and_value(jira_dict['scaffold_count_change'])
    jira_dict['scaffold_N50_change'] = get_change_direction_and_value(jira_dict['scaffold_N50_change'])


    if 'autosomes' in jira_dict:
        try:
            jira_dict['autosomes'] = int(float(jira_dict['autosomes']))
        except (ValueError, TypeError):
            jira_dict['autosomes'] = 0

    if 'chromosome_result' in jira_dict:
        chromosome_lines = jira_dict['chromosome_result'].split('\n')
        for line in chromosome_lines:
            assigned_to_chr_match = re.match(r'Chr length (\S+) \%', line)
            if assigned_to_chr_match:
                jira_dict['jira_perc_assem'] = float(assigned_to_chr_match.group(1))

    if 'manual_haplotig_removals' in jira_dict:
        try:
            jira_dict['manual_haplotig_removals'] = int(float(jira_dict['manual_haplotig_removals']))
        except (ValueError, TypeError):
            jira_dict['manual_haplotig_removals'] = 0

    jira_dict.pop('assembly_statistics', None)
    jira_dict.pop('gfastats', None)

    attachments = response_data['fields'].get('attachment', [])
    yaml_attachment = next(
        (
            attachment
            for attachment in attachments
            if attachment['filename'].endswith(('.yaml', '.yml'))
        ),
        None,
    )

    if yaml_attachment:
        yaml_url = yaml_attachment['content']
        try:
            yaml_response = _jira_get(yaml_url, auth=auth)
        except requests.exceptions.RequestException as exc:
            print(f"Failed to download YAML attachment for {jira_ticket_id}: {exc}")
        else:
            yaml_versions = parse_yaml_attachment(yaml_response.text)
            jira_dict.update(yaml_versions)
    else:
        local_yaml = get_yaml_for_ticket(jira_ticket_id, auth)
        if local_yaml:
            with open(local_yaml) as fh:
                yaml_versions = parse_yaml_attachment(fh.read())
            jira_dict.update(yaml_versions)

    return jira_dict


def download_jira_attachment(jira_ticket_id, directory):
    """Find a .yaml attachment on the JIRA issue and download it."""
    jira_base_url = _jira_base_url()
    if not jira_base_url:
        print("JIRA is not configured; skipping attachment download.")
        return None

    url = f"{jira_base_url}/rest/api/2/issue/{jira_ticket_id}?fields=attachment"

    try:
        auth = get_auth()
    except Exception as exc:
        print(f"JIRA authentication unavailable: {exc}")
        return None

    response = _jira_get(url, auth=auth)
    issue_data = response.json()
    attachments = issue_data['fields'].get('attachment', [])

    for attachment in attachments:
        fn = attachment['filename']
        if fn.lower().endswith(('.yaml', '.yml')):
            download_url = attachment['content']
            local_path = os.path.join(directory, fn)
            print(f"[info] Downloading JIRA attachment → {local_path}")
            # delegate the actual GET + write to our helper:
            return download_jira_attachment_http(download_url, local_path, auth)

    print("[warn] No YAML attachment found on JIRA issue")
    return None



def parse_yaml_attachment(yaml_content):
    """Parse the YAML content and extract software versions."""
    versions = {
        'hifiasm_version': None,
        'mitohifi_version': None,
        'yahs_version': None,
        'purge_dups_version': None,
        'mbg_version': None,
        'oatk_version': None,
    }

    try:
        parsed_yaml = yaml.safe_load(yaml_content)
        if 'pipeline' in parsed_yaml:
            for entry in parsed_yaml['pipeline']:
                # Update the regex to handle software names with/without spaces before the version
                match = re.match(r"(\w+)\s*\(version\s+([\w\.\-]+)\)", entry)
                if match:
                    software, version = match.groups()
                    key = f"{software.lower()}_version"
                    if key in versions:
                        versions[key] = version
                else:
                    # If only software name is mentioned without version
                    key = f"{entry.lower()}_version"
                    if key in versions:
                        versions[key] = None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}")

    return versions




def main():
    jira_ticket_id = "RC-1832"
    fetch_custom_fields(jira_ticket_id)


if __name__ == "__main__":
    main()
