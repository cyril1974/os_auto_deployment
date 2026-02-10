#!/usr/bin/env python3
"""
Generate a JSON file containing file names and paths in a tree structure for iso_repository
"""
import json
import os
from pathlib import Path
from datetime import datetime

def build_tree_structure(directory_path):
    """Build a tree structure with only file names and relative paths"""
    directory = Path(directory_path)
    
    if not directory.exists():
        raise ValueError(f"Directory does not exist: {directory_path}")
    
    tree = {}
    
    # Walk through directory recursively
    for item in sorted(directory.rglob('*')):
        # Skip the output file itself
        if item.name == 'file_list.json':
            continue
        
        # Only include files, not directories
        if not item.is_file():
            continue
        
        # Only include ISO files
        if item.suffix.lower() != '.iso':
            continue
            
        try:
            # Get relative path from iso_repository
            rel_path = item.relative_to(directory)
            
            # Get the parent directory path
            parent_parts = rel_path.parent.parts
            
            # Create file object with OS_Name and OS_Path
            os_name = item.stem  # filename without extension
            file_obj = {
                "OS_Name": os_name,
                "OS_Path": str(rel_path)
            }
            
            # If file is in root directory
            if not parent_parts:
                if "root_files" not in tree:
                    tree["root_files"] = []
                tree["root_files"].append(file_obj)
            else:
                # File is in a subdirectory
                dir_name = parent_parts[0]
                if dir_name not in tree:
                    tree[dir_name] = []
                tree[dir_name].append(file_obj)
                
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not access {item}: {e}")
            continue
    
    return tree

def main():
    # Define paths
    iso_repo_path = "/cyril_works/My_Document/autoinstall/iso_repository"
    output_file = os.path.join(iso_repo_path, "file_list.json")
    
    print(f"Scanning directory: {iso_repo_path}")
    tree_structure = build_tree_structure(iso_repo_path)
    
    # Create output structure
    output = {
        "scan_time": datetime.now().isoformat(),
        "root_directory": "iso_repository",
        "tree": tree_structure
    }
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"File list saved to: {output_file}")

if __name__ == "__main__":
    main()
