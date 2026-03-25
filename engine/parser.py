import re

def clean_amount(text):
    if not text: return 0.0
    text = str(text).strip()
    # Stricter cleaning: remove all but digits, dots, and minus
    # If there are multiple numbers in the cell (separated by space), take the last one (usually the amount)
    # or the one that looks most like an amount.
    parts = text.split()
    if len(parts) > 1:
        # Try to find one with a dot or comma
        for p in reversed(parts):
            if "." in p or "," in p:
                text = p
                break
        else:
            text = parts[-1]

    # Reference ID protection: If it's a long string of digits without typical amount formatting
    if len(re.sub(r'[^0-9]', '', text)) > 11:
        if "." not in text and "," not in text:
            return 0.0
            
    if "(" in text and ")" in text: 
        text = "-" + text.replace("(", "").replace(")", "")
    text = text.replace(",", "")
    if text.count(".") > 1:
        parts = text.split(".")
        text = "".join(parts[:-1]) + "." + parts[-1]
    
    text = re.sub(r'[^\d.\-]', '', text)
    try:
        val = float(text)
        if abs(val) > 1e12: return 0.0 # Realistic threshold for bank transactions
        return val
    except:
        return 0.0

def clean_description(text):
    if not text: return ""
    text = re.sub(r'Page \d+ of \d+.*', '', text, flags=re.I)
    text = re.sub(r'Generated on.*', '', text, flags=re.I)
    noise = [
        r"This is a computer generated.*",
        r"Please notify the bank immediately.*",
        r"Statements are sent to customers only.*",
        r"We would like to reiterate.*",
        r"Never disclose your passwords.*",
        r"are covered under the insurance scheme.*",
        r"Nomination details for your Savings/Deposit accounts.*",
        r"within 30 days from statement.*",
        r"Report irregularities, if any.*"
    ]
    for n in noise:
        text = re.sub(n, '', text, flags=re.I | re.DOTALL)
    # Remove fragments of reference IDs that leaked from amount columns if they are just long numbers
    text = re.sub(r'\b\d{12,}\b', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def is_date(text):
    text = text.strip()
    if not text: return False
    patterns = [
        r'\b\d{1,2}[/\- ](?:[A-Z]{3}|\d{1,2})[/\- ]\d{2,4}\b',
        r'\b\d{1,2}[A-Z]{3}\d{2,4}\b'
    ]
    for p in patterns:
        if re.search(p, text, re.I):
            return True
    return False

def extract_date(text):
    patterns = [
        r'\b\d{1,2}[/\- ](?:[A-Z]{3}|\d{1,2})[/\- ]\d{2,4}\b',
        r'\b\d{1,2}[A-Z]{3}\d{2,4}\b'
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m: return m.group(0)
    return ""

def extract_transactions_universally(page_words):
    if not page_words: return []
    page_words.sort(key=lambda x: (x[1], x[0]))

    lines = []
    curr_y = -1
    curr_line = []
    for w in page_words:
        if abs(w[1] - curr_y) > 4:
            if curr_line: lines.append(curr_line)
            curr_line = [w]; curr_y = w[1]
        else:
            curr_line.append(w)
    if curr_line: lines.append(curr_line)

    header_keywords = ["DATE", "PARTICULARS", "DESCRIPTION", "NARRATION", "CHQ", "REF", "DEPOSIT", "WITHDRAWAL", "CREDIT", "DEBIT", "BALANCE"]
    header_y = None
    columns = [] 

    for i, line in enumerate(lines):
        line_text = " ".join([w[4].upper() for w in line])
        if "SUMMARY" in line_text or "OPENING" in line_text or "PERIOD" in line_text: continue
        
        combined_line = list(line)
        if i + 1 < len(lines): combined_line.extend(lines[i+1])
        combined_text = " ".join([w[4].upper() for w in combined_line])
        
        matches = [k for k in header_keywords if k in combined_text]
        if len(matches) >= 3:
            temp_cols = []
            for w in combined_line:
                val = w[4].upper().strip(":. -/")
                if any(k in val or val in k for k in header_keywords):
                    if not any(abs(c["x0"] - w[0]) < 10 for c in temp_cols):
                        temp_cols.append({"name": val, "x0": w[0], "x1": w[2]})
            
            if any("DATE" in c["name"].upper() for c in temp_cols):
                header_y = max(line[0][1], lines[i+1][0][1]) if i+1 < len(lines) else line[0][1]
                columns = temp_cols
                break

    if not columns: return []

    columns.sort(key=lambda x: x["x0"])
    zones = []
    for i in range(len(columns)):
        start_x = columns[i]["x0"] - 35 if i == 0 else (columns[i-1]["x1"] + columns[i]["x0"]) / 2
        end_x = columns[i]["x1"] + 150 if i == len(columns) - 1 else (columns[i]["x1"] + columns[i+1]["x0"]) / 2
        
        role = "other"
        name = columns[i]["name"].upper()
        if "DATE" in name: role = "date"
        elif any(x in name for x in ["DESC", "PARTICULAR", "NARRATION", "REMARK"]): role = "desc"
        elif any(x in name for x in ["DEPOSIT", "CREDIT", "CR", "INWARD"]): role = "cr"
        elif any(x in name for x in ["WITHDRAWAL", "DEBIT", "DR", "OUTWARD"]): role = "dr"
        elif "BALANCE" in name: role = "bal"
        elif any(x in name for x in ["CHQ", "REF", "CODE", "VAL"]): role = "other"
        
        zones.append({"role": role, "name": name, "x0": start_x, "x1": end_x})

    transactions = []
    current_txn = None

    for line in lines:
        if line[0][1] <= header_y + 4: continue
        
        cells = {"date": "", "desc": "", "cr": "", "dr": "", "bal": ""}
        for w in line:
            wxmid = (w[0] + w[2]) / 2
            for z in zones:
                if z["x0"] <= wxmid <= z["x1"]:
                    cells[z["role"]] = (cells.get(z["role"], "") + " " + w[4]).strip()
                    break

        date_val = cells.get("date", "")
        if is_date(date_val):
            dt = extract_date(date_val)
            if current_txn: transactions.append(current_txn)
            # Fresh transaction line: capture amounts
            current_txn = [dt, cells.get("desc", ""), cells.get("cr", ""), cells.get("dr", ""), cells.get("bal", "")]
        elif current_txn:
            # Continuation line: ONLY update description. 
            # DO NOT merge amounts from continuation lines to prevent Ref ID leaks.
            desc_cont = cells.get("desc", "").strip()
            if desc_cont: current_txn[1] += " " + desc_cont
            # Fallback: if main line amount was empty but continuation has it (rare)
            if not current_txn[2] and cells.get("cr", ""): current_txn[2] = cells["cr"]
            if not current_txn[3] and cells.get("dr", ""): current_txn[3] = cells["dr"]
            if not current_txn[4] and cells.get("bal", ""): current_txn[4] = cells["bal"]
            
    if current_txn: transactions.append(current_txn)

    final_txns = []
    for t in transactions:
        t[1] = clean_description(t[1])
        t[2] = clean_amount(t[2])
        t[3] = clean_amount(t[3])
        t[4] = clean_amount(t[4])
        if t[0] and (t[1] or t[2] or t[3] or t[4] > 0):
            final_txns.append(t)
            
    return final_txns
