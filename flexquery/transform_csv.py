"""
Interactive Brokers FlexQuery to Parqet CSV Converter Plugin

This plugin converts Interactive Brokers FlexQuery XML files to Parqet CSV format
for easy import into the Parqet portfolio tracking platform.

Parqet CSV Format Specification:
- Separator: semicolon (;)
- Required columns: date, type, tax, fee
- Optional columns: price, shares, identifier, wkn, currency, assetType, amount
- Date format: yyyy-MM-dd or dd.MM.yyyy
- Supported transaction types: Buy, Sell, Dividend, Interest, TransferIn, TransferOut
- Asset types: Security (stocks/ETFs), Crypto, Cash
"""

import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from lxml import etree as ET
from lxml.etree import _Element
from loguru import logger as log
import click

log.remove(0)  # remove the default handler configuration
log.add(sys.stderr, format="{time} {level} {message}", filter="transform_csv", level="INFO")


# Mapping of IB activity codes to Parqet transaction types
ACTIVITY_CODE_MAPPING = {
    "BUY": "Buy",
    "SELL": "Sell",
    "DIV": "Dividend",
    "CINT": "Interest",  # Credit Interest
    "DINT": "Interest",  # Debit Interest
    "DEP": "TransferIn",
    "WITH": "TransferOut",
}

# Mapping of IB asset categories to Parqet asset types
ASSET_TYPE_MAPPING = {
    "STK": "Security",  # Stocks and ETFs
    "CASH": "Cash",
    "BOND": "Security",
    "FUT": "Security",
    "OPT": "Security",
    "FOP": "Security",
    "WAR": "Security",
}


def parse_date(date_str: str) -> str:
    """
    Parse IB date format (YYYYMMDD or YYYYMMDD;HHMMSS) to Parqet format (yyyy-MM-dd).
    """
    if not date_str:
        return ""
    
    # Remove time component if present
    if ";" in date_str:
        date_str = date_str.split(";")[0]
    
    try:
        date_obj = datetime.strptime(date_str, "%Y%m%d")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError as e:
        log.warning(f"Failed to parse date '{date_str}': {e}")
        return ""


def extract_transactions_from_xml(xml_path: Path) -> List[Dict[str, str]]:
    """
    Extract transactions from IB FlexQuery XML and convert to Parqet CSV format.
    
    Strategy:
    1. Process OpenPositions first (authoritative for current holdings, includes transfers)
    2. Process StmtFunds for non-buy transactions (dividends, interest, fees, etc.)
    
    Returns a list of dictionaries, each representing a transaction row.
    """
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
    except Exception as e:
        log.error(f"Failed to parse XML file: {e}")
        raise
    
    transactions = []
    processed_transaction_ids = set()  # Track to avoid duplicates
    
    # STEP 1: Process OpenPositions - these are authoritative for current holdings
    open_positions = root.xpath(".//OpenPositions/OpenPosition[@levelOfDetail='LOT']")
    
    for position in open_positions:
        isin = position.get("isin", "")
        if not isin:
            continue
            
        # Extract position details
        shares = position.get("position", "0")
        cost_basis_price = position.get("costBasisPrice", "0")
        currency = position.get("currency", "EUR")
        open_date_time = position.get("openDateTime", "")
        
        # Parse the open date
        if open_date_time:
            # Format: YYYYMMDD;HHMMSS or YYYYMMDD
            date_str = open_date_time.split(";")[0] if ";" in open_date_time else open_date_time
            date = parse_date(date_str)
        else:
            # No openDateTime means this was likely transferred in
            # We'll need to use a different approach - skip for now as we'll get from StmtFunds if bought
            continue
        
        # Create a Buy transaction for this position
        transaction = {
            "date": date,
            "type": "Buy",
            "currency": currency,
            "identifier": isin,
            "shares": abs(float(shares)),
            "price": abs(float(cost_basis_price)),
            "tax": "0",
            "fee": "0",  # We don't have fee info in OpenPosition
            "assetType": "Security",
        }
        
        # Format numeric fields
        for key in ["shares", "price", "tax", "fee"]:
            if key in transaction and transaction[key] != "" and transaction[key] != 0:
                transaction[key] = str(transaction[key]).replace(".", ",")
            elif key in transaction:
                transaction[key] = "0"
        
        # Mark this position's transaction ID to avoid duplicates from StmtFunds
        orig_txn_id = position.get("originatingTransactionID", "")
        if orig_txn_id:
            processed_transaction_ids.add(orig_txn_id)
        
        transactions.append(transaction)
    
    # STEP 2: Process StatementOfFundsLine transactions
    stmt_funds = root.xpath(".//StmtFunds/StatementOfFundsLine")
    
    for line in stmt_funds:
        activity_code = line.get("activityCode", "")
        transaction_id = line.get("transactionID", "")
        
        # Skip if we already processed this transaction from OpenPositions
        if transaction_id and transaction_id in processed_transaction_ids:
            continue
        
        # Skip certain activity codes that are internal transfers or fees we might not want
        if activity_code in ["OFEE"]:  # Skip other fees, can be configured
            continue
        
        # Map activity code to Parqet transaction type
        parqet_type = ACTIVITY_CODE_MAPPING.get(activity_code)
        if not parqet_type:
            log.debug(f"Skipping unmapped activity code: {activity_code}")
            continue
        
        # Extract common fields
        date = parse_date(line.get("date", ""))
        currency = line.get("currency", "EUR")
        
        # Initialize transaction dictionary with required fields
        transaction = {
            "date": date,
            "type": parqet_type,
            "currency": currency,
            "tax": "",
            "fee": "",
        }
        
        # Extract asset-specific information
        asset_category = line.get("assetCategory", "")
        isin = line.get("isin", "")
        
        if asset_category and asset_category in ASSET_TYPE_MAPPING:
            transaction["assetType"] = ASSET_TYPE_MAPPING[asset_category]
        else:
            transaction["assetType"] = "Cash"
        
        # For security transactions (Buy/Sell) - but only if NOT already in OpenPositions
        if activity_code in ["BUY", "SELL"]:
            # Skip BUY transactions that we already got from OpenPositions
            if activity_code == "BUY" and transaction_id in processed_transaction_ids:
                continue
                
            transaction["identifier"] = isin
            transaction["shares"] = abs(float(line.get("tradeQuantity", "0")))
            transaction["price"] = abs(float(line.get("tradePrice", "0")))
            
            # Commission as fee
            commission = line.get("tradeCommission", "0")
            if commission:
                transaction["fee"] = abs(float(commission))
            
            # Tax
            tax = line.get("tradeTax", "0")
            if tax:
                transaction["tax"] = abs(float(tax))
        
        # For dividend transactions
        elif activity_code == "DIV":
            transaction["identifier"] = isin
            transaction["shares"] = ""
            transaction["price"] = ""
            
            # Amount from credit field
            credit = line.get("credit", "0")
            debit = line.get("debit", "0")
            if credit:
                transaction["amount"] = abs(float(credit))
            elif debit:
                transaction["amount"] = abs(float(debit))
        
        # For tax on dividends (separate line item in IB)
        elif activity_code == "FRTAX":
            # This is withholding tax, we could add it to the previous dividend
            # For now, skip as it's typically on a separate line
            continue
        
        # For pure cash transactions (deposits, withdrawals) - SKIP THESE
        # Parqet requires these to be imported separately with a cash holding ID
        # See: https://parqet.com/blog/csv (section "Import von Cash Transaktionen")
        elif activity_code in ["DEP", "WITH"]:
            log.debug(f"Skipping cash transaction {activity_code} - requires separate cash holding import")
            continue
        
        # For interest transactions (these CAN be imported with security-like format)
        elif activity_code in ["CINT", "DINT"]:
            transaction["identifier"] = ""
            transaction["shares"] = ""
            transaction["price"] = ""
            transaction["assetType"] = "Cash"
            
            # Amount
            credit = line.get("credit", "")
            debit = line.get("debit", "")
            
            if credit:
                transaction["amount"] = abs(float(credit))
            elif debit:
                transaction["amount"] = abs(float(debit))
        
        # Format numeric fields
        for key in ["shares", "price", "tax", "fee", "amount"]:
            if key in transaction and transaction[key] != "" and transaction[key] != 0:
                # Use comma as decimal separator for Parqet
                transaction[key] = str(transaction[key]).replace(".", ",")
            elif key in transaction and (transaction[key] == "" or transaction[key] == 0):
                transaction[key] = "0"
        
        transactions.append(transaction)
    
    log.info(f"Extracted {len(transactions)} transactions from {xml_path.name}")
    return transactions


def write_parqet_csv(transactions: List[Dict[str, str]], output_path: Path):
    """
    Write transactions to a Parqet-compatible CSV file.
    
    Important: Parqet has different column requirements for different transaction types:
    - Security transactions (Buy/Sell): date, price, shares, tax, fee, type, assetType, identifier, currency
    - Cash transactions (TransferIn/Out, Interest, Dividend): date, amount, tax, fee, type, assetType, identifier, currency
    """
    if not transactions:
        log.warning("No transactions to write")
        return
    
    # Separate security transactions (stocks + dividends) from cash transactions
    # According to Parqet docs:
    # - Main CSV: Buy, Sell, Dividend (securities with ISIN)
    # - Cash CSV: TransferIn, TransferOut, Interest (cash holding with holding ID)
    security_txns = []
    cash_txns = []
    
    for txn in transactions:
        txn_type = txn.get("type")
        if txn_type in ["Buy", "Sell", "Dividend"]:
            security_txns.append(txn)
        elif txn_type in ["TransferIn", "TransferOut", "Interest"]:
            cash_txns.append(txn)
    
    # Write security transactions (main CSV)
    if security_txns:
        fieldnames = [
            "date",
            "price",
            "shares",
            "amount",
            "tax",
            "fee",
            "type",
            "assetType",
            "identifier",
            "currency",
        ]
        
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=fieldnames,
                    delimiter=";",
                    extrasaction="ignore",
                )
                
                writer.writeheader()
                
                # Write each transaction with appropriate fields
                for transaction in security_txns:
                    # For Buy/Sell transactions, ensure amount is not set or is empty
                    if transaction.get("type") in ["Buy", "Sell"]:
                        transaction["amount"] = ""
                    # For dividend transactions, ensure price and shares are empty
                    elif transaction.get("type") == "Dividend":
                        transaction["price"] = ""
                        transaction["shares"] = ""
                    
                    writer.writerow(transaction)
            
            log.info(f"✓ Parqet CSV saved to {output_path}")
            log.info(f"  Security transactions: {len(security_txns)}")
        except Exception as e:
            log.error(f"Failed to write CSV file: {e}")
            raise
    
    # Write cash transactions (separate CSV)
    if cash_txns:
        cash_output_path = output_path.parent / (output_path.stem + "_cash.csv")
        
        # Cash transactions use a different format with 'holding' field
        # For now, we'll output with a placeholder HOLDING_ID that user must replace
        fieldnames_cash = [
            "date",
            "amount",
            "tax",
            "fee",
            "type",
            "holding",
        ]
        
        try:
            with open(cash_output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=fieldnames_cash,
                    delimiter=";",
                    extrasaction="ignore",
                )
                
                writer.writeheader()
                
                for transaction in cash_txns:
                    # Convert to cash format with holding placeholder
                    cash_txn = {
                        "date": transaction.get("date", ""),
                        "amount": transaction.get("amount", "0"),
                        "tax": transaction.get("tax", "0"),
                        "fee": transaction.get("fee", "0"),
                        "type": transaction.get("type", ""),
                        "holding": "HOLDING_ID",  # User must replace with actual cash holding ID
                    }
                    writer.writerow(cash_txn)
            
            log.info(f"✓ Cash transactions CSV saved to {cash_output_path}")
            log.info(f"  Cash/Interest transactions: {len(cash_txns)}")
            log.warning("⚠️  Please replace 'HOLDING_ID' in the cash CSV with your Parqet cash holding ID")
            log.info("  See: https://parqet.com/blog/csv (section 'Import von Cash Transaktionen')")
        except Exception as e:
            log.error(f"Failed to write cash CSV file: {e}")
            raise
    
    log.info(f"  Total transactions: {len(transactions)}")


@click.command()
@click.argument("xml_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output CSV file path. If not specified, uses the XML filename with .csv extension.",
)
@click.option(
    "--exclude-fees",
    is_flag=True,
    help="Exclude fee transactions (OFEE) from the output.",
)
def main(xml_file: Path, output: Optional[Path], exclude_fees: bool):
    """
    Convert Interactive Brokers FlexQuery XML to Parqet CSV format.
    
    Example:
        transform_csv history/123456_20250923_statement.xml
        
        transform_csv history/123456_20250923_statement.xml -o my_portfolio.csv
    """
    log.info(f"Processing {xml_file}")
    
    # Determine output path
    if output is None:
        output = xml_file.with_suffix(".csv")
    
    # Extract transactions
    transactions = extract_transactions_from_xml(xml_file)
    
    if not transactions:
        log.warning("No transactions found in the XML file")
        return
    
    # Write to CSV
    write_parqet_csv(transactions, output)
    
    log.info("✓ Conversion complete!")
    log.info(f"  You can now import {output.name} to Parqet")


if __name__ == "__main__":
    main()
