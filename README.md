# FlexQuery CLI

A lightweight command-line tool for downloading Interactive Brokers (IB) FlexQuery reports with automatic format detection.

## Features

- **Simple Download**: Request and download FlexQuery reports with a single command
- **Format Auto-Detection**: Automatically detects XML, CSV, or HTML formats
- **Multiple Formats**: Download any format configured in your IB FlexQuery
- **Clean Architecture**: Pure download functionality with optional transformation plugins
- **Environment Variables**: Configure via environment variables for automation

## Requirements

- Python 3.7+
- Interactive Brokers FlexQuery token

## Installation

```bash
git clone https://github.com/cubinet-code/flexquery
cd flexquery
pip install .
```

## Quick Start

```bash
# Set your token (optional - can also use -t flag)
export FLEXQUERY_TOKEN="YOUR_IB_FLEX_TOKEN"

# Download a report (format auto-detected)
flexquery 123456

# Download to a specific directory
flexquery 123456 -o ~/Downloads
```

## Usage

### Command-Line Interface

```bash
flexquery --help
```

**Options:**

- `REPORT_NUMBER` - Your IB FlexQuery report number (required)
- `-t, --token TEXT` - IB FlexQuery authentication token [env: FLEXQUERY_TOKEN]
- `-o, --output-dir TEXT` - Output directory [env: FLEXQUERY_OUTPUT_DIR] [default: reports]

**Examples:**

```bash
# Download with token from environment variable
export FLEXQUERY_TOKEN="YOUR_TOKEN"
flexquery 123456

# Download with explicit token and custom directory
flexquery 123456 -t YOUR_TOKEN -o ~/Downloads

# Download multiple reports in a script
for query in 123456 789012; do
    flexquery $query -o ~/Downloads
done
```

## Transformation Plugins

The core `flexquery` tool handles downloading only. Optional transformation plugins are available for post-processing:

### XML Filtering Plugin (`transform_xml.py`)

Filter and display XML FlexQuery reports by date range.

```python
from flexquery.transform_xml import filter_transactions_by_date_range
from lxml import etree as ET
from datetime import datetime

tree = ET.parse("reports/123456_20251028_statement.xml")
filtered = filter_transactions_by_date_range(
    tree, "123456",
    datetime(2024, 1, 1),
    datetime(2024, 12, 31)
)
```

### Parqet CSV Converter Plugin (`transform_csv.py`)

Convert IB XML reports to Parqet-compatible CSV format.

```bash
# Convert XML to Parqet CSV
transform-csv reports/123456_20251028_statement.xml

# Specify output file
transform-csv statement.xml -o portfolio.csv
```

See `flexquery/PLUGINS.md` for complete plugin documentation.

## How It Works

1. **Request**: Sends generation request to IB Flex Web Service API
2. **Poll**: Waits for report to be ready (with retry logic)
3. **Download**: Fetches the generated report
4. **Detect**: Auto-detects format (XML/CSV/HTML) from content
5. **Save**: Saves with appropriate file extension

## Architecture

- **Core (`flexquery.py`)**: Pure download functionality (~224 lines)
- **Plugins**: Optional transformation modules
  - `transform_xml.py` - XML filtering and display
  - `transform_csv.py` - Parqet CSV conversion

## API Endpoints

Uses official IB Flex Web Service API v3:

- Base: `https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService`
- Documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/flex-web-service/

## Dependencies

- `lxml` - XML parsing
- `click` - CLI framework
- `urllib3` - HTTP client
- `loguru` - Logging
- `tabulate` - Table formatting (plugins only)

```bash
pip install -r requirements.txt
```

## Development

```bash
# Install with dev dependencies
pip install -r dev-requirements.txt

# Type checking
mypy flexquery

# Code style
flake8 flexquery
```

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please open issues or submit pull requests.
