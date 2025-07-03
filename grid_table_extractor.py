import pdfplumber
import pandas as pd
import json
import argparse
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

# --- Logging Setup ---
logger = logging.getLogger('GridTableExtractor')
logger.setLevel(logging.INFO)
# Ensure handlers are cleared to prevent duplicate logs if run multiple times
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
# --- End Logging Setup ---

class GridTableExtractor:
    """
    Extracts structured tables from PDF documents, specifically designed for
    tables with visible grid lines. Leverages pdfplumber for extraction
    and pandas for data structuring and basic cleaning.
    """

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        if self.debug_mode:
            logger.setLevel(logging.DEBUG)
        logger.info("GridTableExtractor initialized.")

    def extract_tables_from_pdf(self, pdf_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Extracts all grid-aligned tables from a given PDF file.
        
        Args:
            pdf_path: Path to the input PDF file.
            
        Returns:
            A list of dictionaries, where each dictionary represents a table
            and contains its data as a list of lists, and metadata.
            Returns an empty list if no tables are found or an error occurs.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return []

        extracted_tables_data = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"Opened PDF: {pdf_path} with {len(pdf.pages)} pages.")
                for page_num, page in enumerate(pdf.pages):
                    logger.debug(f"Processing page {page_num + 1}...")
                    
                    # Use pdfplumber's default table detection, which is good for grid-aligned tables
                    # You can also specify custom table settings here for finer control
                    # For example: table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}
                    tables = page.find_tables()
                    
                    if tables:
                        logger.info(f"Found {len(tables)} table(s) on page {page_num + 1}.")
                        for table_idx, table in enumerate(tables):
                            logger.debug(f"Extracting data for Table {table_idx + 1} on page {page_num + 1}...")
                            
                            # table.extract() returns a list of lists, representing rows and cells
                            raw_table_data = table.extract()
                            
                            # Process with pandas for structuring and basic cleaning
                            if raw_table_data and len(raw_table_data) > 0:
                                # First row is usually header, so set it as header
                                df = pd.DataFrame(raw_table_data[1:], columns=raw_table_data[0])
                                
                                # Basic cleaning: strip whitespace from all cells
                                df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
                                
                                # Attempt to infer better data types
                                # This is where pandas's "excel-like logic" comes in
                                df = df.infer_objects() 
                                
                                # Optional: further refine types, e.g., convert percentages strings to float
                                for col in df.columns:
                                    if df[col].dtype == 'object': # If it's still an object (string) type
                                        try:
                                            # Try to convert to numeric, handling common delimiters and percentages
                                            df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '').astype(float)
                                        except ValueError:
                                            pass # Keep as string if not convertible
                                
                                extracted_tables_data.append({
                                    "page_number": page_num + 1,
                                    "table_index_on_page": table_idx + 1,
                                    "bbox": table.bbox, # Bounding box (x0, y0, x1, y1)
                                    "data": df.values.tolist(), # Data as list of lists
                                    "headers": df.columns.tolist(), # Column headers
                                    "pandas_inferred_types": {col: str(df[col].dtype) for col in df.columns},
                                    "markdown_representation": df.to_markdown(index=False), # Markdown for LLM input
                                    "raw_csv_representation": df.to_csv(index=False) # CSV string
                                })
                                logger.info(f"Table {table_idx + 1} on page {page_num + 1} extracted and processed.")
                            else:
                                logger.warning(f"Table {table_idx + 1} on page {page_num + 1} found but no data extracted.")
                    else:
                        logger.debug(f"No tables found on page {page_num + 1}.")
            
            logger.info(f"Finished processing PDF: {pdf_path}. Total tables extracted: {len(extracted_tables_data)}")
            
        except FileNotFoundError:
            logger.error(f"Error: PDF file not found at {pdf_path}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during PDF table extraction for {pdf_path}: {e}")
        
        return extracted_tables_data

def main():
    parser = argparse.ArgumentParser(description='Extract grid-aligned tables from PDF.')
    parser.add_argument('--input', type=str, required=True,
                        help='Path to the input PDF file.')
    parser.add_argument('--output', type=str,
                        help='Optional: Path to output JSON file. If not provided, prints to console.')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging.')

    args = parser.parse_args()

    extractor = GridTableExtractor(debug_mode=args.debug)
    
    # Example usage for your paper1.pdf
    # The output_v3/session_ID/paper1.pdf path is what controller_v3 will pass as --input
    # So we assume the input PDF is already in the session directory.
    
    extracted_tables = extractor.extract_tables_from_pdf(args.input)

    if extracted_tables:
        if args.output:
            try:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(extracted_tables, f, indent=2, ensure_ascii=False)
                logger.info(f"Extracted tables saved to: {output_path}")
            except Exception as e:
                logger.error(f"Failed to save output to {output_path}: {e}")
        else:
            logger.info("--- Extracted Tables (JSON Output) ---")
            logger.info(json.dumps(extracted_tables, indent=2, ensure_ascii=False))
            logger.info("--- End Extracted Tables ---")
    else:
        logger.warning("No tables extracted or an error occurred during extraction.")

if __name__ == "__main__":
    main()