import time
import os
import urllib3
from urllib.parse import urlencode
from lxml import etree as ET
from lxml.etree import _Element
from loguru import logger as log
import sys
from datetime import datetime
import click

log.remove(0)
log.add(sys.stderr, format="{time} {level} {message}", filter="flexquery", level="INFO")


# IB Flex Web Service API Configuration
API_VERSION = "3"
INITIAL_WAIT = 5
RETRY = 7
RETRY_INCREMENT = 10

# Official IB Flex Web Service endpoints
# https://www.interactivebrokers.com/campus/ibkr-api-page/flex-web-service/
BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
SEND_REQUEST_ENDPOINT = f"{BASE_URL}/SendRequest"
GET_STATEMENT_ENDPOINT = f"{BASE_URL}/GetStatement"

# HTTP client with required User-Agent header
http = urllib3.PoolManager(
    headers={"User-Agent": "flexquery-cli/0.1.2 (Python/urllib3)"}
)


def _detect_format(data: bytes) -> str:
    """
    Detect report format from content for filename generation.
    
    Args:
        data: Raw bytes of the report content
    
    Returns:
        Format string: 'xml', 'html', 'csv', or 'unknown'
    """
    try:
        parsed_xml = ET.fromstring(data)
        if parsed_xml[0].tag == "FlexStatements":
            return "xml"
    except ET.ParseError:
        pass
    
    content_start = data[:100].decode('utf-8', errors='ignore').strip()
    if content_start.startswith('<!DOCTYPE') or content_start.startswith('<html'):
        return "html"
    elif ',' in content_start or ';' in content_start:
        return "csv"
    else:
        return "unknown"


def make_request(token: str, report_number: str) -> _Element:
    """
    Request IB to generate a FlexQuery report.
    
    Args:
        token: IB FlexQuery authentication token
        report_number: FlexQuery report number
    
    Returns:
        XML response element containing status and reference code
    """
    url_values = urlencode({"t": token, "q": report_number, "v": API_VERSION})
    full_url = f"{SEND_REQUEST_ENDPOINT}?{url_values}"

    try:
        response = http.request("GET", full_url)
        root: _Element = ET.fromstring(response.data)

        status = root.findtext("Status")
        log.debug(f"Request status: {status}")

        if status == "Success":
            return root
        else:
            error_code = root.findtext("ErrorCode")
            error_message = root.findtext("ErrorMessage")
            raise ValueError(f"Request rejected - Code: {error_code}, Message: {error_message}")
    except Exception as e:
        raise RuntimeError(f"Failed to make request: {e}")


def download_report(token: str, report_number: str, output_dir: str) -> str:
    """
    Download FlexQuery report from IB.
    
    Requests report generation, polls until ready, downloads, detects format,
    and saves to disk with appropriate file extension.
    
    Args:
        token: IB FlexQuery authentication token
        report_number: FlexQuery report number
        output_dir: Directory to save the downloaded report
    
    Returns:
        Path to the downloaded file
    """
    # Request report generation
    reply = make_request(token, report_number)

    reference_code = reply.findtext("ReferenceCode")
    if not reference_code:
        raise ValueError("Request failed - missing reference code")

    # Poll until report is ready
    url_values = urlencode({"q": reference_code, "t": token, "v": API_VERSION})
    full_url = f"{GET_STATEMENT_ENDPOINT}?{url_values}"

    report_data = None
    for retry in range(RETRY):
        wait_time = retry * RETRY_INCREMENT + INITIAL_WAIT
        log.info(f"Waiting {wait_time} seconds before fetching report (attempt {retry + 1}/{RETRY}).")
        time.sleep(wait_time)

        response = http.request("GET", full_url)
        
        if response.data and len(response.data) > 0:
            log.debug("Report download successful.")
            report_data = response.data
            break
        else:
            log.warning("Report not yet ready. Retrying...")
            continue

    if not report_data:
        raise TimeoutError("All report request retries failed")
    
    # Detect format and prepare filename
    actual_format = _detect_format(report_data)
    log.debug(f"Auto-detected format: {actual_format.upper()}")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filename = f"{output_dir}/{report_number}_{datetime.now().strftime('%Y%m%d')}_statement.{actual_format}"
    
    # Save file
    if actual_format == "xml":
        tree = ET.ElementTree(ET.fromstring(report_data))
        with open(filename, "wb") as file:
            tree.write(file)
    else:
        with open(filename, "wb") as file:
            file.write(report_data)
    
    log.info(f"{actual_format.upper()} report saved to {filename}")
    
    return filename


@click.command(context_settings={"auto_envvar_prefix": "FLEXQUERY"})
@click.argument("report_number", type=str)
@click.option(
    "-t",
    "--token",
    type=str,
    help="IB FlexQuery token for authentication",
    prompt=True,
    show_default=True,
    show_envvar=True,
    required=True,
)
@click.option(
    "-o",
    "--output-dir",
    type=str,
    default="reports",
    help="Output directory for downloaded reports",
    show_default=True,
    show_envvar=True,
)
def main(report_number, token, output_dir):
    """
    Download Interactive Brokers FlexQuery reports.
    
    The format (XML/CSV/HTML) is auto-detected based on your Flex Query 
    configuration in IB Client Portal.
    
    REPORT_NUMBER: Your IB FlexQuery report number
    
    Examples:
    
    \b
    # Download report (format auto-detected)
    flexquery 123456 -t YOUR_TOKEN
    
    \b
    # Download to custom directory
    flexquery 123456 -t YOUR_TOKEN -o ~/Downloads/
    """
    if not token:
        raise EnvironmentError("FLEXQUERY_TOKEN environment variable is not set")
    
    output_dir = os.path.expanduser(output_dir)

    log.info(f"Downloading report for query {report_number}")
    log.debug(f"Output directory: {output_dir}")
    
    downloaded_file = download_report(token, report_number, output_dir=output_dir)
    
    log.info(f"✓ Download complete: {downloaded_file}")


if __name__ == "__main__":
    main()
