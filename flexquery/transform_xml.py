"""
XML Transformation Plugin for FlexQuery

This module contains transformation and filtering functions for XML FlexQuery reports.
These functions can be used as optional post-processing steps after downloading reports.

Future: This will be part of a plugin system for transformations.
"""

from lxml import etree as ET
from lxml.etree import _ElementTree, _Element
from loguru import logger as log
from datetime import datetime
from tabulate import tabulate
import sys

log.remove(0)
log.add(sys.stderr, format="{time} {level} {message}", filter="flexquery.transform_xml", level="DEBUG")


def filter_transactions_by_date_range(
    root: "_ElementTree[_Element]",
    report_number: str,
    start_date: datetime,
    end_date: datetime,
    exclude_deposits_withdrawals: bool = False,
):
    """
    Filter transactions in an XML FlexQuery report by date range.
    
    Args:
        root: ElementTree root of the XML report
        report_number: Query report number (for output filename)
        start_date: Start date for filtering
        end_date: End date for filtering
        exclude_deposits_withdrawals: Whether to exclude deposit/withdrawal transactions
    
    Returns:
        Filtered ElementTree root
    """
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

    write_xml(
        f"{report_number}_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}_statement.xml",
        root,
    )
    return root


def write_xml(filename: str, root: "_ElementTree[_Element]"):
    """
    Write XML ElementTree to file.
    
    Args:
        filename: Output filename
        root: ElementTree root to write
    """
    with open(filename, "wb") as file:
        root.write(file)

    log.info(f"XML data saved to {filename}")


def print_transactions(root: _Element):
    """
    Print filtered trades and cash transactions from the XML in a table format.
    
    Args:
        root: ElementTree root containing transaction data
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
