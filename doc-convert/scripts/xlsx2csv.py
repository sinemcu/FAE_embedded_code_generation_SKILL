#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAE Skill - XLSX to CSV Converter
Converts Excel requirements files to CSV for embedded code generation
"""

import pandas as pd
import os
import sys
from pathlib import Path


def xlsx_to_csv(input_file, output_dir=None):
    """
    Convert XLSX file to CSV (all sheets)
    
    Args:
        input_file (str): Path to .xlsx file
        output_dir (str): Output directory (default: same as input)
    
    Returns:
        list: List of generated CSV file paths
    """
    try:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")
        
        if not input_file.lower().endswith(('.xlsx', '.xls')):
            raise ValueError("Input must be .xlsx or .xls file")
        
        input_path = Path(input_file)
        if output_dir is None:
            output_dir = input_path.parent
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🔍 Reading: {input_file}")
        
        excel_file = pd.ExcelFile(input_file)
        sheet_names = excel_file.sheet_names
        
        print(f"📋 Found {len(sheet_names)} sheet(s): {sheet_names}")
        
        converted_files = []
        for sheet_name in sheet_names:
            df = pd.read_excel(input_file, sheet_name=sheet_name)
            output_filename = f"{input_path.stem}_{sheet_name}.csv"
            output_path = output_dir / output_filename
            
            df.to_csv(output_path, index=False, encoding='utf-8')
            converted_files.append(str(output_path))
            
            print(f"✅ '{sheet_name}' -> {output_path}")
            print(f"   Rows: {len(df)}, Columns: {len(df.columns)}")
        
        print(f"\n🎉 Conversion completed! Created {len(converted_files)} CSV file(s)")
        return converted_files
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python xlsx2csv.py <input.xlsx> [output_dir]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        xlsx_to_csv(input_file, output_dir)
    except Exception as e:
        sys.exit(1)
