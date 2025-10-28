# FlexQuery Transformation Plugins

This directory contains optional transformation plugins for processing downloaded FlexQuery reports.

## Available Plugins

### `transform_xml.py` - XML Report Transformations

Functions for filtering and displaying XML FlexQuery reports.

**Functions:**

- `filter_transactions_by_date_range()` - Filter trades and cash transactions by date range
- `write_xml()` - Save filtered XML to file
- `print_transactions()` - Display transactions in formatted tables

**Example Usage:**

```python
from flexquery.transform_xml import filter_transactions_by_date_range, print_transactions
from lxml import etree as ET
from datetime import datetime

# Load downloaded XML report
tree = ET.parse("history/123456_20251028_statement.xml")

# Filter by date range
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 12, 31)
filtered_tree = filter_transactions_by_date_range(
    tree,
    "123456",
    start_date,
    end_date,
    exclude_deposits_withdrawals=True
)

# Display results
print_transactions(filtered_tree)
```

### `transform_csv.py` - Parqet CSV Converter

Convert Interactive Brokers FlexQuery XML reports to Parqet-compatible CSV format for portfolio tracking.

**Features:**

- Converts IB XML FlexQuery to Parqet CSV format (semicolon-delimited)
- Supports Buy, Sell, Dividend, Interest transactions
- Separates security transactions from cash transactions
- Handles ISIN identifiers, fees, taxes
- Uses comma as decimal separator for Parqet

**CLI Usage:**

```bash
# Convert XML to Parqet CSV
python -m flexquery.transform_csv history/123456_20251028_statement.xml

# Specify custom output file
python -m flexquery.transform_csv statement.xml -o portfolio.csv
```

**Programmatic Usage:**

```python
from flexquery.transform_csv import extract_transactions_from_xml, write_parqet_csv
from pathlib import Path

# Extract transactions
xml_path = Path("history/123456_20251028_statement.xml")
transactions = extract_transactions_from_xml(xml_path)

# Write to Parqet CSV
output_path = Path("parqet_import.csv")
write_parqet_csv(transactions, output_path)
```

**Output:**

- Main CSV file with security transactions (Buy/Sell/Dividend)
- Separate `_cash.csv` file for cash transactions (requires manual holding ID)

## Future Plugin System

The transformation plugins are designed to be:

1. **Optional** - Only import if needed
2. **Modular** - Each plugin is self-contained
3. **Composable** - Chain multiple transformations
4. **Extensible** - Easy to add new plugins

### Planned Plugins

- `transform_parqet.py` - Convert to Parqet CSV format (integration with existing pqcsv module)
- `transform_portfolio_performance.py` - Format for Portfolio Performance import
- `transform_csv.py` - CSV report transformations
- Custom user plugins via plugin discovery

## Design Principles

- **Separation of Concerns**: Download logic stays in `flexquery.py`, transformations are plugins
- **No Dependencies in Core**: Core download module has minimal dependencies
- **Plugin Discovery**: Future support for dynamic plugin loading
- **CLI Integration**: Transform plugins can be invoked via CLI flags when implemented
