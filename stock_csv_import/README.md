# Stock Import from CSV/XLSX

## Description

Odoo 19 Community module to import stock quantities from CSV or XLSX files.

### Key Features

- ✅ Batch processing optimized for 4000+ products
- ✅ Flexible column name detection (SKU, reference, quantity, etc.)
- ✅ Support for CSV and XLSX files
- ✅ Detailed import log with error reporting
- ✅ Safe transactions with exception handling
- ✅ Stock quantity updates for default warehouse

## Requirements

- Odoo 19 Community
- Base module: `stock`
- Python library: `openpyxl`

## Installation

1. Install the module.
2. Install dependencies: `pip install -r requirements.txt`

## Use

1. Go to **Inventory > Operations > Import Stock from CSV/XLSX**
2. Select CSV or XLSX file
3. Click "Import"

### File Format

- **SKU Column**: `sku`, `default_code`, `internal_reference`, or `ref`
- **Quantity Column**: `quantity`, `qty`, or `stock`

## Author

David Carreres Gómez

## License

AGPL-3
