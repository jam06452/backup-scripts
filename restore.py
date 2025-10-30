#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

REPO_URL = 'https://github.com/jam06452/LargeFileStorage'
BUFFER_SIZE = 8 * 1024 * 1024
BYTES_PER_MB = 1024 * 1024

class RestoreError(Exception):
    pass

def run_cmd(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

def print_msg(text: str, prefix: str = '  → ') -> None:
    print(f'{prefix}{text}', file=sys.stderr if prefix == '✗ ' else sys.stdout)

def check_gh_cli() -> bool:
    try:
        result = subprocess.run(['gh', '--version'], capture_output=True, text=True, check=True)
        print_msg("GitHub CLI (gh) is installed", " ")
        result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            print_msg("GitHub CLI authentication verified", " ")
            return True
        else:
            print_msg("GitHub CLI is not authenticated", " ")
            print_msg('Please run: gh auth login')
            return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_msg("GitHub CLI (gh) is not installed", " ")
        print_msg('Install from: https://cli.github.com/')
        return False

def download_chunks(repo_folder: str, repo_url: str) -> tuple[Path, List[Path]]:
    temp_dir = tempfile.mkdtemp(prefix='restore_')
    temp_path = Path(temp_dir)
    repo_path = temp_path / 'repo'
    print_msg(f'Cloning repository to temporary location...')
    try:
        subprocess.run(['gh', 'repo', 'clone', repo_url, str(repo_path)], capture_output=True, text=True, check=True)
        print_msg("Repository cloned", " ")
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir)
        raise RestoreError(f'Failed to clone repository: {e.stderr}')
    folder_path = repo_path / repo_folder
    if not folder_path.exists():
        shutil.rmtree(temp_dir)
        raise RestoreError(f'Folder not found in repository: {repo_folder}')
    chunk_files = sorted(folder_path.glob('*.part*'))
    if not chunk_files:
        shutil.rmtree(temp_dir)
        raise RestoreError(f'No chunk files found in: {repo_folder}')
    print_msg("Found {len(chunk_files)} chunk file(s)", " ")
    return (temp_path, chunk_files)

def reassemble_chunks(chunk_files: List[Path], output_dir: Path) -> Path:
    base_name = chunk_files[0].name
    if '.part' in base_name:
        base_name = base_name.rsplit('.part', 1)[0]
    output_file = output_dir / base_name
    print_msg(f'Reassembling {len(chunk_files)} chunk(s) into: {base_name}')
    buffer_size = 8 * 1024 * 1024
    with open(output_file, 'wb') as outfile:
        for (i, chunk_file) in enumerate(chunk_files, 1):
            if i % 5 == 0 or i == len(chunk_files) or i == 1:
                print_msg(f'  Reading chunk {i}/{len(chunk_files)}...')
            with open(chunk_file, 'rb') as infile:
                shutil.copyfileobj(infile, outfile, length=buffer_size)
    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print_msg("Reassembled archive: {base_name} ({file_size_mb:.2f} MB)", " ")
    return output_file

def extract_archive(archive_file: Path, extract_dir: Path) -> Path:
    print_msg(f'Extracting archive: {archive_file.name}')
    try:
        with zipfile.ZipFile(archive_file, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            zip_ref.extractall(extract_dir)
            print_msg("Extracted {len(file_list)} file(s)", " ")
            if file_list:
                first_file = Path(file_list[0])
                top_level = first_file.parts[0]
                extracted_folder = extract_dir / top_level
                if extracted_folder.exists():
                    return extracted_folder
            return extract_dir
    except zipfile.BadZipFile:
        raise RestoreError(f'Invalid or corrupted ZIP file: {archive_file.name}')
    except Exception as e:
        raise RestoreError(f'Failed to extract archive: {str(e)}')

def restore_to_location(source_folder: Path, repo_folder_path: str, suffix: Optional[str]=None) -> Path:
    repo_parts = Path(repo_folder_path).parts
    if repo_parts[0].lower() == 'downloads':
        base_path = Path.home() / 'Downloads'
        dest_parts = repo_parts[1:]
    else:
        base_path = Path.home()
        dest_parts = repo_parts
    dest_path = base_path
    for part in dest_parts[:-1]:
        dest_path = dest_path / part
    folder_name = repo_parts[-1]
    if suffix:
        folder_name = f'{folder_name}{suffix}'
    final_dest = dest_path / folder_name
    dest_path.mkdir(parents=True, exist_ok=True)
    if final_dest.exists():
        print_msg(f'Destination already exists: {final_dest}')
        counter = 1
        while final_dest.exists():
            if suffix:
                test_name = f'{repo_parts[-1]}{suffix}_{counter}'
            else:
                test_name = f'{repo_parts[-1]}_{counter}'
            final_dest = dest_path / test_name
            counter += 1
        print_msg(f'Using alternative name: {final_dest}')
    print_msg(f'Restoring to: {final_dest}')
    shutil.move(str(source_folder), str(final_dest))
    print_msg("Restored to: {final_dest}", " ")
    return final_dest

def restore_from_github(repo_folder: str, suffix: Optional[str]=None) -> None:
    print(f"\n{'='*70}\n  GitHub Chunked Backup Restore Utility\n{'='*70}\n")
    print(f'  → Repository: {REPO_URL}')
    print(f'  → Folder: {repo_folder}')
    if suffix:
        print(f'  → Name Suffix: {suffix}')
    temp_path = None
    try:
        print(f"\n[Step 0] Pre-flight Checks]\n{'-'*70}")
        if not check_gh_cli():
            raise RestoreError('GitHub CLI setup required')
        print(f"\n[Step 1] Downloading from GitHub]\n{'-'*70}")
        (temp_path, chunk_files) = download_chunks(repo_folder, REPO_URL)
        print(f"\n[Step 2] Reassembling Chunks]\n{'-'*70}")
        archive_file = reassemble_chunks(chunk_files, temp_path)
        print(f"\n[Step 3] Extracting Archive]\n{'-'*70}")
        extracted_folder = extract_archive(archive_file, temp_path)
        print(f"\n[Step 4] Restoring to Original Location]\n{'-'*70}")
        final_path = restore_to_location(extracted_folder, repo_folder, suffix)
        print(f"\n{'='*70}\n  Restore Completed Successfully!\n{'='*70}\n")
        print(f'✓ Restored folder: {final_path}')
        print(f'  → Repository folder: {repo_folder}')
    except RestoreError as e:
        print_msg("\nRestore failed: {str(e)}", " ")
        sys.exit(1)
    except KeyboardInterrupt:
        print_msg("\nRestore cancelled by user", " ")
        sys.exit(1)
    except Exception as e:
        print_msg("\nUnexpected error: {str(e)}", " ")
        sys.exit(1)
    finally:
        if temp_path and temp_path.exists():
            print(f"\n[Step 5] Cleanup]\n{'-'*70}")
            print_msg('Cleaning up temporary files...')
            try:
                shutil.rmtree(temp_path)
                print_msg("Cleanup complete", " ")
            except (PermissionError, OSError) as e:
                print_msg(f'Note: Some temp files may remain at: {temp_path}')
                print_msg('These will be cleaned up automatically by the system')

def main():
    parser = argparse.ArgumentParser(description='Restore files/folders from GitHub chunked backup', formatter_class=argparse.RawDescriptionHelpFormatter, epilog='\nExamples:\n  # Restore CloverPit folder\n  python restore.py "Downloads/Compressed/Games/CloverPit"\n  \n  # Restore with a suffix to distinguish from original\n  python restore.py "Downloads/Compressed/Games/CloverPit" --suffix "_restored"\n  \n  # Restore with a custom suffix\n  python restore.py "Downloads/Compressed/Games/CloverPit" -s "_from_backup"\n\nNotes:\n  - The folder will be restored to its original location based on the repo path\n  - If the path starts with "Downloads", it will restore to your Downloads folder\n  - If the destination already exists, a number will be appended to avoid overwriting\n  - Use --suffix to add a custom identifier to the restored folder name\n        ')
    parser.add_argument('repo_folder', help="Path to folder in GitHub repository (e.g., 'Downloads/Compressed/Games/CloverPit')")
    parser.add_argument('-s', '--suffix', help="Optional suffix to add to restored folder name (e.g., '_restored')", default=None)
    args = parser.parse_args()
    repo_folder = args.repo_folder.replace('\\', '/')
    restore_from_github(repo_folder, args.suffix)
if __name__ == '__main__':
    main()

