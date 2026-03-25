import pandas as pd
import json
import os

def export_to_excel(transactions, metadata, output_path):
    """
    Exports transactions to Excel with metadata at the top.
    Columns: Date, Description, Credit, Debit, Balance
    """
    # Create DataFrame for transactions
    df = pd.DataFrame(transactions, columns=["Date", "Description", "Credit", "Debit", "Balance"])
    
    # Create writer
    writer = pd.ExcelWriter(output_path, engine='xlsxwriter')
    workbook = writer.book
    sheet_name = 'Statement'
    
    # Formats
    header_format = workbook.add_format({
        'bold': True, 
        'bg_color': '#D7E4BC', 
        'border': 1,
        'align': 'center'
    })
    meta_label_format = workbook.add_format({'bold': True, 'font_color': '#1F4E78'})
    meta_value_format = workbook.add_format({'font_color': '#3B3838'})
    
    # 1. Write Metadata at the top
    row_idx = 0
    df.to_excel(writer, sheet_name=sheet_name, startrow=10, index=False)
    worksheet = writer.sheets[sheet_name]
    
    metadata_fields = [
        ("Account Name", metadata.get("Account Holder Name", "N/A")),
        ("Account Number", metadata.get("Account Number", "N/A")),
        ("Bank Name", metadata.get("Bank Name", "N/A")),
        ("IFSC Code", metadata.get("IFSC", "N/A")),
        ("MICR Code", metadata.get("MICR", "N/A")),
        ("Branch", metadata.get("Branch", "N/A")),
        ("Statement Date", metadata.get("Statement Date", "N/A")),
        ("Filename", metadata.get("filename", "N/A")),
        ("Total Pages", metadata.get("page_count", "N/A"))
    ]
    
    for label, value in metadata_fields:
        worksheet.write(row_idx, 0, label, meta_label_format)
        worksheet.write(row_idx, 1, str(value), meta_value_format)
        row_idx += 1
    
    # 2. Format Transaction Headers (at row 10)
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(10, col_num, value, header_format)
        
    # 3. Auto-adjust column widths
    for i, col in enumerate(df.columns):
        column_len = df[col].astype(str).str.len().max()
        column_len = max(column_len, len(col)) + 2
        worksheet.set_column(i, i, column_len)

    writer.close()

def export_to_json(metadata, summary, transactions, output_path):
    """
    Exports metadata, summary, and full transactions to JSON.
    """
    data = {
        "metadata": metadata, 
        "summary": summary,
        "transactions": transactions
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
