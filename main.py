import os
import sys
import time
import re
import fitz
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import tkinter as tk
from tkinter import filedialog

# Add engine to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from engine.parser import extract_transactions_universally, extract_transactions_from_text, clean_amount, extract_date, parse_date_obj
from engine.detector import extract_metadata, is_bank_statement_structure
from engine.exporter import export_to_excel
from engine.ai_validator import AIValidator

def get_ay_range(ay_str):
    """
    Converts AY format 'YYYY-YY' to a date range (April 1 of YYYY-1 to March 31 of YYYY).
    Example: AY 2024-25 -> April 1, 2023 to March 31, 2024.
    """
    try:
        parts = ay_str.split('-')
        start_year_str = parts[0].strip()
        if len(start_year_str) == 4:
            start_year = int(start_year_str)
        else:
            raise ValueError()
            
        # FY starts April 1 of start_year
        fy_start = datetime(start_year, 4, 1)
        # FY ends March 31 of next year
        fy_end = datetime(start_year + 1, 3, 31, 23, 59, 59)
        return fy_start, fy_end
    except Exception:
        raise ValueError("Invalid Financial Year format. Use YYYY-YY (e.g., 2024-25).")


def normalize_transaction_date(date_str, ay_range):
    if not date_str:
        return datetime(1900,1,1)

    parsed = parse_date_obj(date_str)
    if parsed.year != 1900:
        return parsed

    m = re.match(r"^\s*(\d{1,2})[/\-](\d{1,2})\s*$", date_str.strip())
    if m:
        dd = int(m.group(1)); mm = int(m.group(2))
        # Prefer AY window to resolve year
        for y in (ay_range[0].year, ay_range[1].year):
            try:
                cand = datetime(y, mm, dd)
            except ValueError:
                continue
            if ay_range[0] <= cand <= ay_range[1]:
                return cand
        # If not in AY, fallback to AY start year
        try:
            return datetime(ay_range[0].year, mm, dd)
        except ValueError:
            pass

    return parsed

def select_files():
    """Opens a GUI file dialog to select multiple PDF files."""
    root = tk.Tk()
    root.withdraw()
    # Bring the dialog to the front
    root.attributes("-topmost", True)
    
    files = filedialog.askopenfilenames(
        title="Select Bank Statement PDF(s)",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    
    root.destroy()
    return list(files)

def validate_and_process_pdf(filepath, ay_range):
    """
    Validates if the file is a bank statement and processes it.
    Returns (error_code, metadata, transactions)
    """
    filename = os.path.basename(filepath)

    if not os.path.exists(filepath):
        return f"FILE_NOT_FOUND", None, []

    if not filename.lower().endswith('.pdf'):
        return "UNSUPPORTED_FILE_TYPE", None, []

    try:
        with fitz.open(filepath) as doc:
            if len(doc) == 0:
                return "EMPTY_PDF", None, []

            first_page_words = doc[0].get_text_words()
            first_page_text = doc[0].get_text()
            metadata = extract_metadata(first_page_text, first_page_words)

            # Quick structural validation (expected for most statements)
            is_valid_structure = False
            for p_idx in range(min(3, len(doc))):
                p_words = doc[p_idx].get_text_words()
                if is_bank_statement_structure(p_words):
                    is_valid_structure = True
                    break

            # Metadata validity check (Bank Name/account number are key signals)
            is_valid_metadata = any(
                metadata.get(x) not in (None, "Not Found", "")
                for x in ["Bank Name", "Account Number", "Account Holder Name"]
            )

            # If structure is weak but metadata looks correct, continue.
            if not is_valid_structure and is_valid_metadata:
                # Some statements have unusual layout, still valid from metadata
                is_valid_structure = True

            # If both structure and metadata are weak, apply brute-force fallback methods
            if not is_valid_structure and not is_valid_metadata:
                temp_txns = extract_transactions_universally(first_page_words)
                if len(temp_txns) >= 2:
                    is_valid_structure = True
                    metadata["Bank Name"] = "Generic Bank (Brute-Force Detected)"
                else:
                    ai_v = AIValidator()
                    if ai_v.client:
                        ai_result = ai_v.verify_document(filename, first_page_text)
                        if ai_result.get("is_statement"):
                            metadata["Bank Name"] = ai_result.get("bank_name", "Generic AI Detected")
                            metadata["Account Number"] = ai_result.get("account_number", "Unknown")
                            is_valid_metadata = True
                            is_valid_structure = True
                        else:
                            return "INVALID_BANK_STATEMENT", None, []
                    else:
                        return "INVALID_BANK_STATEMENT", None, []

            # If structure matched but metadata didn't, assign generic name for reporting.
            if is_valid_structure and not is_valid_metadata:
                metadata["Bank Name"] = metadata.get("Bank Name", "Generic Bank (Structure Detected)")
                # Layer 3: Brute-Force Fallback (If it has transactions, it IS a statement)
                temp_txns = extract_transactions_universally(first_page_words)
                if len(temp_txns) >= 2:
                    is_valid_structure = True
                    metadata["Bank Name"] = "Generic Bank (Brute-Force Detected)"
                else:
                    # Layer 4: Top-Grade AI Check (Optional - if API Key is set)
                    ai_v = AIValidator()
                    if ai_v.client:
                        ai_result = ai_v.verify_document(filename, first_page_text)
                        if ai_result.get("is_statement"):
                            metadata["Bank Name"] = ai_result.get("bank_name", "Generic AI Detected")
                            metadata["Account Number"] = ai_result.get("account_number", "Unknown")
                        else:
                            return "INVALID_BANK_STATEMENT", None, []
                    else:
                        return "INVALID_BANK_STATEMENT", None, []
            
            # If structure matched but metadata didn't, assign generic name
            if not is_valid_metadata and is_valid_structure:
                metadata["Bank Name"] = "Generic Bank (Structure Detected)"
            
            metadata["filename"] = filename
            metadata["page_count"] = len(doc)
            
            all_txns = []
            for i in range(len(doc)):
                page = doc[i]
                page_words = page.get_text_words()
                page_txns = extract_transactions_universally(page_words)

                # If page-level extraction has almost all empty descriptions, use text fallback.
                if page_txns:
                    empty_count = sum(1 for t in page_txns if not t[1].strip() and (t[2] > 0 or t[3] > 0))
                    if empty_count / len(page_txns) > 0.8:
                        fallback_txns = extract_transactions_from_text(page.get_text())
                        if fallback_txns:
                            page_txns = fallback_txns

                all_txns.extend(page_txns)

            if not all_txns:
                # Some valid statements may not expose structured transactions in text extraction.
                # For metadata-confirmed statements, continue with empty transactions.
                if not is_valid_metadata:
                    return "INVALID_BANK_STATEMENT", None, []

            # Filter by AY
            start_date, end_date = ay_range
            filtered_txns = []
            for t in all_txns:
                txn_date = normalize_transaction_date(t[0], ay_range)
                if start_date <= txn_date <= end_date:
                    filtered_txns.append(t)

            # Cross-page same-date description fill: if a date appears with non-empty description earlier,
            # propagate to later same-date rows with empty description.
            last_desc_by_date = {}
            for t in filtered_txns:
                date_key = t[0]
                desc = t[1].strip() if t[1] else ""
                if desc:
                    last_desc_by_date[date_key] = desc
                else:
                    if date_key in last_desc_by_date:
                        t[1] = last_desc_by_date[date_key]

            return None, metadata, filtered_txns
            
    except Exception as e:
        err_msg = str(e).lower()
        if "encrypted" in err_msg or "password" in err_msg:
            return "ENCRYPTED", None, []
        return f"ERROR: {str(e)}", None, []

def main():
    print("="*70)
    print("        UNIVERSAL BANK STATEMENT EXTRACTOR - TERMINAL EDITION")
    print("="*70)
    
    # 1. Financial Year Input
    while True:
        ay_input = input("\nEnter Financial Year (FY) (e.g., 2024-25): ").strip()
        try:
            ay_range = get_ay_range(ay_input)
            print(f"Validation: Target Period set to {ay_range[0].strftime('%d-%b-%Y')} to {ay_range[1].strftime('%d-%b-%Y')}")
            break
        except ValueError as e:
            print(f"Error: {e}")

    # 2. File Selection via Dialog
    print("\nOpening File Manager to select PDF files...")
    pdf_paths = select_files()
    
    if not pdf_paths:
        print("No files selected. Exiting.")
        return
        
    print(f"Selected {len(pdf_paths)} file(s).")

    start_time = time.time()
    print(f"\nProcessing {len(pdf_paths)} files using multi-threading...")
    
    # 3. Setup Directories
    OUTPUT_BASE = "output"
    EXCEL_DIR = os.path.join(OUTPUT_BASE, "excel")
    JSON_DIR = os.path.join(OUTPUT_BASE, "json")
    os.makedirs(EXCEL_DIR, exist_ok=True)
    os.makedirs(JSON_DIR, exist_ok=True)
    
    account_groups = {}
    
    # 4. Multi-threaded Processing
    with ThreadPoolExecutor(max_workers=min(len(pdf_paths), 4)) as executor:
        futures = {executor.submit(validate_and_process_pdf, p, ay_range): p for p in pdf_paths}
        
        for future in futures:
            p = futures[future]
            filename = os.path.basename(p)
            err_code, meta, txns = future.result()
            
            if err_code:
                # Handle error reporting in JSON
                json_filename = f"nobankstatement_{filename.replace('.pdf', '')}.json"
                json_path = os.path.join(JSON_DIR, json_filename)
                
                error_msg = "not a valid file"
                if err_code == "ENCRYPTED":
                    error_msg = "encrypted file"
                elif err_code == "EMPTY_PDF":
                    error_msg = "not a valid file (empty pdf)"
                elif err_code == "UNSUPPORTED_FILE_TYPE":
                    error_msg = "unsupported file type - only PDF is allowed"
                elif err_code == "INVALID_BANK_STATEMENT":
                    error_msg = "uploaded file is not a bank statement or format mismatch"
                elif err_code == "FILE_NOT_FOUND":
                    error_msg = "file not found"
                else:
                    error_msg = str(err_code)

                with open(json_path, 'w') as f:
                    json.dump({"error": error_msg, "filename": filename}, f, indent=4)

                print(f"ERROR: '{filename}' -> {error_msg}")
                continue
            
            # If success, group by account
            acc_no = meta.get("Account Number", "Unknown")
            if acc_no == "Not Found" or not acc_no:
                acc_no = f"Unknown_{os.path.splitext(meta['filename'])[0]}"

            if acc_no not in account_groups:
                account_groups[acc_no] = {
                    "metadata": meta.copy(),
                    "transactions": [],
                    "source_files": [meta.get("filename", filename)]
                }
            else:
                current_files = account_groups[acc_no].setdefault("source_files", [])
                if meta.get("filename") and meta.get("filename") not in current_files:
                    current_files.append(meta.get("filename"))

            account_groups[acc_no]["transactions"].extend(txns)
            # Merge metadata
            for k, v in meta.items():
                if account_groups[acc_no]["metadata"].get(k) in (None, "Not Found", "") and v not in (None, "Not Found", ""):
                    account_groups[acc_no]["metadata"][k] = v

    # 4. Final Export & Terminal Summary
    print("\n" + "-"*70)
    print(f"{'ACCOUNT NUMBER':<25} | {'TXNS':<6} | {'TTL CREDIT':<15} | {'TTL DEBIT':<15}")
    print("-"*70)
    
    grand_total_credit = 0
    grand_total_debit = 0
    
    for acc_no, data in account_groups.items():
        txns = data["transactions"]
        txns.sort(key=lambda x: parse_date_obj(x[0]))
        
        acc_credit = sum(t[2] for t in txns)
        acc_debit = sum(t[3] for t in txns)
        grand_total_credit += acc_credit
        grand_total_debit += acc_debit
        
        print(f"{acc_no:<25} | {len(txns):<6} | {acc_credit:<15.2f} | {acc_debit:<15.2f}")
        
        # Prepare only the required metadata fields for output
        output_metadata = {
            "Bank Name": data["metadata"].get("Bank Name", "Not Found"),
            "Account Holder Name": data["metadata"].get("Account Holder Name", "Not Found"),
            "Account Number": data["metadata"].get("Account Number", "Not Found"),
            "page_count": data["metadata"].get("page_count", 0),
            "source_files": sorted(data.get("source_files", []))
        }

        # Export to Excel
        excel_path = os.path.join(EXCEL_DIR, f"{acc_no}.xlsx")
        export_to_excel(txns, output_metadata, excel_path)
        
        # Export to JSON
        json_path = os.path.join(JSON_DIR, f"{acc_no}.json")
        final_bal = txns[-1][4] if txns else 0.0
        json_data = {
            "metadata": output_metadata,
            "transactions": [
                {"date": t[0], "description": t[1], "credit": t[2], "debit": t[3], "balance": t[4]}
                for t in txns
            ],
            "summary": {
                "total_credit": acc_credit,
                "total_debit": acc_debit,
                "transaction_count": len(txns),
                "final_balance": final_bal
            }
        }
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=4)

    end_time = time.time()
    total_time = round(end_time - start_time, 2)
    
    # Create report.json
    report_path = os.path.join(OUTPUT_BASE, "report.json")
    report_data = {
        "execution_time_seconds": total_time,
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": len(pdf_paths),
        "total_accounts": len(account_groups)
    }
    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=4)
    
    print("-"*70)
    print(f"{'GRAND TOTAL':<25} | {'':<6} | {grand_total_credit:<15.2f} | {grand_total_debit:<15.2f}")
    print("="*70)
    print(f"SUCCESS: Processed {len(pdf_paths)} files in {total_time} seconds.")
    print(f"Excel files saved in: {os.path.abspath(EXCEL_DIR)}")
    print(f"JSON files and report saved in: {os.path.abspath(JSON_DIR)}")
    print(f"Execution report: {os.path.abspath(report_path)}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
