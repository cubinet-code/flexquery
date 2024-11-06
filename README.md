
# FlexQuery CLI

A command-line tool for requesting, downloading, and processing Interactive Brokers (IB) Flex queries in XML format. This tool helps filter and display transaction data within a specified date range.

This was written for simplifying the xml import to [Portfolio Performance](https://forum.portfolio-performance.info/t/interactive-brokers/276), but can be used for any FlexQuery.

## Features

- Sends requests to IB to generate Flex queries based on your credentials.
- Downloads the generated XML report and saves it locally.
- Filters transactions (trades and cash transactions) by date range.
- Displays the filtered transactions in a formatted table on the console.

## Requirements

- Python 3.7+
- Access to an Interactive Brokers FlexQuery token

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/cubinet-code/flexquery
   cd flexquery
   ```

2. Install the package:
   ```bash
   pip install .
   ```

## Using as a CLI Utility

After installing, you can use the `flexquery` command directly from the command line.
You can get help by running `flexquery --help`.

### Command-Line Usage

```
> flexquery --help
Usage: flexquery [OPTIONS] REPORT_NUMBER

Options:
  -s, --start-date [%Y-%m-%d]  Start Date  [env var: FLEXQUERY_START_DATE;
                               default: 2024-10-31; required]
  -e, --end-date [%Y-%m-%d]    End Date  [env var: FLEXQUERY_END_DATE;
                               default: 2024-10-31; required]
  -t, --token TEXT             IB FlexQuery token for authentication  [env
                               var: FLEXQUERY_TOKEN; required]
  --help                       Show this message and exit.
```

**Example:**

```bash
flexquery 123456 --start-date 2024-01-01 --end-date 2024-12-31 --token YOUR_IB_FLEX_TOKEN
```

### Environment Variable Support

You can also set the token using the `FLEXQUERY_TOKEN` environment variable instead of passing it as a command-line argument:
Also the other parameters can be set via environment variables (see --help).

```bash
export FLEXQUERY_TOKEN="YOUR_IB_FLEX_TOKEN"
flexquery 123456 --start-date 2024-01-01 --end-date 2024-12-31
```

## How It Works

1. **Request Generation**: Sends a request to IB to generate the FlexQuery report.
2. **Download**: Downloads the generated XML report when it becomes available.
3. **Filtering**: Filters transactions based on the specified date range.
4. **Display**: Prints the filtered transactions in a tabular format.

## Code Overview

- **make_xml_request**: Sends a request to IB to generate the FlexQuery report.
- **get_xml**: Waits and retrieves the report once it’s ready.
- **download_xml**: Downloads and saves the XML report to the `history` directory.
- **filter_transactions_by_date_range**: Filters transactions within a specified date range.
- **print_transactions**: Displays the filtered transactions in a table format using `tabulate`.
- **write_xml**: Saves the XML data to a file.

## Dependencies

- `lxml`: For XML parsing and processing.
- `click`: For command-line argument parsing.
- `urllib3`: For HTTP requests.
- `tabulate`: For table formatting in the console.
- `loguru`: For enhanced logging.

Install dependencies using `requirements.txt`:

```bash
pip install -r requirements.txt
```

## License

This project is licensed under the MIT License.

## Contributing

Feel free to contribute by opening issues or submitting pull requests. 
