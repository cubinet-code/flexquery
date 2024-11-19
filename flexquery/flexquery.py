import time
import os
import urllib3
from urllib.parse import urlencode
from lxml import etree as ET
from lxml.etree import _ElementTree, _Element
from loguru import logger as log
import sys
from datetime import datetime
from datetime import date
from dateutil.relativedelta import relativedelta
import click
from tabulate import tabulate

log.remove(0)  # remove the default handler configuration
log.add(sys.stderr, format="{time} {level} {message}", filter="flexquery", level="DEBUG")


# Constants
REQUEST_VERSION = "3"
XML_VERSION = "3"
INITIAL_WAIT = 5  # Waiting time for first attempt
RETRY = 7  # Number of retries before aborting
RETRY_INCREMENT = 10  # Incremental wait time for each retry

# HTTP client setup
http = urllib3.PoolManager()


def make_xml_request(token: str, report_number: str, version: str) -> _Element:
    """Requests IB to generate the flex query file by sending a request with the token."""

    url_values = urlencode({"t": token, "q": report_number, "v": version})
    base_url = "https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest"
    full_url = f"{base_url}?{url_values}"

    try:
        response = http.request("GET", full_url)
        root: _Element = ET.fromstring(response.data)

        status = root.findtext("Status")
        log.debug(f"XML request status: {status}")

        if status == "Success":
            return root
        else:
            raise ValueError(f"ERROR: XML request was rejected: {status}")
    except Exception as e:
        raise RuntimeError(f"Failed to make XML request: {e}")


def get_xml(base_url: str, reference_code: str, token: str, version: str) -> _Element:
    """
    After the request is accepted, this function waits and fetches the file once it is ready for download.
    """
    xml_url_values = urlencode({"q": reference_code, "t": token, "v": version})
    xml_full_url = f"{base_url}?{xml_url_values}"

    for retry in range(RETRY):
        wait_time = retry * RETRY_INCREMENT + INITIAL_WAIT
        log.info(f"Waiting {wait_time} seconds before fetching XML.")
        time.sleep(wait_time)

        try:
            response = http.request("GET", xml_full_url)
            xml_report = ET.fromstring(response.data)

            if xml_report[0].tag == "FlexStatements":
                log.debug("XML download successful.")
                return xml_report
            elif xml_report.findtext("ErrorCode") == "1019":  # statement generation in process
                log.warning("XML is not yet ready. Retrying...")
            else:
                error_code = xml_report.findtext("ErrorCode")
                error_message = xml_report.findtext("ErrorMessage")
                raise ValueError(f"Error Code: {error_code}, Error Message: {error_message}")
        except Exception as e:
            log.error(f"Error fetching XML: {e}")

    raise TimeoutError("ERROR: All XML request retries failed.")


def download_xml(token: str, report_number: str):
    """
    Downloads the XML file after successful request and retrieval of the generated report.
    """
    xml_reply = make_xml_request(token, report_number, REQUEST_VERSION)

    url = xml_reply.findtext("Url")
    reference_code = xml_reply.findtext("ReferenceCode")
    if not url or not reference_code:
        raise ValueError("ERROR: XML request failed.")

    xml_result = get_xml(url, reference_code, token, XML_VERSION)
    tree = ET.ElementTree(xml_result)

    if not os.path.exists("history"):
        os.makedirs("history")
    write_xml(f"history/{datetime.now().strftime('%Y%m%d')}_statement.xml", tree)
    return tree


def filter_transactions_by_date_range(
    root: "_ElementTree[_Element]",
    start_date: datetime,
    end_date: datetime,
    exclude_deposits_withdrawals: bool = False,
):
    log.debug(f"Filtering transactions from {start_date.date()} to {end_date.date()}")
    flex_statement = root.find(".//FlexStatement")
    if flex_statement is None:
        raise ValueError("ERROR: FlexStatement node not found in the XML.")

    trades = flex_statement.find("Trades")
    if trades is not None:
        for trade in list(trades):
            trade_date_str = trade.get("tradeDate", "")
            if trade_date_str:
                trade_date = datetime.strptime(trade_date_str, "%Y%m%d")
                if not (start_date <= trade_date <= end_date):
                    trades.remove(trade)

    cash_transactions = flex_statement.find("CashTransactions")
    if cash_transactions is not None:
        for transaction in list(cash_transactions):
            transaction_date_str = transaction.get("dateTime", "")
            transaction_type = transaction.get("type", "")
            if transaction_date_str:
                if ";" in transaction_date_str:
                    transaction_date = datetime.strptime(transaction_date_str, "%Y%m%d;%H%M%S")
                else:
                    transaction_date = datetime.strptime(transaction_date_str, "%Y%m%d")

                # Apply date filtering
                if not (start_date <= transaction_date <= end_date):
                    cash_transactions.remove(transaction)
                    continue

                # Exclude Deposits/Withdrawals if specified
                if exclude_deposits_withdrawals and transaction_type == "Deposits/Withdrawals":
                    cash_transactions.remove(transaction)

    write_xml(f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}_statement.xml", root)
    return root


def write_xml(filename, root: "_ElementTree[_Element]"):
    with open(filename, "wb") as file:
        root.write(file)

    log.info(f"XML data saved to {filename}")


def print_transactions(root: _Element):
    """
    Prints the filtered trades and cash transactions from the XML in a table format.
    """
    # Extract and format trades for display
    trades = []
    for trade in root.xpath(".//Trades/Trade"):
        trades.append(
            {
                "Date": datetime.strptime(trade.get("tradeDate"), "%Y%m%d").strftime("%Y-%m-%d"),
                "Symbol": trade.get("symbol"),
                "Description": trade.get("description"),
                "Quantity": trade.get("quantity"),
                "Price": trade.get("tradePrice"),
                "Amount": trade.get("tradeMoney"),
                "Type": trade.get("buySell"),
                "Comm": trade.get("ibCommission"),
                "Taxes": trade.get("taxes"),
                "Total Cost": trade.get("cost") + " " + trade.get("currency"),
            }
        )

    # Extract and format cash transactions for display
    cash_transactions = []
    for transaction in root.xpath(".//CashTransactions/CashTransaction"):
        transaction_date_str = transaction.get("dateTime", "")
        if transaction_date_str:
            # Choose the format based on the presence of a time component
            if ";" in transaction_date_str:
                transaction_date = datetime.strptime(transaction_date_str, "%Y%m%d;%H%M%S")
            else:
                transaction_date = datetime.strptime(transaction_date_str, "%Y%m%d")

            cash_transactions.append(
                {
                    "Date": transaction_date.strftime("%Y-%m-%d"),
                    "Description": transaction.get("description"),
                    "Amount": transaction.get("amount"),
                    "Type": transaction.get("type"),
                }
            )

    # Display in table format
    if trades:
        print("\nFiltered Trades:")
        print(tabulate(trades, headers="keys", tablefmt="grid"))

    if cash_transactions:
        print("\nFiltered Cash Transactions:")
        print(tabulate(cash_transactions, headers="keys", tablefmt="grid"))


@click.command(context_settings={"auto_envvar_prefix": "FLEXQUERY"})
@click.argument("report_number", type=str)
@click.option(
    "-s",
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start Date",
    prompt=True,
    default=lambda: (date.today() - relativedelta(days=7)).strftime("%Y-%m-%d"),
    show_default=True,
    show_envvar=True,
    required=True,
)
@click.option(
    "-e",
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End Date",
    prompt=True,
    default=lambda: date.today().strftime("%Y-%m-%d"),
    show_default=True,
    show_envvar=True,
    required=True,
)
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
    "-x",
    "--exclude-deposits-withdrawals",
    is_flag=True,
    default=False,
    help="Exclude transactions of type 'Deposits/Withdrawals'",
)
def main(report_number, start_date, end_date, token, exclude_deposits_withdrawals):
    if not token:
        raise EnvironmentError("ERROR: FLEXQUERY_TOKEN environment variable is not set.")

    xml_content = download_xml(token, report_number)
    filtered_xml_content = filter_transactions_by_date_range(xml_content, start_date, end_date, exclude_deposits_withdrawals)
    print_transactions(filtered_xml_content)


if __name__ == "__main__":
    main()
