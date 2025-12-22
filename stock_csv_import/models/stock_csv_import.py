# Done by David Carreres Gomez
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import csv
import io
import base64
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class StockCsvImport(models.TransientModel):
    _name = 'stock.csv.import'
    _description = 'Stock Import from CSV/XLSX'

    file_data = fields.Binary(string='CSV/XLSX File', required=True, attachment=True)
    filename = fields.Char(string='Filename')
    import_date = fields.Datetime(string='Import Date', default=fields.Datetime.now, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('error', 'Error')
    ], default='draft', readonly=True)
    log_message = fields.Text(string='Import Log', readonly=True)
    imported_count = fields.Integer(string='Imported Records', readonly=True, default=0)
    error_count = fields.Integer(string='Error Records', readonly=True, default=0)

    def _detect_file_type(self):
        """Detect if file is CSV or XLSX based on filename"""
        self.ensure_one()
        if not self.filename:
            raise ValidationError(_("No filename specified."))
        
        filename_lower = self.filename.lower()
        if filename_lower.endswith('.csv'):
            return 'csv'
        elif filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls'):
            return 'xlsx'
        else:
            raise ValidationError(_("Unsupported file format. Use CSV or XLSX."))

    def _read_xlsx_file(self, file_content):
        """Read XLSX file and convert to list of dictionaries"""
        try:
            import openpyxl
        except ImportError:
            raise UserError(_("'openpyxl' library not installed. Install it with: pip install openpyxl"))
        
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
            sheet = workbook.active
            
            # Get headers from first row
            headers = []
            for cell in sheet[1]:
                headers.append(str(cell.value).strip() if cell.value else '')
            
            if not headers or not any(headers):
                raise ValidationError(_("The XLSX file is empty or has no headers."))
            
            # Read data rows
            data_rows = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not any(row):  # Skip empty rows
                    continue
                row_dict = {}
                for idx, value in enumerate(row):
                    if idx < len(headers):
                        row_dict[headers[idx]] = str(value).strip() if value is not None else ''
                data_rows.append(row_dict)
            
            workbook.close()
            return headers, data_rows
            
        except Exception as e:
            raise ValidationError(_("Error reading XLSX file: %s") % str(e))

    def _read_csv_file(self, file_content):
        """Read CSV file and convert to list of dictionaries"""
        try:
            # Try to detect delimiter
            sample = file_content.decode('utf-8')[:1024]
            try:
                dialect = csv.Sniffer().sniff(sample)
            except:
                dialect = csv.excel()
            
            reader = csv.DictReader(io.StringIO(file_content.decode('utf-8')), dialect=dialect)
            
            if not reader.fieldnames:
                raise ValidationError(_("The CSV file is empty or corrupt."))
            
            headers = [h.strip() for h in reader.fieldnames]
            data_rows = list(reader)
            
            return headers, data_rows
            
        except UnicodeDecodeError:
            # Try with latin-1 encoding
            try:
                reader = csv.DictReader(io.StringIO(file_content.decode('latin-1')))
                headers = [h.strip() for h in reader.fieldnames]
                data_rows = list(reader)
                return headers, data_rows
            except Exception as e:
                raise ValidationError(_("CSV file encoding error: %s") % str(e))
        except Exception as e:
            raise ValidationError(_("Error processing CSV: %s") % str(e))

    def _validate_and_find_columns(self, headers):
        """
        Validate that required columns exist and return their names.
        Accepts various column name variations.
        """
        # Normalize headers (case-insensitive)
        normalized_headers = {h.lower().strip(): h for h in headers}
        
        # Find SKU column
        sku_column = None
        for variant in ['sku', 'default_code', 'internal_reference', 'reference', 'referencia interna']:
            if variant in normalized_headers:
                sku_column = normalized_headers[variant]
                break
        
        # Find quantity column
        qty_column = None
        for variant in ['quantity', 'stock_quantity', 'qty', 'stock_qty', 'cantidad', 'cantidad disponible']:
            if variant in normalized_headers:
                qty_column = normalized_headers[variant]
                break
        
        if not sku_column:
            raise ValidationError(
                _("SKU column not found. Use: 'sku', 'default_code', 'internal_reference', 'reference' or 'referencia interna'")
            )
        if not qty_column:
            raise ValidationError(
                _("Quantity column not found. Use: 'quantity', 'stock_quantity', 'qty', 'stock_qty' or 'cantidad'")
            )
        
        return sku_column, qty_column

    def import_stock_from_csv(self):
        """
        Main import method - supports both CSV and XLSX files.
        Processes stock updates with batch optimization.
        """
        self.ensure_one()
        
        try:
            self.write({'state': 'processing'})
            
            # Decode file
            if not self.file_data:
                raise UserError(_("No file selected."))
            
            file_content = base64.b64decode(self.file_data)
            file_type = self._detect_file_type()
            
            # Read file based on type
            if file_type == 'xlsx':
                headers, data_rows = self._read_xlsx_file(file_content)
            else:
                headers, data_rows = self._read_csv_file(file_content)
            
            # Validate and find columns
            sku_column, qty_column = self._validate_and_find_columns(headers)
            
            # Process data in batches
            batch_size = 500
            batch_data = []
            imported = 0
            errors = 0
            error_details = []
            
            Product = self.env['product.product'].sudo()
            Quant = self.env['stock.quant'].sudo()
            
            _logger.info(f"Starting import of {len(data_rows)} rows from {file_type.upper()} file")
            
            # Process rows
            for row_num, row in enumerate(data_rows, start=2):  # Start at 2 (header is row 1)
                try:
                    sku = row.get(sku_column, '').strip()
                    quantity_str = row.get(qty_column, '0').strip()
                    
                    # Basic validations
                    if not sku:
                        errors += 1
                        error_details.append(_("Row %s: Empty SKU") % row_num)
                        continue
                    
                    try:
                        quantity = float(quantity_str.replace(',', '.'))
                    except (ValueError, AttributeError):
                        errors += 1
                        error_details.append(_("Row %s: Invalid quantity '%s' for SKU '%s'") % (row_num, quantity_str, sku))
                        continue
                    
                    if quantity < 0:
                        errors += 1
                        error_details.append(_("Row %s: Negative quantity for SKU '%s'") % (row_num, sku))
                        continue
                    
                    # Add to batch
                    batch_data.append({
                        'sku': sku,
                        'quantity': quantity,
                        'row': row_num
                    })
                    
                    # Process batch when it reaches size
                    if len(batch_data) >= batch_size:
                        imported_batch, errors_batch, error_batch_details = self._process_batch(
                            batch_data, Product, Quant
                        )
                        imported += imported_batch
                        errors += errors_batch
                        error_details.extend(error_batch_details)
                        batch_data = []
                
                except Exception as e:
                    errors += 1
                    error_details.append(_("Row %s: Unexpected error - %s") % (row_num, str(e)))
                    continue
            
            # Process last batch
            if batch_data:
                imported_batch, errors_batch, error_batch_details = self._process_batch(
                    batch_data, Product, Quant
                )
                imported += imported_batch
                errors += errors_batch
                error_details.extend(error_batch_details)
            
            # Generate log message
            log_msg = _("✓ Import completed: %s products updated, %s errors\n") % (imported, errors)
            log_msg += _("File: %s\n") % self.filename
            log_msg += _("Type: %s\n") % file_type.upper()
            log_msg += _("Total rows processed: %s\n") % len(data_rows)
            
            if error_details:
                log_msg += _("\n=== ERRORS FOUND ===\n")
                for error in error_details[:50]:  # Show first 50 errors
                    log_msg += f"  • {error}\n"
                if len(error_details) > 50:
                    log_msg += _("\n  ... and %s more errors\n") % (len(error_details) - 50)
            
            self.write({
                'state': 'done',
                'imported_count': imported,
                'error_count': errors,
                'log_message': log_msg
            })
            
            _logger.info(f"Import completed: {imported} imported, {errors} errors")
            
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': _("Import completed successfully!"),
                    'type': 'rainbow_man',
                },
                'type': 'ir.actions.act_window',
                'res_model': 'stock.csv.import',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
            
        except Exception as e:
            error_msg = _("❌ Critical error during import:\n%s") % str(e)
            _logger.error(error_msg, exc_info=True)
            self.write({
                'state': 'error',
                'log_message': error_msg
            })
            raise UserError(error_msg)

    def _process_batch(self, batch_data, Product, Quant):
        """
        Process a batch of products optimized for 4000+ items.
        Uses efficient SQL searches and batch updates.
        """
        imported = 0
        errors = 0
        error_details = []
        
        try:
            # Extract SKUs from batch
            skus = [item['sku'] for item in batch_data]
            
            # Efficient bulk search
            products = Product.search([('default_code', 'in', skus)])
            product_map = {p.default_code: p for p in products}
            
            # Get default warehouse location
            warehouse = self.env['stock.warehouse'].search([], limit=1)
            if not warehouse:
                error_details.append(_("No warehouse configured in the system"))
                return 0, len(batch_data), error_details
            
            location = warehouse.lot_stock_id
            
            for item in batch_data:
                try:
                    sku = item['sku']
                    quantity = item['quantity']
                    row = item['row']
                    
                    if sku not in product_map:
                        errors += 1
                        error_details.append(_("Row %s: Product with SKU '%s' not found") % (row, sku))
                        continue
                    
                    product = product_map[sku]
                    
                    # Search or create quant
                    quant = Quant.search([
                        ('product_id', '=', product.id),
                        ('location_id', '=', location.id)
                    ], limit=1)
                    
                    if quant:
                        # Update existing quantity
                        quant.write({'quantity': quantity})
                    else:
                        # Create new quant
                        Quant.create({
                            'product_id': product.id,
                            'location_id': location.id,
                            'quantity': quantity,
                        })
                    
                    imported += 1
                
                except Exception as e:
                    errors += 1
                    error_details.append(_("Row %s: %s") % (item['row'], str(e)))
                    continue
            
            return imported, errors, error_details
        
        except Exception as e:
            error_details.append(_("Error processing batch: %s") % str(e))
            return 0, len(batch_data), error_details

    def action_reset(self):
        """Allow creating a new import after completing one."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.csv.import',
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
