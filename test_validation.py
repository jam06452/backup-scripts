#!/usr/bin/env python3
"""
Quick validation test for the backup utility.
Tests basic functionality without actually uploading to GitHub.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import backup module
sys.path.insert(0, str(Path(__file__).parent))

from backup import (
    check_gh_cli_installed,
    check_gh_authentication,
    get_file_size_mb,
    CHUNK_SIZE_BYTES,
    CHUNK_SIZE_MB,
)

def test_constants():
    """Test that constants are set correctly."""
    print("Testing constants...")
    assert CHUNK_SIZE_MB == 50, "Chunk size should be 50MB"
    assert CHUNK_SIZE_BYTES == 52428800, "Chunk size in bytes should be 52,428,800"
    print("✓ Constants are correct")

def test_gh_cli():
    """Test GitHub CLI detection."""
    print("\nTesting GitHub CLI detection...")
    is_installed = check_gh_cli_installed()
    print(f"  GitHub CLI installed: {is_installed}")
    
    if is_installed:
        is_authenticated = check_gh_authentication()
        print(f"  GitHub CLI authenticated: {is_authenticated}")
        if is_authenticated:
            print("✓ GitHub CLI is installed and authenticated")
        else:
            print("⚠ GitHub CLI is installed but NOT authenticated")
            print("  Run: gh auth login")
    else:
        print("⚠ GitHub CLI is NOT installed")
        print("  Install from: https://cli.github.com/")

def test_file_size_calculation():
    """Test file size calculation."""
    print("\nTesting file size calculation...")
    
    # Create a small test file
    test_file = Path("test_size.tmp")
    test_data = b"0" * (1024 * 1024)  # 1MB of data
    
    try:
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        size_mb = get_file_size_mb(test_file)
        assert 0.99 < size_mb < 1.01, f"Size should be ~1MB, got {size_mb}MB"
        print(f"✓ File size calculation correct: {size_mb:.2f} MB")
    finally:
        if test_file.exists():
            test_file.unlink()

def test_import():
    """Test that all required functions can be imported."""
    print("\nTesting imports...")
    
    required_functions = [
        'check_gh_cli_installed',
        'check_gh_authentication',
        'get_file_size_mb',
        'create_archive',
        'split_file',
        'upload_chunks_to_github',
        'cleanup_temp_files',
        'backup_to_github',
    ]
    
    from backup import (
        check_gh_cli_installed,
        check_gh_authentication,
        get_file_size_mb,
        create_archive,
        split_file,
        upload_chunks_to_github,
        cleanup_temp_files,
        backup_to_github,
    )
    
    print("✓ All required functions imported successfully")

def main():
    """Run all validation tests."""
    print("=" * 70)
    print("  Backup Utility - Validation Tests")
    print("=" * 70)
    
    try:
        test_import()
        test_constants()
        test_file_size_calculation()
        test_gh_cli()
        
        print("\n" + "=" * 70)
        print("  Validation Complete!")
        print("=" * 70)
        print("\n✓ All tests passed successfully")
        print("\nNext steps:")
        print("  1. Ensure GitHub CLI is installed and authenticated")
        print("  2. Test with a small file: python backup.py <test_file>")
        print("  3. Verify chunks appear in: https://github.com/jam06452/LargeFileStorage")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
