"""
Inspect the CSV file structure to determine the correct format and separators.
"""
import pandas as pd
import os

def inspect_csv(filename):
    """Read the first few lines of a CSV file to determine its structure"""
    print(f"Inspecting file: {filename}")
    
    # First read the raw text
    print("\n--- Raw data (first 5 lines) ---")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                print(f"{i+1}: {line.strip()}")
    except Exception as e:
        print(f"Error reading file: {str(e)}")
    
    # Now try to parse with different approaches
    try:
        # Try reading with comma separator
        print("\n--- Using comma separator ---")
        df_comma = pd.read_csv(filename, nrows=5)
        print(f"Columns: {df_comma.columns.tolist()}")
        print(f"Shape: {df_comma.shape}")
        print(df_comma.head())
    except Exception as e:
        print(f"Error with comma separator: {str(e)}")
    
    try:
        # Try reading with semicolon separator
        print("\n--- Using semicolon separator ---")
        df_semi = pd.read_csv(filename, sep=';', nrows=5)
        print(f"Columns: {df_semi.columns.tolist()}")
        print(f"Shape: {df_semi.shape}")
        print(df_semi.head())
    except Exception as e:
        print(f"Error with semicolon separator: {str(e)}")
    
    try:
        # Try auto-detection
        print("\n--- Using Python engine for detection ---")
        df_auto = pd.read_csv(filename, delimiter=None, engine='python', nrows=5)
        print(f"Columns: {df_auto.columns.tolist()}")
        print(f"Shape: {df_auto.shape}")
        print(df_auto.head())
    except Exception as e:
        print(f"Error with auto-detection: {str(e)}")

if __name__ == "__main__":
    inspect_csv('simulation_results.csv')
