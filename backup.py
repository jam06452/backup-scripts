#!/usr/bin/env python3
"""
GitHub Chunked Backup Utility

Backs up large files or folders to GitHub by splitting them into 50MB chunks.
Uses the GitHub CLI (gh) for authentication.

Version: 1.0
Date: October 30, 2025
"""

import os
import sys
import subprocess
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, List
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue


# ============================================================================
# CONFIGURATION (Hardcoded as per PRD)
# ============================================================================

TARGET_REPO_URL = "https://github.com/jam06452/LargeFileStorage"
CHUNK_SIZE_MB = 50
CHUNK_SIZE_BYTES = CHUNK_SIZE_MB * 1024 * 1024  # 50MB = 52,428,800 bytes
TEMP_CHUNKS_FOLDER = "temp_split_chunks"


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

class BackupError(Exception):
    """Custom exception for backup errors."""
    pass


def print_header(message: str):
    """Print a formatted header message."""
    print(f"\n{'=' * 70}")
    print(f"  {message}")
    print(f"{'=' * 70}\n")


def print_step(step_num: int, message: str):
    """Print a step message."""
    print(f"\n[Step {step_num}] {message}")
    print("-" * 70)


def print_success(message: str):
    """Print a success message."""
    print(f"✓ {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"✗ ERROR: {message}", file=sys.stderr)


def print_info(message: str):
    """Print an info message."""
    print(f"  → {message}")


def get_existing_files_in_repo(repo_url: str, folder_path: str) -> set:
    """
    Get list of existing files in the GitHub repository using gh CLI.
    
    Args:
        repo_url: GitHub repository URL
        folder_path: Path in repo to check (e.g., "Downloads/HD5s")
        
    Returns:
        Set of relative file paths that exist in the repo
    """
    try:
        # Extract owner/repo from URL
        # https://github.com/jam06452/LargeFileStorage -> jam06452/LargeFileStorage
        repo_parts = repo_url.replace("https://github.com/", "").strip("/")
        
        # Use gh api to list files in the folder
        result = subprocess.run(
            ["gh", "api", f"repos/{repo_parts}/contents/{folder_path}", "--paginate"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            # Folder doesn't exist yet
            return set()
        
        import json
        existing_files = set()
        
        # Parse JSON response
        try:
            items = json.loads(result.stdout)
            if isinstance(items, list):
                for item in items:
                    if item.get("type") == "file":
                        # Extract just the filename
                        existing_files.add(item.get("name"))
        except json.JSONDecodeError:
            pass
        
        return existing_files
        
    except Exception as e:
        print_info(f"Could not check existing files: {e}")
        return set()


def check_gh_cli_installed() -> bool:
    """Check if GitHub CLI (gh) is installed."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_gh_authentication() -> bool:
    """Check if user is authenticated with GitHub CLI."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def get_file_size_mb(file_path: Path) -> float:
    """Get file size in MB."""
    size_bytes = file_path.stat().st_size
    return size_bytes / (1024 * 1024)


def create_archive(source_folder: Path, output_path: Path) -> None:
    """
    Create a ZIP archive from a folder.
    
    Args:
        source_folder: Path to the folder to archive
        output_path: Path where the ZIP file should be created
    """
    print_info(f"Creating archive: {output_path.name}")
    print_info(f"This may take a while for large folders...")
    
    try:
        file_count = 0
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            # Walk through the directory
            for root, dirs, files in os.walk(source_folder):
                for file in files:
                    file_path = Path(root) / file
                    # Calculate the archive name (relative path)
                    arcname = file_path.relative_to(source_folder.parent)
                    zipf.write(file_path, arcname)
                    file_count += 1
                    # Only print every 10th file to reduce output overhead
                    if file_count % 10 == 0 or file_count <= 5:
                        print_info(f"  Added {file_count} files...")
        
        size_mb = get_file_size_mb(output_path)
        print_success(f"Archive created: {output_path.name} ({size_mb:.2f} MB, {file_count} files)")
    except Exception as e:
        raise BackupError(f"Failed to create archive: {e}")


def split_file(source_file: Path, output_folder: Path) -> List[Path]:
    """
    Split a file into chunks of CHUNK_SIZE_BYTES.
    
    Args:
        source_file: Path to the file to split
        output_folder: Path to the folder where chunks will be saved
        
    Returns:
        List of paths to the created chunk files
    """
    output_folder.mkdir(parents=True, exist_ok=True)
    
    chunk_files = []
    chunk_num = 1
    
    file_size = source_file.stat().st_size
    total_chunks = (file_size + CHUNK_SIZE_BYTES - 1) // CHUNK_SIZE_BYTES
    
    print_info(f"File size: {get_file_size_mb(source_file):.2f} MB")
    print_info(f"Will create {total_chunks} chunk(s) of max {CHUNK_SIZE_MB} MB each")
    
    try:
        with open(source_file, 'rb') as f:
            while True:
                chunk_data = f.read(CHUNK_SIZE_BYTES)
                if not chunk_data:
                    break
                
                # Create chunk filename: basename.partXXX
                chunk_filename = f"{source_file.name}.part{chunk_num:03d}"
                chunk_path = output_folder / chunk_filename
                
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)
                
                chunk_size_mb = len(chunk_data) / (1024 * 1024)
                print_info(f"Created chunk {chunk_num}/{total_chunks}: {chunk_filename} ({chunk_size_mb:.2f} MB)")
                
                chunk_files.append(chunk_path)
                chunk_num += 1
        
        print_success(f"Created {len(chunk_files)} chunk file(s)")
        return chunk_files
        
    except Exception as e:
        raise BackupError(f"Failed to split file: {e}")


def upload_files_to_github(files_to_upload: List[tuple[Path, Path]], repo_url: str, source_path: Path) -> None:
    """
    Upload files to GitHub repository using gh CLI.
    Preserves the original folder structure in the repository.
    
    Args:
        files_to_upload: List of (actual_file_path, relative_path_in_repo) tuples
        repo_url: GitHub repository URL
        source_path: Original source path to extract folder structure from
    """
    # Create a temporary directory for git operations
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        repo_path = temp_path / "repo"
        
        print_info(f"Cloning repository to temporary location...")
        
        # Clone the repository
        try:
            result = subprocess.run(
                ["gh", "repo", "clone", repo_url, str(repo_path)],
                capture_output=True,
                text=True,
                check=True
            )
            print_success("Repository cloned")
        except subprocess.CalledProcessError as e:
            raise BackupError(f"Failed to clone repository: {e.stderr}")
        
        # Extract the folder structure from source path
        # e.g., C:\Users\Dan\Downloads\HD5s becomes: Downloads/HD5s
        source_parts = source_path.parts
        # Find "Downloads" in the path and take everything from there
        try:
            downloads_index = [p.lower() for p in source_parts].index('downloads')
            folder_parts = list(source_parts[downloads_index:])
        except ValueError:
            # If "Downloads" not found, just use the folder name
            folder_parts = [source_path.name]
        
        # Create base folder structure in repo
        base_dest_path = repo_path
        for folder_name in folder_parts:
            base_dest_path = base_dest_path / folder_name
        
        base_dest_path.mkdir(parents=True, exist_ok=True)
        print_success(f"Created base folder structure: {'/'.join(folder_parts)}")
        
        # Copy all files preserving structure
        print_info(f"Copying {len(files_to_upload)} file(s) to repository...")
        
        for i, (actual_file_path, rel_path) in enumerate(files_to_upload, 1):
            # Determine destination path in repo
            dest_path = base_dest_path / rel_path
            
            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(actual_file_path, dest_path)
            
            if i % 50 == 0 or i == len(files_to_upload) or i <= 10:
                print_info(f"  Copied {i}/{len(files_to_upload)} file(s)...")
        
        print_success(f"All files copied to repository")
        
        # Single batch commit and push for all files
        print_info("Committing and uploading files...")
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
            
            if len(files_to_upload) == 1:
                commit_msg = f"Add file: {files_to_upload[0][1]}"
            else:
                commit_msg = f"Add {len(files_to_upload)} files to {'/'.join(folder_parts)}"
            
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
            
            subprocess.run(
                ["git", "push"],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
            
            print_success(f"Successfully uploaded {len(files_to_upload)} file(s)")
        except subprocess.CalledProcessError as e:
            raise BackupError(f"Failed to upload: {e.stderr}")


def cleanup_temp_files(temp_folder: Path, temp_archive: Optional[Path]) -> None:
    """
    Clean up temporary files and folders.
    
    Args:
        temp_folder: Path to temporary folder
        temp_archive: Path to temporary archive file (if created)
    """
    print_info("Cleaning up temporary files...")
    
    # Delete temp chunks folder
    if temp_folder.exists():
        try:
            shutil.rmtree(temp_folder)
            print_success(f"Deleted: {temp_folder}")
        except Exception as e:
            print_error(f"Failed to delete temporary folder: {e}")
    
    # Delete temporary archive
    if temp_archive and temp_archive.exists():
        try:
            temp_archive.unlink()
            print_success(f"Deleted: {temp_archive.name}")
        except Exception as e:
            print_error(f"Failed to delete temporary archive: {e}")


# ============================================================================
# MAIN BACKUP FUNCTION
# ============================================================================

def process_and_upload_files(source: Path, repo_url: str, skip_folders: List[str] = None) -> None:
    """
    Process files and upload concurrently - split large files while uploading small ones.
    
    Args:
        source: Source file or folder
        repo_url: GitHub repository URL
        skip_folders: List of folder names to skip during backup
    """
    if skip_folders is None:
        skip_folders = []
    
    # Queue for files ready to upload: (actual_file_path, relative_path, is_temp)
    upload_queue = queue.Queue()
    upload_complete = threading.Event()
    upload_error = []
    
    # Statistics
    stats = {
        'total_files': 0,
        'files_split': 0,
        'files_uploaded': 0,
        'upload_lock': threading.Lock()
    }
    
    # Create temp folder if needed
    temp_folder = source.parent / TEMP_CHUNKS_FOLDER
    if temp_folder.exists():
        shutil.rmtree(temp_folder)
    temp_folder.mkdir(exist_ok=True)
    
    # Get folder structure for repo
    source_parts = source.parts
    try:
        downloads_index = [p.lower() for p in source_parts].index('downloads')
        folder_parts = list(source_parts[downloads_index:])
    except ValueError:
        folder_parts = [source.name]
    
    # DON'T clone/fetch - just init a fresh local repo and push to remote
    print_info("Setting up local repository...")
    temp_git_dir = tempfile.mkdtemp(prefix="git_repo_")
    repo_path = Path(temp_git_dir) / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Initialize new git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "backup-bot"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "backup@bot.local"], cwd=repo_path, capture_output=True, check=True)
        
        # Add remote
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=repo_path, capture_output=True, check=True)
        
        print_success("Repository ready")
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_git_dir)
        raise BackupError(f"Failed to setup repository: {e.stderr}")
    
    # Create base folder structure in repo locally (no push yet)
    print_info("Creating folder structure locally...")
    base_dest_path = repo_path
    
    for i, folder_name in enumerate(folder_parts):
        base_dest_path = base_dest_path / folder_name
        base_dest_path.mkdir(exist_ok=True)
        
        # Create .gitkeep to track this folder level (permanent marker)
        gitkeep = base_dest_path / ".gitkeep"
        gitkeep.touch()
        
        current_path = '/'.join(folder_parts[:i+1])
        print_info(f"  Creating: {current_path}")
    
    # Commit folder structure locally (no push yet)
    try:
        subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Create folder structure: {'/'.join(folder_parts)}"],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        # Might fail if nothing to commit (folder already exists)
        pass
    
    print_success(f"Created folder structure: {'/'.join(folder_parts)}")
    print_info("Keeping .gitkeep files at each folder level to preserve visible hierarchy on GitHub")
    
    # Keep the .gitkeep marker files in each level so GitHub's tree
    # view doesn't collapse single-child directories into a single
    # linked path like "HD5s/H5". Leaving these markers makes each
    # folder show as a separate, free-floating directory in the UI.
    print_info("Keeping marker files (.gitkeep) at each folder level to preserve visible hierarchy on GitHub")
    
    base_dest_path.mkdir(parents=True, exist_ok=True)
    
    def uploader_thread():
        """Background thread that uploads files as they become available"""
        batch = []
        batch_size = 20  # Push every 20 files
        last_push_time = 0
        push_interval = 30  # Or every 30 seconds
        
        try:
            while not upload_complete.is_set() or not upload_queue.empty():
                try:
                    # Get file to upload with timeout
                    file_info = upload_queue.get(timeout=0.5)
                    if file_info is None:  # Sentinel to stop
                        break
                    
                    actual_file_path, rel_path, is_temp = file_info
                    
                    # Copy to repo
                    dest_path = base_dest_path / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Ensure .gitkeep exists in parent directory (permanent marker)
                    gitkeep_path = dest_path.parent / ".gitkeep"
                    if not gitkeep_path.exists():
                        gitkeep_path.touch()
                    
                    shutil.copy2(actual_file_path, dest_path)
                    
                    batch.append(rel_path)
                    
                    with stats['upload_lock']:
                        stats['files_uploaded'] += 1
                        current_uploaded = stats['files_uploaded']
                    
                    upload_queue.task_done()
                    
                    # Push to GitHub when batch is full or time interval reached
                    import time
                    current_time = time.time()
                    should_push = (
                        len(batch) >= batch_size or 
                        (current_time - last_push_time >= push_interval and len(batch) > 0) or
                        upload_complete.is_set()  # Final push
                    )
                    
                    if should_push:
                        try:
                            # Add and commit batch
                            subprocess.run(
                                ["git", "add", "-A"],
                                cwd=repo_path,
                                capture_output=True,
                                check=True
                            )
                            
                            commit_msg = f"Add {len(batch)} file(s) ({current_uploaded} total)"
                            subprocess.run(
                                ["git", "commit", "-m", commit_msg],
                                cwd=repo_path,
                                capture_output=True,
                                check=True
                            )
                            
                            # Push - force on first push, then normal
                            push_result = subprocess.run(
                                ["git", "push", "-u", "origin", "master"],
                                cwd=repo_path,
                                capture_output=True,
                                check=False
                            )
                            
                            # If first push failed, try force push
                            if push_result.returncode != 0:
                                subprocess.run(
                                    ["git", "push", "-u", "origin", "master", "--force"],
                                    cwd=repo_path,
                                    capture_output=True,
                                    check=True
                                )
                            
                            print_info(f"  Pushed {len(batch)} file(s) to GitHub ({current_uploaded} total uploaded)")
                            
                            batch.clear()
                            last_push_time = current_time
                            
                        except subprocess.CalledProcessError as e:
                            upload_error.append(f"Git push failed: {e.stderr}")
                            break
                    
                except queue.Empty:
                    # Check if we should push accumulated files even if batch not full
                    import time
                    if len(batch) > 0 and time.time() - last_push_time >= push_interval:
                        try:
                            subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, check=True)
                            subprocess.run(["git", "commit", "-m", f"Add {len(batch)} file(s)"], cwd=repo_path, capture_output=True, check=True)
                            
                            push_result = subprocess.run(["git", "push"], cwd=repo_path, capture_output=True, check=False)
                            if push_result.returncode != 0:
                                subprocess.run(["git", "push", "-u", "origin", "master", "--force"], cwd=repo_path, capture_output=True, check=True)
                            
                            with stats['upload_lock']:
                                print_info(f"  Pushed {len(batch)} file(s) to GitHub ({stats['files_uploaded']} total)")
                            
                            batch.clear()
                            last_push_time = time.time()
                        except:
                            pass
                    continue
            
            # Final push of any remaining files
            if len(batch) > 0:
                try:
                    subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, check=True)
                    subprocess.run(["git", "commit", "-m", f"Add final {len(batch)} file(s)"], cwd=repo_path, capture_output=True, check=True)
                    
                    push_result = subprocess.run(["git", "push"], cwd=repo_path, capture_output=True, check=False)
                    if push_result.returncode != 0:
                        subprocess.run(["git", "push", "-u", "origin", "master", "--force"], cwd=repo_path, capture_output=True, check=True)
                    
                    with stats['upload_lock']:
                        print_info(f"  Pushed final {len(batch)} file(s) to GitHub ({stats['files_uploaded']} total)")
                except:
                    pass
                    
        except Exception as e:
            upload_error.append(str(e))
    
    # Start uploader thread
    uploader = threading.Thread(target=uploader_thread, daemon=True)
    uploader.start()
    
    if source.is_file():
        # Single file
        stats['total_files'] = 1
        file_size_mb = get_file_size_mb(source)
        
        if file_size_mb > CHUNK_SIZE_MB:
            print_info(f"File size: {file_size_mb:.2f} MB - splitting into chunks")
            chunk_files = split_file(source, temp_folder)
            stats['total_files'] = len(chunk_files)
            stats['files_split'] = 1
            
            for chunk in chunk_files:
                upload_queue.put((chunk, Path(chunk.name), True))
        else:
            print_info(f"File size: {file_size_mb:.2f} MB - uploading directly")
            upload_queue.put((source, Path(source.name), False))
    
    else:
        # Folder
        print_step(1, "Processing Folder Contents")
        
        # Get existing files from repo (by name only, no download needed)
        print_info("Checking for existing files in repository...")
        folder_path = '/'.join(folder_parts)
        existing_files_in_repo = get_existing_files_in_repo(repo_url, folder_path)
        if existing_files_in_repo:
            print_info(f"Found {len(existing_files_in_repo)} existing file(s) in repository")
        
        # Scan all files and check which already exist in repo
        all_files = []
        skipped_files = []
        for root, dirs, files in os.walk(source):
            # Skip folders in skip_folders list
            if skip_folders:
                dirs[:] = [d for d in dirs if d not in skip_folders]
            
            for file in files:
                file_path = Path(root) / file
                file_size_mb = get_file_size_mb(file_path)
                rel_path = file_path.relative_to(source)
                
                # Check if file already exists in repo by name
                # For large files, check if chunks exist (*.part001, *.part002, etc.)
                if file_size_mb > CHUNK_SIZE_MB:
                    # Check if first chunk exists - if so, assume file is uploaded
                    chunk_name = f"{file_path.name}.part001"
                    if chunk_name in existing_files_in_repo:
                        skipped_files.append(rel_path)
                        continue
                else:
                    # Small file - check exact name
                    if rel_path.name in existing_files_in_repo:
                        skipped_files.append(rel_path)
                        continue
                
                all_files.append((file_path, rel_path, file_size_mb))
        
        print_info(f"Found {len(all_files)} file(s) to upload")
        if skipped_files:
            print_info(f"Skipped {len(skipped_files)} file(s) already in repository")
        if skip_folders:
            print_info(f"Skipped folders: {', '.join(skip_folders)}")
        
        # Separate small and large files
        small_files = [(fp, rp) for fp, rp, size in all_files if size <= CHUNK_SIZE_MB]
        large_files = [(fp, rp, size) for fp, rp, size in all_files if size > CHUNK_SIZE_MB]
        
        # Start uploading small files immediately
        stats['total_files'] = len(all_files)
        print_info(f"Uploading {len(small_files)} small file(s) and splitting {len(large_files)} large file(s) concurrently...")
        
        for file_path, rel_path in small_files:
            upload_queue.put((file_path, rel_path, False))
        
        # Split large files in parallel and add chunks to upload queue
        if large_files:
            def split_and_queue(file_info):
                file_path, rel_path, file_size_mb = file_info
                print_info(f"  Splitting: {rel_path} ({file_size_mb:.2f} MB)")
                
                # Create subfolder for chunks
                chunk_dest_folder = temp_folder / rel_path.parent
                chunk_dest_folder.mkdir(parents=True, exist_ok=True)
                
                # Split file
                chunk_files = split_file(file_path, chunk_dest_folder)
                
                # Queue chunks for upload
                for chunk in chunk_files:
                    chunk_rel_path = rel_path.parent / chunk.name
                    upload_queue.put((chunk, chunk_rel_path, True))
                
                with stats['upload_lock']:
                    stats['files_split'] += 1
                    stats['total_files'] += len(chunk_files) - 1  # Adjust total (chunks replace original)
                
                return len(chunk_files)
            
            # Process large files with up to 4 parallel splits
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(split_and_queue, file_info) for file_info in large_files]
                
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print_error(f"Failed to split file: {e}")
    
    # Signal processing complete
    upload_complete.set()
    
    # Wait for all uploads to finish
    upload_queue.join()
    uploader.join(timeout=30)
    
    if upload_error:
        raise BackupError(f"Upload failed: {upload_error[0]}")
    
    print_success(f"All {stats['files_uploaded']} file(s) uploaded to GitHub")
    
    # Cleanup
    shutil.rmtree(temp_git_dir, ignore_errors=True)
    if temp_folder.exists():
        shutil.rmtree(temp_folder, ignore_errors=True)
    """
    Process files for upload - only split individual files larger than 50MB.
    Returns original file paths when possible to avoid duplicating disk space.
    
    For folders:
    - Upload files directly from source folder (no copying)
    - Only create temporary chunks for files over 50MB
    
    Args:
        source: Source file or folder
        
    Returns:
        Tuple of (temp_chunks_folder, list of (file_path, relative_path) tuples, needs_cleanup)
    """
    temp_folder = None
    files_to_upload = []  # List of (actual_file_path, relative_path_in_repo)
    
    if source.is_file():
        # Single file - check size
        file_size_mb = get_file_size_mb(source)
        if file_size_mb > CHUNK_SIZE_MB:
            print_info(f"File size: {file_size_mb:.2f} MB - splitting into chunks")
            temp_folder = source.parent / TEMP_CHUNKS_FOLDER
            if temp_folder.exists():
                shutil.rmtree(temp_folder)
            temp_folder.mkdir(exist_ok=True)
            
            chunk_files = split_file(source, temp_folder)
            for chunk in chunk_files:
                files_to_upload.append((chunk, Path(chunk.name)))
        else:
            print_info(f"File size: {file_size_mb:.2f} MB - uploading directly")
            files_to_upload.append((source, Path(source.name)))
        
        return temp_folder, files_to_upload, temp_folder is not None
    
    else:
        # Folder - process files without copying
        print_step(1, "Analyzing Folder Contents")
        
        # Find all files and categorize by size
        all_files = []
        large_files = []
        
        for root, dirs, files in os.walk(source):
            for file in files:
                file_path = Path(root) / file
                file_size_mb = get_file_size_mb(file_path)
                rel_path = file_path.relative_to(source)
                all_files.append((file_path, rel_path, file_size_mb))
                
                if file_size_mb > CHUNK_SIZE_MB:
                    large_files.append((file_path, rel_path, file_size_mb))
        
        print_info(f"Found {len(all_files)} file(s) in folder")
        
        if large_files:
            print_info(f"Found {len(large_files)} file(s) over {CHUNK_SIZE_MB} MB - will split only those")
            
            # Create temp folder for chunks
            temp_folder = source.parent / TEMP_CHUNKS_FOLDER
            if temp_folder.exists():
                shutil.rmtree(temp_folder)
            temp_folder.mkdir(exist_ok=True)
            
            # Track which files have been split
            split_files = set()
            
            def split_large_file(file_info):
                file_path, rel_path, file_size_mb = file_info
                print_info(f"  Splitting: {rel_path} ({file_size_mb:.2f} MB)")
                
                # Create subfolder in temp to preserve relative path structure
                chunk_dest_folder = temp_folder / rel_path.parent
                chunk_dest_folder.mkdir(parents=True, exist_ok=True)
                
                # Split the file into chunks
                chunk_files = split_file(file_path, chunk_dest_folder)
                
                # Return chunks with their relative paths (replacing original file)
                chunk_results = []
                for i, chunk in enumerate(chunk_files):
                    # Chunk relative path: same directory as original, but with chunk name
                    chunk_rel_path = rel_path.parent / chunk.name
                    chunk_results.append((chunk, chunk_rel_path))
                
                return file_path, chunk_results
            
            # Process large files in parallel (max 4 concurrent splits)
            print_info(f"Splitting large files concurrently...")
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(split_large_file, file_info): file_info for file_info in large_files}
                
                for future in as_completed(futures):
                    try:
                        original_file, chunk_results = future.result()
                        split_files.add(original_file)
                        files_to_upload.extend(chunk_results)
                    except Exception as e:
                        file_path, _, _ = futures[future]
                        print_error(f"Failed to split {file_path.name}: {e}")
            
            print_success(f"Split {len(large_files)} large file(s)")
        else:
            print_info(f"All files are under {CHUNK_SIZE_MB} MB - no splitting needed")
            split_files = set()
        
        # Add all non-split files for direct upload
        for file_path, rel_path, file_size_mb in all_files:
            if file_path not in split_files:
                files_to_upload.append((file_path, rel_path))
        
        print_success(f"Prepared {len(files_to_upload)} file(s) for upload")
        
        return temp_folder, files_to_upload, temp_folder is not None


def backup_to_github(source_path: str, skip_folders: List[str] = None) -> None:
    """
    Main backup function that orchestrates the entire backup process.
    
    Args:
        source_path: Path to file or folder to backup
        skip_folders: List of folder names to skip during backup
    """
    source = Path(source_path).resolve()
    
    try:
        # ===================================================================
        # STEP 0: Pre-flight Checks
        # ===================================================================
        print_header("GitHub Chunked Backup Utility")
        print_info(f"Source: {source}")
        print_info(f"Target Repository: {TARGET_REPO_URL}")
        print_info(f"Chunk Size: {CHUNK_SIZE_MB} MB")
        
        # Check if source exists
        if not source.exists():
            raise BackupError(f"Source path does not exist: {source}")
        
        # Check gh CLI
        print_step(0, "Pre-flight Checks")
        if not check_gh_cli_installed():
            raise BackupError(
                "GitHub CLI (gh) is not installed or not in PATH.\n"
                "Please install it from: https://cli.github.com/\n"
                "Then run: gh auth login"
            )
        print_success("GitHub CLI (gh) is installed")
        
        # Check authentication
        if not check_gh_authentication():
            raise BackupError(
                "Not authenticated with GitHub CLI.\n"
                "Please run: gh auth login"
            )
        print_success("GitHub CLI authentication verified")
        
        # ===================================================================
        # STEP 1 & 2: Process and Upload Files Concurrently
        # ===================================================================
        print_step(1, "Processing and Uploading Files")
        process_and_upload_files(source, TARGET_REPO_URL, skip_folders)
        
        # ===================================================================
        # SUCCESS
        # ===================================================================
        print_header("Backup Completed Successfully!")
        print_success(f"Original source preserved: {source}")
        print_info(f"Repository: {TARGET_REPO_URL}")
        
    except BackupError as e:
        print_error(str(e))
        sys.exit(1)
        
    except KeyboardInterrupt:
        print_error("Backup cancelled by user")
        sys.exit(1)
        
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Backup large files or folders to GitHub by splitting into 50MB chunks.",
        epilog=f"Target Repository: {TARGET_REPO_URL}"
    )
    
    parser.add_argument(
        "source",
        help="Path to the file or folder to backup"
    )
    
    parser.add_argument(
        "--skip-folders",
        nargs="+",
        default=[],
        help="Folder names to skip during backup (e.g., --skip-folders 'H5 Torrent' 'Other Folder')"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="GitHub Chunked Backup Utility v1.0"
    )
    
    args = parser.parse_args()
    
    backup_to_github(args.source, args.skip_folders)


if __name__ == "__main__":
    main()
