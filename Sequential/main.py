import os
import sys
import glob
import fitz
import json
from datetime import datetime

# Add engine to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from engine.parser import extract_transactions_universally, clean_amount, extract_date
from engine.detector import extract_metadata
from engine.exporter import export_to_excel, export_to_json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
EXCEL_OUTPUT_DIR = os.path.join(BASE_DIR, "output", "excel")
JSON_OUTPUT_DIR = os.path.join(BASE_DIR, "output", "json")

def parse_date_obj(date_str):
    """Parses various date strings into a datetime object for sorting."""
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %b %y", "%d %b %Y", "%d%b%y", "%d %B %y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    return datetime(1900, 1, 1)

def process_pdf_into_data(filepath, pages=None):
    filename = os.path.basename(filepath)
    all_transactions = []
    
    with fitz.open(filepath) as doc:
        first_page_words = doc[0].get_text_words()
        first_page_text = doc[0].get_text()
        metadata = extract_metadata(first_page_text, first_page_words)
        metadata["filename"] = filename
        metadata["page_count"] = len(doc)
        
        max_p = min(pages, len(doc)) if pages else len(doc)
        for i in range(max_p):
            page_words = doc[i].get_text_words()
            txns = extract_transactions_universally(page_words)
            all_transactions.extend(txns)

    return metadata, all_transactions

def main():
    if not os.path.exists(INPUT_DIR): os.makedirs(INPUT_DIR)
    pdfs = glob.glob(os.path.join(INPUT_DIR, "*.pdf"))
    if not pdfs:
        print(f"WARNING: No PDFs found in {INPUT_DIR}")
        return

    account_groups = {}
    for pdf in pdfs:
        print(f"Reading {pdf}...")
        try:
            metadata, txns = process_pdf_into_data(pdf)
            acc_no = metadata.get("Account Number", "Unknown")
            if acc_no == "Not Found" or not acc_no: acc_no = f"Unknown_{os.path.basename(pdf)}"
            
            if acc_no not in account_groups:
                account_groups[acc_no] = {"metadata": metadata, "transactions": []}
            
            account_groups[acc_no]["transactions"].extend(txns)
            # Metadata merge
            for k, v in metadata.items():
                if account_groups[acc_no]["metadata"].get(k) == "Not Found" and v != "Not Found":
                    account_groups[acc_no]["metadata"][k] = v
        except Exception as e:
            print(f"Error processing {pdf}: {e}")

    # Export
    os.makedirs(EXCEL_OUTPUT_DIR, exist_ok=True)
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)

    for acc_no, data in account_groups.items():
        print(f"Exporting data for Account: {acc_no}...")
        txns = data["transactions"]
        meta = data["metadata"]
        
        # 1. Sort transactions by date for a reliable final balance
        txns.sort(key=lambda x: parse_date_obj(x[0]))
        
        # 2. Summary Calculation with Duplicate/Balance Protection
        total_debit = 0.0
        total_credit = 0.0
        for t in txns:
            desc = t[1].upper()
            # Skip "Balance Forward" or "Opening Balance" rows for Credit/Debit totals
            if any(x in desc for x in ["BALANCE FORWARD", "OPENING BALANCE", "BROUGHT FORWARD", "B/F"]):
                continue
            total_credit += t[2]
            total_debit += t[3]
            
        final_balance = txns[-1][4] if txns else 0.0

        summary = {
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "number_of_transactions": len(txns),
            "final_balance": final_balance
        }

        excel_path = os.path.join(EXCEL_OUTPUT_DIR, f"{acc_no}.xlsx")
        json_path = os.path.join(JSON_OUTPUT_DIR, f"{acc_no}.json")
        export_to_excel(txns, meta, excel_path)
        export_to_json(meta, summary, txns, json_path)

if __name__ == "__main__":
    main()
