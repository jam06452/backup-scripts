# GitHub Chunked Backup Utility

A command-line utility for backing up large files or folders to GitHub by automatically splitting them into 50MB chunks.

## Overview

This utility solves GitHub's file size limitations by:
- Automatically compressing folders into archives
- Splitting large files into 50MB chunks
- Uploading chunks to your GitHub repository using the GitHub CLI
- Cleaning up all temporary data while preserving your original files

**Target Repository:** `https://github.com/jam06452/LargeFileStorage`

## Features

✅ **Backup:** Single files or entire folders  
✅ **Restore:** Download and reassemble backed up files  
✅ Automatic folder compression (ZIP format)  
✅ Smart chunking (50MB max per file)  
✅ Uses your existing `gh` CLI authentication  
✅ Automatic cleanup of temporary files  
✅ Original source files remain untouched  
✅ Detailed progress reporting  

## Requirements

### System Requirements
- Windows, macOS, or Linux
- Python 3.7 or higher
- GitHub CLI (`gh`) installed and authenticated

### Installation

1. **Install GitHub CLI** (if not already installed):
   - Windows: `winget install GitHub.cli`
   - macOS: `brew install gh`
   - Linux: See [GitHub CLI installation guide](https://github.com/cli/cli#installation)

2. **Authenticate with GitHub CLI:**
   ```powershell
   gh auth login
   ```

3. **Install Python dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

## Usage

### Backup

**Basic Syntax:**
```powershell
python backup.py <source_path>
```

**Examples:**

Backup a single file:
```powershell
python backup.py "C:\backups\my_archive.zip"
```

Backup an entire folder:
```powershell
python backup.py "C:\Users\Dan\Downloads\Compressed\Games\CloverPit"
```

### Restore

**Basic Syntax:**
```powershell
python restore.py <repo_folder> [--suffix SUFFIX]
```

**Examples:**

Restore CloverPit folder:
```powershell
python restore.py "Downloads/Compressed/Games/CloverPit"
```

Restore with a suffix to distinguish from original:
```powershell
python restore.py "Downloads/Compressed/Games/CloverPit" --suffix "_restored"
```

Restore with custom suffix:
```powershell
python restore.py "Downloads/Compressed/Games/CloverPit" -s "_from_backup"
```

**Restore Notes:**
- The folder will be restored to its original location based on the repo path
- If the path starts with "Downloads", it restores to your Downloads folder
- If the destination already exists, a number is appended to avoid overwriting
- Use `--suffix` to add a custom identifier to the restored folder name

## How It Works

### Backup Process Flow

1. **Input Validation**
   - Checks if source path exists
   - Verifies `gh` CLI is installed and authenticated

2. **Archiving (if folder)**
   - If source is a folder, creates a temporary ZIP archive
   - Archive is created in the same directory as the source

3. **Splitting**
   - Creates a temporary `temp_split_chunks` folder
   - Splits the file into sequential 50MB chunks
   - Names chunks as `filename.partXXX`

4. **Uploading**
   - Clones the target repository to a temporary location
   - Creates folder structure matching original path
   - Copies chunk files to the repository
   - Commits and pushes each chunk individually
   - Verifies successful upload

5. **Cleanup**
   - Deletes the temporary split chunks folder
   - Deletes the temporary archive (if created)
   - **Preserves the original source file/folder**

### Restore Process Flow

1. **Pre-flight Checks**
   - Verifies `gh` CLI is installed and authenticated

2. **Downloading**
   - Clones the repository to a temporary location
   - Locates the specified folder in the repository
   - Finds all chunk files (*.part*)

3. **Reassembling**
   - Combines all chunks back into the original archive
   - Verifies file integrity

4. **Extracting**
   - Extracts the ZIP archive
   - Preserves internal folder structure

5. **Restoring**
   - Determines original location from repo path
   - Adds optional suffix if specified
   - Moves extracted folder to final destination
   - Handles name conflicts automatically

6. **Cleanup**
   - Removes all temporary files
   - Cleans up cloned repository

### Example Process (Folder Input)

**Initial State:**
```
C:\Users\Dan\Downloads\Compressed\Games\CloverPit\
```

**During Processing (temporary files):**
```
C:\Users\Dan\Downloads\Compressed\Games\CloverPit.zip  (temp archive)
C:\Users\Dan\Downloads\Compressed\Games\temp_split_chunks\
    ├── CloverPit.zip.part001
    ├── CloverPit.zip.part002
    ├── CloverPit.zip.part003
    └── ...
```

**Final State (after cleanup):**
```
C:\Users\Dan\Downloads\Compressed\Games\CloverPit\  (UNCHANGED)

GitHub Repository:
Downloads/
  └── Compressed/
      └── Games/
          └── CloverPit/
              ├── CloverPit.zip.part001
              ├── CloverPit.zip.part002
              └── CloverPit.zip.part003
```

All temporary files are deleted. Original folder remains intact.

## Configuration

The following values are hardcoded in the script:

- **Target Repository:** `https://github.com/jam06452/LargeFileStorage`
- **Chunk Size:** 50 MB (52,428,800 bytes)
- **Archive Format:** ZIP

To change these, edit the constants at the top of `backup.py`.

## Error Handling

The utility will stop and display an error if:

- ❌ GitHub CLI (`gh`) is not installed
- ❌ User is not authenticated via `gh auth status`
- ❌ Source path does not exist
- ❌ Insufficient permissions to read source or write temporary files
- ❌ Upload to GitHub fails

## Limitations & Notes

### Important Features
- **Backup and Restore:** Full round-trip support for backing up and restoring files
- **Folder Structure Preservation:** Maintains original folder hierarchy in repository
- **Name Conflict Handling:** Automatically handles existing files during restore

### Important Reminders
- Original files are **never deleted or modified** during backup
- Temporary files are automatically cleaned up after successful operations
- Each chunk upload is verified before proceeding
- Large backups may take significant time depending on file size and internet speed
- Restored folders can have custom suffixes to distinguish from originals

## Troubleshooting

### "gh: command not found"
Install the GitHub CLI and ensure it's in your system PATH.

### "Not authenticated with GitHub"
Run `gh auth login` and follow the prompts.

### "Permission denied"
Ensure you have write access to the target repository.

### Uploads are slow
GitHub has rate limits and file size considerations. The utility uploads one chunk at a time to ensure reliability.

## License

This is a personal utility. Use at your own risk.

## Version

- **Version:** 1.0
- **Date:** October 30, 2025
- **Status:** Production
