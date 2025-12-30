{
    'name': 'NEXUS: Stock Import from CSV/XLSX',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Import stock quantities from CSV/XLSX files',
    'description': """
Import stock quantities from CSV or XLSX files with batch processing optimized for 4000+ products.

Features:
- Batch processing optimized for 4000+ products
- Flexible column name detection (sku, default_code, quantity, etc.)
- Detailed import log with error reporting
- Support for both CSV and XLSX formats
- Safe transaction handling
    """,
    'author': 'David Carreres Gómez',
    'website': 'https://carreres.es',
    'support': 'david@carreres.es',
    'maintainer': 'David Carreres Gómez',
    'license': 'OPL-1',
    'price': 15.90,
    'currency': 'EUR',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_csv_import_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/icon.png', 'static/description/screenshot_1.png'],
    'external_dependencies': {
        'python': ['openpyxl'],
    },

}
