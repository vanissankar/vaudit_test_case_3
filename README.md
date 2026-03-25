# Universal Bank Statement Extractor (Universal Phaser)

A truly universal, layout-agnostic bank statement extraction engine capable of processing any PDF statement without hardcoded rules. The system uses dynamic table parsing and spatial Key-Value Pair (KVP) discovery to extract metadata and transaction data from diverse bank formats with high precision.

## Features
- **Truly Universal**: No bank-specific code or hardcoded regex needed for new formats.
- **Dynamic Table Parsing**: Automatically detects column headers and boundaries (midpoint-based zones).
- **Multi-line Header Support**: Corrects split-line headers (e.g., KVB).
- **Hybrid Metadata Extraction**: Combines high-reliability coordinate-aware keyword search with layout-agnostic KVP discovery.
- **Summary Precision**: Automatically identifies and filters "Balance Forward" rows to prevent double-counting in credit/debit totals.
- **Multi-threaded Support**: Includes both Sequential and Multi-threaded (ThreadPoolExecutor) implementations for benchmarking.

## Project Structure
- `engine/`: Core logic (parser, detector, exporter).
- `Sequential/`: Sequential processing implementation.
- `Threads/`: Multi-threaded processing implementation.

## Usage
1. Place your bank statement PDFs in `Sequential/input/` or `Threads/input/`.
2. Run the extractor:
   ```bash
   python Sequential/main.py
   ```
3. Find your results in `Sequential/output/json/` and `Sequential/output/excel/`.

## Dependencies
- `PyMuPDF (fitz)`
- `pandas`
- `openpyxl`
- `xlsxwriter`
