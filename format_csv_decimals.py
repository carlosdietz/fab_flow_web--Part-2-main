"""
Format a semicolon-separated CSV file to use commas for decimals in the Avg Cycle Time column.

This script:
1. Reads a semicolon-separated CSV file
2. Formats the Avg Cycle Time column to use commas instead of periods for decimals
3. Saves the updated file
"""
import os
import pandas as pd
import re

def format_cycle_time(input_file='simulation_results.csv', output_file=None, backup=True):
    print(f"Processing file: {input_file}")
    
    # Create backup if requested
    if backup:
        base, ext = os.path.splitext(input_file)
        backup_file = f"{base}_backup{ext}"
        print(f"Creating backup: {backup_file}")
        with open(input_file, 'r', encoding='utf-8') as src, open(backup_file, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    
    # If no output file specified, overwrite the original
    if output_file is None:
        output_file = input_file
    
    # Read the file content
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.readlines()
    
    # Find the header row
    header = content[0].strip()
    headers = header.split(';')
    
    # Find the index of Avg Cycle Time column
    cycle_time_index = -1
    for i, col in enumerate(headers):
        if 'cycle' in col.lower() and 'time' in col.lower():
            cycle_time_index = i
            print(f"Found 'Avg Cycle Time' column at index {cycle_time_index}: '{col}'")
            break
    
    if cycle_time_index == -1:
        print("Error: Could not find 'Avg Cycle Time' column in headers:")
        print(headers)
        return False
    
    # Process each line
    new_content = [header]  # Keep header as is
    changes_made = 0
    
    for i in range(1, len(content)):
        line = content[i].strip()
        if not line:
            new_content.append(line)
            continue
            
        parts = line.split(';')
        if len(parts) <= cycle_time_index:
            print(f"Warning: Line {i+1} has fewer columns than expected")
            new_content.append(line)
            continue
        
        value = parts[cycle_time_index]
        
        # Skip if already using comma
        if ',' in value:
            new_content.append(line)
            continue
        
        # Replace period with comma for decimals
        if '.' in value:
            new_value = value.replace('.', ',')
            parts[cycle_time_index] = new_value
            new_line = ';'.join(parts)
            new_content.append(new_line)
            changes_made += 1
            
            if changes_made <= 5:
                print(f"Changed: '{value}' → '{new_value}'")
        else:
            new_content.append(line)
    
    # Write the updated content
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in new_content:
            f.write(line + '\n')
    
    print(f"Completed: {changes_made} decimal formats changed")
    print(f"Output saved to: {output_file}")
    return True

if __name__ == "__main__":
    import sys
    input_file = 'simulation_results.csv'
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        
    format_cycle_time(input_file)
