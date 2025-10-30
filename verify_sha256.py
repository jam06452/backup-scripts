#!/usr/bin/env python3
import hashlib
import sys
from pathlib import Path

def calculate_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def compare_directories(dir1: Path, dir2: Path):
    files1 = {f.relative_to(dir1): f for f in dir1.rglob('*') if f.is_file()}
    files2 = {f.relative_to(dir2): f for f in dir2.rglob('*') if f.is_file()}
    
    all_files = set(files1.keys()) | set(files2.keys())
    
    matches = 0
    mismatches = 0
    missing = 0
    
    for rel_path in sorted(all_files):
        if rel_path not in files1:
            print(f'✗ Missing in original: {rel_path}')
            missing += 1
        elif rel_path not in files2:
            print(f'✗ Missing in restored: {rel_path}')
            missing += 1
        else:
            hash1 = calculate_sha256(files1[rel_path])
            hash2 = calculate_sha256(files2[rel_path])
            if hash1 == hash2:
                matches += 1
            else:
                print(f'✗ SHA256 mismatch: {rel_path}')
                print(f'  Original:  {hash1}')
                print(f'  Restored:  {hash2}')
                mismatches += 1
    
    total = matches + mismatches + missing
    print(f'\n{"="*70}')
    print(f'Total files: {total}')
    print(f'✓ Matches: {matches} ({matches/total*100:.1f}%)')
    if mismatches:
        print(f'✗ Mismatches: {mismatches}')
    if missing:
        print(f'✗ Missing: {missing}')
    print(f'{"="*70}')
    
    return matches == total

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python verify_sha256.py <original_dir> <restored_dir>')
        sys.exit(1)
    
    dir1 = Path(sys.argv[1])
    dir2 = Path(sys.argv[2])
    
    if not dir1.exists():
        print(f'Error: {dir1} does not exist')
        sys.exit(1)
    if not dir2.exists():
        print(f'Error: {dir2} does not exist')
        sys.exit(1)
    
    success = compare_directories(dir1, dir2)
    sys.exit(0 if success else 1)
