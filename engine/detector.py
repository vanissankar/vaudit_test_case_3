import re

def normalize_text(text):
    if not text: return ""
    return re.sub(r'[^A-Z0-9]', '', text.upper())

# Robust Standard Labels for Hybrid Search
HEADERS = {
    "ACCOUNT_HOLDER": ["Account Holder Name", "Account Name", "Name", "Customer Name", "Customer Name :", "MR ", "MRS ", "MS ", "Account Holder"],
    "ACCOUNT_NUMBER": ["Account Number", "Account No", "A/C No", "A/C Number", "A/C No.", "Acc.No.", "Account No :", "Ac No"],
    "IFSC": ["IFSC", "IFSC Code", "IFSC No", "RTGS/NEFT IFSC"],
    "MICR": ["MICR", "MICR Code"],
    "BRANCH": ["Branch", "Branch Name", "Branch :", "Office"],
    "STATEMENT_DATE": ["Statement Date", "Date :", "Date of Issue", "Date"]
}

def extract_metadata_from_coords(page_words, labels):
    """Refined coordinate-based extraction for high precision."""
    for label in labels:
        label_norm = normalize_text(label)
        for i, w in enumerate(page_words):
            if label_norm in normalize_text(w[4]):
                # Found label, look to the right
                curr_y = w[1]
                x1 = w[2]
                # Filter words on same line, to the right, within 350px
                line_words = [pw for pw in page_words if abs(pw[1] - curr_y) < 5 and pw[0] > x1 and pw[0] - x1 < 350]
                if line_words:
                    line_words.sort(key=lambda x: x[0])
                    val = " ".join([pw[4] for pw in line_words]).strip()
                    val = re.sub(r'^[:\- ]+', '', val).strip()
                    if val and len(val) > 1: return val
                
                # If nothing on right, look below (Vertical KVP)
                below_words = [pw for pw in page_words if pw[1] > curr_y and abs(pw[0] - w[0]) < 80 and pw[1] - curr_y < 40]
                if below_words:
                    below_words.sort(key=lambda x: (x[1], x[0]))
                    val = " ".join([pw[4] for pw in below_words]).strip()
                    val = re.sub(r'^[:\- ]+', '', val).strip()
                    if val and len(val) > 1: return val
    return None

def extract_metadata(first_page_text, page_words=None):
    """
    Hybrid Universal Metadata Extraction.
    Combines high-reliability keywords with layout-agnostic KVP discovery.
    """
    metadata = {
        "Bank Name": "Not Found",
        "Account Holder Name": "Not Found",
        "Account Number": "Not Found",
        "IFSC": "Not Found",
        "MICR": "Not Found",
        "Branch": "Not Found",
        "Statement Date": "Not Found",
        "Statement Period": "Not Found"
    }

    if not first_page_text or not page_words: return metadata
    first_page_upper = first_page_text.upper()
    
    # 1. Bank Identification (Name and IFSC-based)
    # Search top of page for full bank names first (highest priority)
    header_area = first_page_text[:1200].upper()
    for bid, config in BANK_CONFIG.items():
        if config["name"].upper() in header_area:
            metadata["Bank Name"] = config["name"]
            break
    
    # IFSC fallback for Bank Name
    ifsc_m = re.search(r'\b([A-Z]{4})0[A-Z0-9]{6}\b', first_page_upper)
    if ifsc_m:
        metadata["IFSC"] = ifsc_m.group(0)
        if metadata["Bank Name"] == "Not Found":
            bank_code = ifsc_m.group(1)
            if bank_code in BANK_CONFIG: metadata["Bank Name"] = BANK_CONFIG[bank_code]["name"]
            else: metadata["Bank Name"] = f"Bank ({bank_code})"

    # 2. Strategy A: Coordinate-Aware Keyword Search (Reliable for SBI/KVB/HDFC)
    targets = {
        "Account Holder Name": HEADERS["ACCOUNT_HOLDER"],
        "Account Number": HEADERS["ACCOUNT_NUMBER"],
        "Branch": HEADERS["BRANCH"],
        "Statement Date": HEADERS["STATEMENT_DATE"],
        "IFSC": HEADERS["IFSC"],
        "MICR": HEADERS["MICR"]
    }
    
    for field, labels in targets.items():
        val = extract_metadata_from_coords(page_words, labels)
        if val and metadata[field] == "Not Found":
            metadata[field] = val

    # 3. Strategy B: Colon-based KVP Discovery (Supplemental for SCBL/Unknowns)
    lines = []
    curr_y = -1
    curr_line = []
    for w in sorted(page_words, key=lambda x: (x[1], x[0])):
        if abs(w[1] - curr_y) > 4:
            if curr_line: lines.append(curr_line)
            curr_line = [w]; curr_y = w[1]
        else: curr_line.append(w)
    if curr_line: lines.append(curr_line)

    for i, line in enumerate(lines):
        line_text = " ".join([w[4] for w in line])
        if ":" in line_text:
            parts = line_text.split(":", 1)
            k_raw = parts[0].strip().upper()
            v_raw = parts[1].strip()
            if not v_raw and i+1 < len(lines): v_raw = " ".join([w[4] for w in lines[i+1]]).strip()
            
            # Map discovered KVP to metadata
            for field, keywords in targets.items():
                if any(kw.upper() in k_raw for kw in keywords if len(kw) > 3):
                    if metadata[field] == "Not Found" and len(v_raw) > 1:
                        metadata[field] = v_raw

    # 4. Strategy C: Pure Heuristics for Holder and Account
    # Holder Name Priority: Search for MR/MRS/MS in top area
    if metadata["Account Holder Name"] == "Not Found" or len(metadata["Account Holder Name"]) > 100:
        for line in lines[2:15]: # Skip very top header
            text = " ".join([w[4] for w in line]).strip()
            if text.upper().startswith(("MR ", "MRS ", "MS ", "DR ")):
                metadata["Account Holder Name"] = text; break

    # Account Number: 9-18 digit string in top 35% of page
    if metadata["Account Number"] == "Not Found":
        p_accs = re.findall(r'\b\d{9,18}\b', first_page_text[:1200])
        if p_accs: metadata["Account Number"] = p_accs[0]

    # 5. Final Cleaning and Validation
    if metadata["Account Number"] != "Not Found":
        metadata["Account Number"] = re.sub(r'[^0-9]', '', metadata["Account Number"])
    
    if metadata["Account Holder Name"] != "Not Found":
        # Clean up appended noise
        metadata["Account Holder Name"] = re.split(r'CIF|Address|Acc\.No|Statement|Date|Branch', metadata["Account Holder Name"], flags=re.I)[0].strip()

    return metadata

BANK_CONFIG = {
    "SBIN": {"name": "State Bank of India"},
    "SCBL": {"name": "Standard Chartered Bank"},
    "KVBL": {"name": "Karur Vysya Bank"},
    "HDFC": {"name": "HDFC Bank"},
    "ICIC": {"name": "ICICI Bank"},
    "AXIS": {"name": "Axis Bank"},
    "KKBK": {"name": "Kotak Mahindra Bank"},
    "FDRL": {"name": "Federal Bank"},
    "IDFB": {"name": "IDFC First Bank"},
    "INDB": {"name": "IndusInd Bank"},
    "KARB": {"name": "Karnataka Bank"},
    "RBL": {"name": "RBL Bank"},
    "SIB": {"name": "South Indian Bank"},
    "TMBL": {"name": "Tamilnad Mercantile Bank"},
    "BARB": {"name": "Bank of Baroda"},
    "UBIN": {"name": "Union Bank of India"},
    "CNRB": {"name": "Canara Bank"},
    "IDIB": {"name": "Indian Bank"},
    "IOBA": {"name": "Indian Overseas Bank"},
    "UCBA": {"name": "UCO Bank"},
    "MAHB": {"name": "Bank of Maharashtra"},
    "PSIB": {"name": "Punjab & Sind Bank"}
}
