"""
Fix CSV formatting for Average Cycle Time column.

This script reads simulation_results.csv, fixes formatting in the Average Cycle Time column,
and saves the corrected file.
"""
import pandas as pd
import re
import os
import sys

def fix_csv_format(input_file='simulation_results.csv', output_file=None):
    if output_file is None:
        # If no output file specified, create a backup and overwrite the original
        base, ext = os.path.splitext(input_file)
        backup_file = f"{base}_backup{ext}"
        output_file = input_file
        # Create backup
        if os.path.exists(input_file):
            print(f"Creating backup of original file: {backup_file}")
            with open(input_file, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())
    
    try:
        # Read the CSV file - try different separators
        print(f"Reading CSV file: {input_file}")
        try:
            # First try with comma
            df = pd.read_csv(input_file)
            print("Using comma as separator")
        except:
            try:
                # Then try with semicolon
                df = pd.read_csv(input_file, sep=';')
                print("Using semicolon as separator")
            except:
                # Try with auto-detection
                print("Trying to auto-detect separator...")
                with open(input_file, 'r') as f:
                    first_line = f.readline().strip()
                    if ';' in first_line:
                        df = pd.read_csv(input_file, sep=';')
                        print("Detected semicolon separator")
                    else:
                        df = pd.read_csv(input_file, delimiter=None, engine='python')
                        print(f"Using python engine to auto-detect separator")
        
        # Check if 'Avg Cycle Time' column exists
        cycle_time_col = None
        for col in df.columns:
            if 'cycle' in col.lower() and 'time' in col.lower():
                cycle_time_col = col
                break
        
        if cycle_time_col is None:
            print("Error: Could not find a column matching 'Avg Cycle Time'")
            print(f"Available columns: {df.columns.tolist()}")
            sys.exit(1)
        
        print(f"Found cycle time column: '{cycle_time_col}'")
        
        # Function to fix date-like formatting in cycle time values
        def fix_format(val):
            # Convert to string if it's not already
            val_str = str(val).strip()
            
            # Check if it contains month abbreviations
            month_patterns = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
            }
            
            for month, num in month_patterns.items():
                if month in val_str:
                    # Extract the number before the month (day)
                    parts = val_str.split('.')
                    if len(parts) >= 2:
                        day_part = parts[0].strip()
                        # Replace month with its number and reconstruct
                        return f"{day_part},{num}"
            
            # If it's already a proper decimal, ensure consistent format
            if '.' in val_str:
                parts = val_str.split('.')
                if len(parts) == 2:
                    # Ensure 2 decimal places with comma as separator
                    return f"{parts[0]},{parts[1].ljust(2, '0')[:2]}"
                    
            # If it's an integer, add ",00"
            if val_str.isdigit():
                return f"{val_str},00"
                
            # If none of the above, return as is with period replaced by comma
            return val_str.replace('.', ',')
        
        # Apply the formatting fix to the cycle time column
        original_values = df[cycle_time_col].tolist()
        df[cycle_time_col] = df[cycle_time_col].apply(fix_format)
        
        # Save the corrected CSV
        print(f"Saving corrected CSV to: {output_file}")
        df.to_csv(output_file, index=False)
        
        # Show some examples of the changes
        print("\nExample of corrections:")
        for i in range(min(5, len(original_values))):
            print(f"  Original: {original_values[i]} -> Corrected: {df[cycle_time_col].iloc[i]}")
        
        print("\nCSV formatting correction completed successfully.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Get file path from command line if provided
    input_file = 'simulation_results.csv'
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    fix_csv_format(input_file)
