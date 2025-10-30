#!/usr/bin/env python3
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
TARGET_REPO_URL = 'https://github.com/jam06452/LargeFileStorage'
CHUNK_SIZE_MB = 50
CHUNK_SIZE_BYTES = CHUNK_SIZE_MB * 1024 * 1024
TEMP_CHUNKS_FOLDER = 'temp_split_chunks'
BATCH_SIZE = 20
PUSH_INTERVAL = 30
MAX_WORKERS = 4
BYTES_PER_MB = 1024 * 1024

class BackupError(Exception):
    pass

def run_git(cmd: List[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(['git'] + cmd, cwd=cwd, capture_output=True, check=check)

def git_push(repo_path: Path, force: bool = False) -> bool:
    cmd = ['push', '-u', 'origin', 'master'] if force else ['push']
    if force:
        cmd.append('--force')
    result = run_git(cmd, repo_path, check=False)
    if result.returncode != 0 and not force:
        return git_push(repo_path, force=True)
    return result.returncode == 0

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def create_gitkeep(path: Path) -> None:
    (path / '.gitkeep').touch()

def extract_folder_parts(source: Path) -> List[str]:
    try:
        downloads_index = [p.lower() for p in source.parts].index('downloads')
        return list(source.parts[downloads_index:])
    except ValueError:
        return [source.name]

def setup_git_repo(repo_url: str) -> Path:
    temp_git_dir = tempfile.mkdtemp(prefix='git_repo_')
    repo_path = Path(temp_git_dir) / 'repo'
    ensure_dir(repo_path)
    try:
        run_git(['init'], repo_path)
        run_git(['config', 'user.name', 'backup-bot'], repo_path)
        run_git(['config', 'user.email', 'backup@bot.local'], repo_path)
        run_git(['remote', 'add', 'origin', repo_url], repo_path)
        return repo_path
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_git_dir)
        raise BackupError(f'Failed to setup repository: {e.stderr}')

def create_folder_structure(repo_path: Path, folder_parts: List[str]) -> Path:
    base_dest_path = repo_path
    for folder_name in folder_parts:
        base_dest_path = base_dest_path / folder_name
        ensure_dir(base_dest_path)
        create_gitkeep(base_dest_path)
    try:
        run_git(['add', '-A'], repo_path)
        run_git(['commit', '-m', f"Create folder structure: {'/'.join(folder_parts)}"], repo_path)
    except subprocess.CalledProcessError:
        pass
    return base_dest_path

def is_large_file(file_path: Path) -> bool:
    return get_file_size_mb(file_path) > CHUNK_SIZE_MB

def print_header(message: str):
    print(f"\n{'=' * 70}")
    print(f'  {message}')
    print(f"{'=' * 70}\n")

def print_step(step_num: int, message: str):
    print(f'\n[Step {step_num}] {message}')
    print('-' * 70)

def print_success(message: str):
    print(f'✓ {message}')

def print_error(message: str):
    print(f'✗ ERROR: {message}', file=sys.stderr)

def print_info(message: str):
    print(f'  → {message}')

def get_existing_files_in_repo(repo_url: str, folder_path: str) -> set:
    try:
        repo_parts = repo_url.replace('https://github.com/', '').strip('/')
        result = subprocess.run(['gh', 'api', f'repos/{repo_parts}/contents/{folder_path}', '--paginate'], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return set()
        import json
        existing_files = set()
        try:
            items = json.loads(result.stdout)
            if isinstance(items, list):
                for item in items:
                    if item.get('type') == 'file':
                        existing_files.add(item.get('name'))
        except json.JSONDecodeError:
            pass
        return existing_files
    except Exception as e:
        print_info(f'Could not check existing files: {e}')
        return set()

def check_gh_cli_installed() -> bool:
    try:
        result = subprocess.run(['gh', '--version'], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def check_gh_authentication() -> bool:
    try:
        result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except Exception:
        return False

def get_file_size_mb(file_path: Path) -> float:
    return file_path.stat().st_size / BYTES_PER_MB

def create_archive(source_folder: Path, output_path: Path) -> None:
    print_info(f'Creating archive: {output_path.name}')
    print_info(f'This may take a while for large folders...')
    try:
        file_count = 0
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            for (root, dirs, files) in os.walk(source_folder):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(source_folder.parent)
                    zipf.write(file_path, arcname)
                    file_count += 1
                    if file_count % 10 == 0 or file_count <= 5:
                        print_info(f'  Added {file_count} files...')
        size_mb = get_file_size_mb(output_path)
        print_success(f'Archive created: {output_path.name} ({size_mb:.2f} MB, {file_count} files)')
    except Exception as e:
        raise BackupError(f'Failed to create archive: {e}')

def split_file(source_file: Path, output_folder: Path) -> List[Path]:
    ensure_dir(output_folder)
    chunk_files = []
    chunk_num = 1
    file_size = source_file.stat().st_size
    total_chunks = (file_size + CHUNK_SIZE_BYTES - 1) // CHUNK_SIZE_BYTES
    try:
        with open(source_file, 'rb') as f:
            while True:
                chunk_data = f.read(CHUNK_SIZE_BYTES)
                if not chunk_data:
                    break
                chunk_filename = f'{source_file.name}.part{chunk_num:03d}'
                chunk_path = output_folder / chunk_filename
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)
                chunk_files.append(chunk_path)
                chunk_num += 1
        return chunk_files
    except Exception as e:
        raise BackupError(f'Failed to split file: {e}')

def upload_files_to_github(files_to_upload: List[tuple[Path, Path]], repo_url: str, source_path: Path) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        repo_path = temp_path / 'repo'
        print_info(f'Cloning repository to temporary location...')
        try:
            result = subprocess.run(['gh', 'repo', 'clone', repo_url, str(repo_path)], capture_output=True, text=True, check=True)
            print_success('Repository cloned')
        except subprocess.CalledProcessError as e:
            raise BackupError(f'Failed to clone repository: {e.stderr}')
        source_parts = source_path.parts
        try:
            downloads_index = [p.lower() for p in source_parts].index('downloads')
            folder_parts = list(source_parts[downloads_index:])
        except ValueError:
            folder_parts = [source_path.name]
        base_dest_path = repo_path
        for folder_name in folder_parts:
            base_dest_path = base_dest_path / folder_name
        base_dest_path.mkdir(parents=True, exist_ok=True)
        print_success(f"Created base folder structure: {'/'.join(folder_parts)}")
        print_info(f'Copying {len(files_to_upload)} file(s) to repository...')
        for (i, (actual_file_path, rel_path)) in enumerate(files_to_upload, 1):
            dest_path = base_dest_path / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actual_file_path, dest_path)
            if i % 50 == 0 or i == len(files_to_upload) or i <= 10:
                print_info(f'  Copied {i}/{len(files_to_upload)} file(s)...')
        print_success(f'All files copied to repository')
        print_info('Committing and uploading files...')
        try:
            subprocess.run(['git', 'add', '-A'], cwd=repo_path, capture_output=True, check=True)
            if len(files_to_upload) == 1:
                commit_msg = f'Add file: {files_to_upload[0][1]}'
            else:
                commit_msg = f"Add {len(files_to_upload)} files to {'/'.join(folder_parts)}"
            subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_path, capture_output=True, check=True)
            subprocess.run(['git', 'push'], cwd=repo_path, capture_output=True, check=True)
            print_success(f'Successfully uploaded {len(files_to_upload)} file(s)')
        except subprocess.CalledProcessError as e:
            raise BackupError(f'Failed to upload: {e.stderr}')

def cleanup_temp_files(temp_folder: Path, temp_archive: Optional[Path]) -> None:
    print_info('Cleaning up temporary files...')
    if temp_folder.exists():
        try:
            shutil.rmtree(temp_folder)
            print_success(f'Deleted: {temp_folder}')
        except Exception as e:
            print_error(f'Failed to delete temporary folder: {e}')
    if temp_archive and temp_archive.exists():
        try:
            temp_archive.unlink()
            print_success(f'Deleted: {temp_archive.name}')
        except Exception as e:
            print_error(f'Failed to delete temporary archive: {e}')

def process_and_upload_files(source: Path, repo_url: str, skip_folders: List[str]=None) -> None:
    if skip_folders is None:
        skip_folders = []
    upload_queue = queue.Queue()
    upload_complete = threading.Event()
    upload_error = []
    stats = {'total_files': 0, 'files_split': 0, 'files_uploaded': 0, 'upload_lock': threading.Lock()}
    temp_folder = source.parent / TEMP_CHUNKS_FOLDER
    if temp_folder.exists():
        shutil.rmtree(temp_folder)
    temp_folder.mkdir(exist_ok=True)
    
    folder_parts = extract_folder_parts(source)
    
    print_info('Setting up local repository...')
    repo_path = setup_git_repo(repo_url)
    print_success('Repository ready')
    
    print_info('Creating folder structure locally...')
    base_dest_path = create_folder_structure(repo_path, folder_parts)
    print_success(f"Created folder structure: {'/'.join(folder_parts)}")
    ensure_dir(base_dest_path)

    def uploader_thread():
        batch = []
        last_push_time = 0
        try:
            while not upload_complete.is_set() or not upload_queue.empty():
                try:
                    file_info = upload_queue.get(timeout=0.5)
                    if file_info is None:
                        break
                    (actual_file_path, rel_path, is_temp) = file_info
                    dest_path = base_dest_path / rel_path
                    ensure_dir(dest_path.parent)
                    create_gitkeep(dest_path.parent)
                    shutil.copy2(actual_file_path, dest_path)
                    batch.append(rel_path)
                    with stats['upload_lock']:
                        stats['files_uploaded'] += 1
                        current_uploaded = stats['files_uploaded']
                    upload_queue.task_done()
                    import time
                    current_time = time.time()
                    should_push = len(batch) >= BATCH_SIZE or (current_time - last_push_time >= PUSH_INTERVAL and len(batch) > 0) or upload_complete.is_set()
                    if should_push:
                        try:
                            run_git(['add', '-A'], repo_path)
                            run_git(['commit', '-m', f'Add {len(batch)} file(s) ({current_uploaded} total)'], repo_path)
                            git_push(repo_path)
                            batch.clear()
                            last_push_time = current_time
                        except subprocess.CalledProcessError as e:
                            upload_error.append(f'Git push failed: {e.stderr}')
                            break
                except queue.Empty:
                    import time
                    if len(batch) > 0 and time.time() - last_push_time >= PUSH_INTERVAL:
                        try:
                            run_git(['add', '-A'], repo_path)
                            run_git(['commit', '-m', f'Add {len(batch)} file(s)'], repo_path)
                            git_push(repo_path)
                            with stats['upload_lock']:
                                print(f"✓ Pushed batch ({stats['files_uploaded']} total)")
                            batch.clear()
                            last_push_time = time.time()
                        except:
                            pass
                    continue
            if len(batch) > 0:
                try:
                    run_git(['add', '-A'], repo_path)
                    run_git(['commit', '-m', f'Add final {len(batch)} file(s)'], repo_path)
                    git_push(repo_path)
                    with stats['upload_lock']:
                        print(f"✓ Final push ({stats['files_uploaded']} total)")
                except:
                    pass
        except Exception as e:
            upload_error.append(str(e))
    uploader = threading.Thread(target=uploader_thread, daemon=True)
    uploader.start()
    if source.is_file():
        stats['total_files'] = 1
        file_size_mb = get_file_size_mb(source)
        if is_large_file(source):
            print_info(f'File size: {file_size_mb:.2f} MB - splitting into chunks')
            chunk_files = split_file(source, temp_folder)
            stats['total_files'] = len(chunk_files)
            stats['files_split'] = 1
            for chunk in chunk_files:
                upload_queue.put((chunk, Path(chunk.name), True))
        else:
            print_info(f'File size: {file_size_mb:.2f} MB - uploading directly')
            upload_queue.put((source, Path(source.name), False))
    else:
        print_step(1, 'Processing Folder Contents')
        print_info('Checking for existing files in repository...')
        folder_path = '/'.join(folder_parts)
        existing_files_in_repo = get_existing_files_in_repo(repo_url, folder_path)
        if existing_files_in_repo:
            print_info(f'Found {len(existing_files_in_repo)} existing file(s) in repository')
        all_files = []
        skipped_files = []
        for (root, dirs, files) in os.walk(source):
            if skip_folders:
                dirs[:] = [d for d in dirs if d not in skip_folders]
            for file in files:
                file_path = Path(root) / file
                file_size_mb = get_file_size_mb(file_path)
                rel_path = file_path.relative_to(source)
                if is_large_file(file_path):
                    chunk_name = f'{file_path.name}.part001'
                    if chunk_name in existing_files_in_repo:
                        skipped_files.append(rel_path)
                        continue
                elif rel_path.name in existing_files_in_repo:
                    skipped_files.append(rel_path)
                    continue
                all_files.append((file_path, rel_path, file_size_mb))
        print_info(f'Found {len(all_files)} file(s) to upload')
        if skipped_files:
            print_info(f'Skipped {len(skipped_files)} file(s) already in repository')
        if skip_folders:
            print_info(f"Skipped folders: {', '.join(skip_folders)}")
        small_files = [(fp, rp) for (fp, rp, size) in all_files if not is_large_file(fp)]
        large_files = [(fp, rp, size) for (fp, rp, size) in all_files if is_large_file(fp)]
        stats['total_files'] = len(all_files)
        print_info(f'Uploading {len(small_files)} small file(s) and splitting {len(large_files)} large file(s) concurrently...')
        for (file_path, rel_path) in small_files:
            upload_queue.put((file_path, rel_path, False))
        if large_files:

            def split_and_queue(file_info):
                (file_path, rel_path, file_size_mb) = file_info
                chunk_dest_folder = temp_folder / rel_path.parent
                ensure_dir(chunk_dest_folder)
                chunk_files = split_file(file_path, chunk_dest_folder)
                for chunk in chunk_files:
                    chunk_rel_path = rel_path.parent / chunk.name
                    upload_queue.put((chunk, chunk_rel_path, True))
                with stats['upload_lock']:
                    stats['files_split'] += 1
                    stats['total_files'] += len(chunk_files) - 1
                return len(chunk_files)
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(split_and_queue, file_info) for file_info in large_files]
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print_error(f'Failed to split file: {e}')
    upload_complete.set()
    upload_queue.join()
    uploader.join(timeout=30)
    if upload_error:
        raise BackupError(f'Upload failed: {upload_error[0]}')
    print_success(f"All {stats['files_uploaded']} file(s) uploaded to GitHub")
    shutil.rmtree(repo_path.parent, ignore_errors=True)
    if temp_folder.exists():
        shutil.rmtree(temp_folder, ignore_errors=True)

def backup_to_github(source_path: str, skip_folders: List[str]=None) -> None:
    source = Path(source_path).resolve()
    try:
        print_header('GitHub Chunked Backup Utility')
        print_info(f'Source: {source}')
        print_info(f'Target Repository: {TARGET_REPO_URL}')
        print_info(f'Chunk Size: {CHUNK_SIZE_MB} MB')
        if not source.exists():
            raise BackupError(f'Source path does not exist: {source}')
        print_step(0, 'Pre-flight Checks')
        if not check_gh_cli_installed():
            raise BackupError('GitHub CLI (gh) is not installed or not in PATH.\nPlease install it from: https://cli.github.com/\nThen run: gh auth login')
        print_success('GitHub CLI (gh) is installed')
        if not check_gh_authentication():
            raise BackupError('Not authenticated with GitHub CLI.\nPlease run: gh auth login')
        print_success('GitHub CLI authentication verified')
        print_step(1, 'Processing and Uploading Files')
        process_and_upload_files(source, TARGET_REPO_URL, skip_folders)
        print_header('Backup Completed Successfully!')
        print_success(f'Original source preserved: {source}')
        print_info(f'Repository: {TARGET_REPO_URL}')
    except BackupError as e:
        print_error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print_error('Backup cancelled by user')
        sys.exit(1)
    except Exception as e:
        print_error(f'Unexpected error: {e}')
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Backup large files or folders to GitHub by splitting into 50MB chunks.', epilog=f'Target Repository: {TARGET_REPO_URL}')
    parser.add_argument('source', help='Path to the file or folder to backup')
    parser.add_argument('--skip-folders', nargs='+', default=[], help="Folder names to skip during backup (e.g., --skip-folders 'H5 Torrent' 'Other Folder')")
    parser.add_argument('--version', action='version', version='GitHub Chunked Backup Utility v1.0')
    args = parser.parse_args()
    backup_to_github(args.source, args.skip_folders)
if __name__ == '__main__':
    main()
