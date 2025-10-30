#!/usr/bin/env python3
"""
GitHub Chunked Backup Restore Utility
Restores files/folders from GitHub repository that were backed up using backup.py
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional

# Constants
REPO_URL = "https://github.com/jam06452/LargeFileStorage"


class RestoreError(Exception):
    """Custom exception for restore errors"""
    pass


def print_header(text: str) -> None:
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_section(text: str) -> None:
    """Print a section header"""
    print(f"\n[{text}]")
    print("-" * 70)


def print_info(text: str) -> None:
    """Print info message"""
    print(f"  → {text}")


def print_success(text: str) -> None:
    """Print success message"""
    print(f"✓ {text}")


def print_error(text: str) -> None:
    """Print error message"""
    print(f"✗ {text}", file=sys.stderr)


def check_gh_cli() -> bool:
    """Check if GitHub CLI is installed and authenticated"""
    try:
        # Check if gh is installed
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print_success("GitHub CLI (gh) is installed")
        
        # Check authentication
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print_success("GitHub CLI authentication verified")
            return True
        else:
            print_error("GitHub CLI is not authenticated")
            print_info("Please run: gh auth login")
            return False
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("GitHub CLI (gh) is not installed")
        print_info("Install from: https://cli.github.com/")
        return False


def download_chunks(repo_folder: str, repo_url: str) -> tuple[Path, List[Path]]:
    """
    Download chunk files from GitHub repository folder.
    
    Args:
        repo_folder: Path to folder in repository (e.g., "Downloads/Compressed/Games/CloverPit")
        repo_url: GitHub repository URL
        
    Returns:
        Tuple of (temp_dir_path, list of downloaded chunk files)
    """
    # Create temporary directory for download
    temp_dir = tempfile.mkdtemp(prefix="restore_")
    temp_path = Path(temp_dir)
    repo_path = temp_path / "repo"
    
    print_info(f"Cloning repository to temporary location...")
    
    # Clone the repository
    try:
        subprocess.run(
            ["gh", "repo", "clone", repo_url, str(repo_path)],
            capture_output=True,
            text=True,
            check=True
        )
        print_success("Repository cloned")
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir)
        raise RestoreError(f"Failed to clone repository: {e.stderr}")
    
    # Find the folder in the repo
    folder_path = repo_path / repo_folder
    if not folder_path.exists():
        shutil.rmtree(temp_dir)
        raise RestoreError(f"Folder not found in repository: {repo_folder}")
    
    # Find all chunk files (files ending with .partXXX)
    chunk_files = sorted(folder_path.glob("*.part*"))
    
    if not chunk_files:
        shutil.rmtree(temp_dir)
        raise RestoreError(f"No chunk files found in: {repo_folder}")
    
    print_success(f"Found {len(chunk_files)} chunk file(s)")
    
    return temp_path, chunk_files


def reassemble_chunks(chunk_files: List[Path], output_dir: Path) -> Path:
    """
    Reassemble chunk files into original archive.
    
    Args:
        chunk_files: List of chunk file paths
        output_dir: Directory to write reassembled file
        
    Returns:
        Path to reassembled archive file
    """
    # Get base name from first chunk (remove .partXXX extension)
    base_name = chunk_files[0].name
    # Remove the .partXXX suffix
    if ".part" in base_name:
        base_name = base_name.rsplit(".part", 1)[0]
    
    output_file = output_dir / base_name
    
    print_info(f"Reassembling {len(chunk_files)} chunk(s) into: {base_name}")
    
    # Reassemble chunks with larger buffer for better performance
    buffer_size = 8 * 1024 * 1024  # 8MB buffer
    with open(output_file, 'wb') as outfile:
        for i, chunk_file in enumerate(chunk_files, 1):
            if i % 5 == 0 or i == len(chunk_files) or i == 1:
                print_info(f"  Reading chunk {i}/{len(chunk_files)}...")
            with open(chunk_file, 'rb') as infile:
                shutil.copyfileobj(infile, outfile, length=buffer_size)
    
    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print_success(f"Reassembled archive: {base_name} ({file_size_mb:.2f} MB)")
    
    return output_file


def extract_archive(archive_file: Path, extract_dir: Path) -> Path:
    """
    Extract ZIP archive.
    
    Args:
        archive_file: Path to ZIP archive
        extract_dir: Directory to extract to
        
    Returns:
        Path to extracted folder
    """
    print_info(f"Extracting archive: {archive_file.name}")
    
    try:
        with zipfile.ZipFile(archive_file, 'r') as zip_ref:
            # Get list of files
            file_list = zip_ref.namelist()
            
            # Extract all files at once (faster than individual extraction)
            zip_ref.extractall(extract_dir)
            
            print_success(f"Extracted {len(file_list)} file(s)")
            
            # Find the extracted folder (should be the top-level folder in the zip)
            # Get the first path component from the first file
            if file_list:
                first_file = Path(file_list[0])
                top_level = first_file.parts[0]
                extracted_folder = extract_dir / top_level
                
                if extracted_folder.exists():
                    return extracted_folder
            
            # If we can't determine the folder, return the extract dir
            return extract_dir
            
    except zipfile.BadZipFile:
        raise RestoreError(f"Invalid or corrupted ZIP file: {archive_file.name}")
    except Exception as e:
        raise RestoreError(f"Failed to extract archive: {str(e)}")


def restore_to_location(source_folder: Path, repo_folder_path: str, suffix: Optional[str] = None) -> Path:
    """
    Restore folder to its original location based on repo path.
    
    Args:
        source_folder: Path to extracted folder
        repo_folder_path: Original repo folder path (e.g., "Downloads/Compressed/Games/CloverPit")
        suffix: Optional suffix to add to folder name (e.g., "_restored")
        
    Returns:
        Path to final restored location
    """
    # Parse the repo folder path to reconstruct original location
    # e.g., "Downloads/Compressed/Games/CloverPit" -> C:\Users\Dan\Downloads\Compressed\Games\CloverPit
    
    # Convert forward slashes to Path
    repo_parts = Path(repo_folder_path).parts
    
    # Build the destination path
    # Start from user's home directory or a common base
    if repo_parts[0].lower() == "downloads":
        # Restore to Downloads folder
        base_path = Path.home() / "Downloads"
        # Skip "Downloads" and add the rest
        dest_parts = repo_parts[1:]
    else:
        # Use the repo path as-is from current drive
        base_path = Path.home()
        dest_parts = repo_parts
    
    # Build destination path
    dest_path = base_path
    for part in dest_parts[:-1]:  # All parts except the last (folder name)
        dest_path = dest_path / part
    
    # Get the final folder name
    folder_name = repo_parts[-1]
    
    # Add suffix if specified
    if suffix:
        folder_name = f"{folder_name}{suffix}"
    
    final_dest = dest_path / folder_name
    
    # Create parent directories if they don't exist
    dest_path.mkdir(parents=True, exist_ok=True)
    
    # Check if destination already exists
    if final_dest.exists():
        print_info(f"Destination already exists: {final_dest}")
        # Add a number suffix to avoid overwriting
        counter = 1
        while final_dest.exists():
            if suffix:
                test_name = f"{repo_parts[-1]}{suffix}_{counter}"
            else:
                test_name = f"{repo_parts[-1]}_{counter}"
            final_dest = dest_path / test_name
            counter += 1
        print_info(f"Using alternative name: {final_dest}")
    
    print_info(f"Restoring to: {final_dest}")
    
    # Move the folder to final destination
    shutil.move(str(source_folder), str(final_dest))
    
    print_success(f"Restored to: {final_dest}")
    
    return final_dest


def restore_from_github(repo_folder: str, suffix: Optional[str] = None) -> None:
    """
    Main restore function.
    
    Args:
        repo_folder: Path to folder in repository to restore
        suffix: Optional suffix to add to restored folder name
    """
    print_header("GitHub Chunked Backup Restore Utility")
    
    print(f"  → Repository: {REPO_URL}")
    print(f"  → Folder: {repo_folder}")
    if suffix:
        print(f"  → Name Suffix: {suffix}")
    
    temp_path = None
    
    try:
        # Step 0: Pre-flight checks
        print_section("Step 0] Pre-flight Checks")
        if not check_gh_cli():
            raise RestoreError("GitHub CLI setup required")
        
        # Step 1: Download chunks
        print_section("Step 1] Downloading from GitHub")
        temp_path, chunk_files = download_chunks(repo_folder, REPO_URL)
        
        # Step 2: Reassemble chunks
        print_section("Step 2] Reassembling Chunks")
        archive_file = reassemble_chunks(chunk_files, temp_path)
        
        # Step 3: Extract archive
        print_section("Step 3] Extracting Archive")
        extracted_folder = extract_archive(archive_file, temp_path)
        
        # Step 4: Restore to original location
        print_section("Step 4] Restoring to Original Location")
        final_path = restore_to_location(extracted_folder, repo_folder, suffix)
        
        # Success
        print_header("Restore Completed Successfully!")
        print(f"✓ Restored folder: {final_path}")
        print(f"  → Repository folder: {repo_folder}")
        
    except RestoreError as e:
        print_error(f"\nRestore failed: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print_error("\nRestore cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nUnexpected error: {str(e)}")
        sys.exit(1)
    finally:
        # Cleanup temporary files
        if temp_path and temp_path.exists():
            print_section("Step 5] Cleanup")
            print_info("Cleaning up temporary files...")
            try:
                shutil.rmtree(temp_path)
                print_success("Cleanup complete")
            except (PermissionError, OSError) as e:
                print_info(f"Note: Some temp files may remain at: {temp_path}")
                print_info("These will be cleaned up automatically by the system")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Restore files/folders from GitHub chunked backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Restore CloverPit folder
  python restore.py "Downloads/Compressed/Games/CloverPit"
  
  # Restore with a suffix to distinguish from original
  python restore.py "Downloads/Compressed/Games/CloverPit" --suffix "_restored"
  
  # Restore with a custom suffix
  python restore.py "Downloads/Compressed/Games/CloverPit" -s "_from_backup"

Notes:
  - The folder will be restored to its original location based on the repo path
  - If the path starts with "Downloads", it will restore to your Downloads folder
  - If the destination already exists, a number will be appended to avoid overwriting
  - Use --suffix to add a custom identifier to the restored folder name
        """
    )
    
    parser.add_argument(
        "repo_folder",
        help="Path to folder in GitHub repository (e.g., 'Downloads/Compressed/Games/CloverPit')"
    )
    
    parser.add_argument(
        "-s", "--suffix",
        help="Optional suffix to add to restored folder name (e.g., '_restored')",
        default=None
    )
    
    args = parser.parse_args()
    
    # Normalize path separators
    repo_folder = args.repo_folder.replace("\\", "/")
    
    restore_from_github(repo_folder, args.suffix)


if __name__ == "__main__":
    main()
