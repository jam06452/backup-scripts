# GitHub Chunked Backup Utility

A Python-based backup and restore system for managing large files on GitHub by automatically splitting them into 50MB chunks.

## Features

- Automatic file chunking (50MB per chunk)
- Concurrent file processing (4 parallel workers)
- Progress tracking with percentage display
- Skip existing files (incremental backups)
- Incomplete chunk detection and re-upload
- SHA256 verification on restore
- Zero disk duplication (direct source file access)
- Batch uploads (20 files or 30 second intervals)

## Requirements

- Python 3.7+
- GitHub CLI (`gh`) installed and authenticated
- Git

## Setup

1. Install GitHub CLI: https://cli.github.com/
2. Authenticate with GitHub:
   ```bash
   gh auth login
   ```

## Backup Commands

### Basic Backup
```bash
python backup.py "C:\path\to\folder"
```

### Backup Single File
```bash
python backup.py "C:\path\to\large_file.zip"
```

### Skip Specific Folders
```bash
python backup.py "C:\path\to\folder" --skip-folders "FolderName1" "FolderName2"
```

### Examples
```bash
# Backup entire Downloads folder
python backup.py "C:\Users\YourName\Downloads"

# Backup with exclusions
python backup.py "C:\Data" --skip-folders "temp" "cache" "logs"

# Backup a single large file
python backup.py "C:\archive.zip"
```

## Restore Commands

### List Available Backups
```bash
python restore.py --list
```

### Restore Specific Folder
```bash
python restore.py "Downloads/Compressed/FolderName"
```

### Restore to Custom Location
```bash
python restore.py "Downloads/Compressed/FolderName" --output "D:\Restored"
```

### Restore with Custom Repository
```bash
python restore.py "path/in/repo" --repo "https://github.com/username/repo"
```

### Examples
```bash
# List all available backups
python restore.py --list

# Restore CrosshairX folder
python restore.py "Downloads/Compressed/CrosshairX"

# Restore to specific location
python restore.py "Downloads/Compressed/CrosshairX" --output "D:\Games\CrosshairX"

# Restore from different repository
python restore.py "path/to/backup" --repo "https://github.com/user/other-repo"
```

## Configuration

Edit the constants in `backup.py`:

```python
TARGET_REPO_URL = 'https://github.com/username/LargeFileStorage'  # Target repository
CHUNK_SIZE_MB = 50        # Size of each chunk in MB
BATCH_SIZE = 20           # Files per batch commit
PUSH_INTERVAL = 30        # Seconds between automatic pushes
MAX_WORKERS = 4           # Concurrent file splitting workers
```

## How It Works

### Backup Process
1. Checks GitHub CLI authentication
2. Creates local git repository structure
3. Scans source for files
4. Checks repository for existing files (skips duplicates)
5. Validates existing chunks (detects incomplete sequences)
6. Splits large files (>50MB) into chunks concurrently
7. Uploads files in batches with progress tracking
8. Cleans up temporary files

### Restore Process
1. Clones repository to temporary location
2. Locates all chunk files for requested path
3. Downloads and reassembles chunks
4. Verifies SHA256 checksums (for chunked files)
5. Copies restored files to output directory
6. Cleans up temporary files

## Output Format

### Backup Output
```
[BACKUP] Source: FolderName
[BACKUP] Target: https://github.com/user/repo
  > Setting up local repository...
[OK] Repository ready
  > Found 390 file(s) to upload
  > Uploading 388 small file(s) and splitting 2 large file(s) concurrently...
[UPLOAD] Progress: 45.2% (180/398)
[UPLOAD] Progress: 100.0% (398/398)
[OK] All 398 file(s) uploaded to GitHub
[OK] Backup complete!
```

### Restore Output
```
  > Cloning repository...
[OK] Repository cloned
  > Found 7 chunk(s) for reassembly
  > Reassembling chunks...
[OK] SHA256 verified
[OK] Restored: large_file.zip
```

## Error Handling

- **Missing GitHub CLI**: Install from https://cli.github.com/
- **Not Authenticated**: Run `gh auth login`
- **Source Not Found**: Check file/folder path
- **Upload Failed**: Auto-retries with force push if needed
- **Incomplete Chunks**: Automatically detected and re-uploaded
- **SHA256 Mismatch**: Corruption detected during restore

## Repository Structure

After backup, files are organized as:
```
repo/
└── Downloads/
    └── Compressed/
        └── FolderName/
            ├── file1.txt
            ├── file2.jpg
            ├── largefile.zip.part001
            ├── largefile.zip.part002
            └── largefile.zip.part003
```

## Tips

- Use `--skip-folders` to exclude temporary or cache directories
- Large folders are processed incrementally (can resume if interrupted)
- Existing files are automatically skipped (fast incremental backups)
- Progress percentage helps estimate completion time
- Restore validates data integrity via SHA256 checksums

## Version

GitHub Chunked Backup Utility v1.0
