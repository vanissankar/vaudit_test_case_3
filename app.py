import os
import shutil
import uuid
import time
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Engine imports
from engine.parser import extract_transactions_universally, clean_amount, extract_date, parse_date_obj
from engine.detector import extract_metadata
from engine.exporter import export_to_excel
import fitz

app = FastAPI(title="Bank Statement Extractor API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "./uploads"
RESULTS_DIR = "./results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

def get_ay_range(ay_str):
    try:
        parts = ay_str.split('-')
        start_year = int(parts[0].strip())
        fy_start = datetime(start_year, 4, 1)
        fy_end = datetime(start_year + 1, 3, 31, 23, 59, 59)
        return fy_start, fy_end
    except:
        raise ValueError("Invalid FY format. Use YYYY-YY.")

def process_single_pdf(filepath, ay_range):
    filename = os.path.basename(filepath)
    try:
        with fitz.open(filepath) as doc:
            if len(doc) == 0: return {"error": "Empty PDF"}
            
            first_page_words = doc[0].get_text_words()
            first_page_text = doc[0].get_text()
            metadata = extract_metadata(first_page_text, first_page_words)
            
            # Validation
            if metadata["Bank Name"] == "Not Found" and metadata["Account Number"] == "Not Found":
                return {"error": f"Invalid bank statement format: {filename}"}
            
            metadata["filename"] = filename
            metadata["page_count"] = len(doc)
            
            all_txns = []
            for i in range(len(doc)):
                page_words = doc[i].get_text_words()
                all_txns.extend(extract_transactions_universally(page_words))
            
            # Filter by AY
            start_date, end_date = ay_range
            filtered_txns = [t for t in all_txns if start_date <= parse_date_obj(t[0]) <= end_date]
            
            return {"metadata": metadata, "transactions": filtered_txns, "error": None}
    except Exception as e:
        return {"error": str(e)}

@app.post("/process")
async def process_statements(ay: str = Form(...), files: List[UploadFile] = File(...)):
    start_time = time.time()
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    try:
        ay_range = get_ay_range(ay)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    saved_files = []
    for file in files:
        file_path = os.path.join(job_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(file_path)
    
    account_groups = {}
    errors = []
    
    # Use ThreadPoolExecutor for multi-threaded processing
    with ThreadPoolExecutor(max_workers=min(len(saved_files), 4)) as executor:
        results = list(executor.map(lambda f: process_single_pdf(f, ay_range), saved_files))
    
    for res in results:
        if res["error"]:
            errors.append(res["error"])
            continue
            
        meta = res["metadata"]
        txns = res["transactions"]
        acc_no = meta.get("Account Number", "Unknown")
        if acc_no == "Not Found" or not acc_no: acc_no = f"Unknown_{os.path.splitext(meta['filename'])[0]}"
        
        if acc_no not in account_groups:
            account_groups[acc_no] = {"metadata": meta, "transactions": []}
        
        account_groups[acc_no]["transactions"].extend(txns)

    if errors:
        # If any validation failed, we return error as per user instructions "terminate with custom error"
        raise HTTPException(status_code=400, detail=f"Validation Failed: {', '.join(errors)}")

    final_results = []
    for acc_no, data in account_groups.items():
        txns = data["transactions"]
        txns.sort(key=lambda x: parse_date_obj(x[0]))
        
        acc_credit = sum(t[2] for t in txns)
        acc_debit = sum(t[3] for t in txns)
        
        # Export to Excel
        export_filename = f"{acc_no}_{job_id[:8]}.xlsx"
        export_path = os.path.join(RESULTS_DIR, export_filename)
        export_to_excel(txns, data["metadata"], export_path)
        
        final_results.append({
            "account_no": acc_no,
            "bank": data["metadata"].get("Bank Name", "N/A"),
            "transaction_count": len(txns),
            "total_credit": round(acc_credit, 2),
            "total_debit": round(acc_debit, 2),
            "download_url": f"/download/{export_filename}",
            "filename": export_filename
        })

    end_time = time.time()
    return {
        "status": "success",
        "job_id": job_id,
        "time_taken": round(end_time - start_time, 2),
        "results": final_results
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
