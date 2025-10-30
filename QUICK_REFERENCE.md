# Quick Reference Guide

## One-Line Commands

### Backup
```powershell
# Backup a file
python backup.py "C:\path\to\file.zip"

# Backup a folder
python backup.py "C:\path\to\folder"
```

### Restore
```powershell
# Restore to original location
python restore.py "Downloads/Compressed/Games/CloverPit"

# Restore with suffix
python restore.py "Downloads/Compressed/Games/CloverPit" --suffix "_restored"
```

### Setup (First Time Only)
```powershell
# Install GitHub CLI
winget install GitHub.cli

# Authenticate
gh auth login

# Verify
gh auth status
```

### Help
```powershell
# Backup help
python backup.py --help

# Restore help
python restore.py --help

# Run validation tests
python test_validation.py
```

## What Gets Deleted vs Preserved

### ✓ Preserved (NEVER deleted)
- Original source file or folder

### ✗ Deleted (automatically cleaned up)
- Temporary ZIP archive (if source was a folder)
- Temporary `temp_split_chunks` folder
- All chunk files (.partXXX)

## File Size Limits

| Item | Limit |
|------|-------|
| Chunk Size | 50 MB |
| Max File Size | Unlimited (will be split) |
| GitHub File Limit | Handled automatically |

## Common Paths (Windows)

```powershell
# Documents
python backup.py "$env:USERPROFILE\Documents\MyFolder"

# Downloads
python backup.py "$env:USERPROFILE\Downloads\file.zip"

# Desktop
python backup.py "$env:USERPROFILE\Desktop\MyProject"

# Custom drive
python backup.py "D:\Backups\important.zip"
```

## Process Flow (Quick)

### Backup
```
Input File/Folder
    ↓
[Archive if folder] → temp.zip
    ↓
[Split] → temp_split_chunks/*.partXXX
    ↓
[Upload] → GitHub repo (preserves folder structure)
    ↓
[Cleanup] → Delete temp files
    ↓
Original preserved ✓
```

### Restore
```
GitHub Repo Folder
    ↓
[Download] → Clone repo & find chunks
    ↓
[Reassemble] → Combine chunks → archive.zip
    ↓
[Extract] → Unzip archive
    ↓
[Restore] → Move to original location (+ suffix)
    ↓
[Cleanup] → Delete temp files
    ↓
Restored folder ready ✓
```

## Error Messages

| Error | Solution |
|-------|----------|
| `gh: command not found` | Install GitHub CLI |
| `Not authenticated` | Run `gh auth login` |
| `Source path does not exist` | Check path spelling |
| `Permission denied` | Check file/folder permissions |
| `Failed to upload` | Check internet & repo access |

## Repository Info

**Target:** https://github.com/jam06452/LargeFileStorage

To view uploaded chunks:
1. Visit the repository URL
2. Look for files like: `filename.part001`, `filename.part002`, etc.

## Configuration (in backup.py)

```python
TARGET_REPO_URL = "https://github.com/jam06452/LargeFileStorage"
CHUNK_SIZE_MB = 50
TEMP_CHUNKS_FOLDER = "temp_split_chunks"
```

## Manual Restore Process (Alternative)

```powershell
# 1. Clone the repo
gh repo clone jam06452/LargeFileStorage
cd LargeFileStorage

# 2. Navigate to folder with chunks
cd Downloads\Compressed\Games\CloverPit

# 3. Combine chunks (Windows)
cmd /c copy /b "CloverPit.zip.part*" "CloverPit.zip"

# 4. Extract
Expand-Archive -Path "CloverPit.zip" -DestinationPath "C:\restore_location"
```

**Or use the automated restore script:**
```powershell
python restore.py "Downloads/Compressed/Games/CloverPit" --suffix "_restored"
```

## Tips

💡 **Before First Use:**
- Verify gh CLI: `gh --version`
- Test with small file first
- Ensure stable internet

💡 **For Large Backups:**
- Free up disk space
- Don't interrupt the process
- Be patient (may take hours)

💡 **Best Practices:**
- Use absolute paths
- Quote paths with spaces
- Verify backup before deleting original

## Example Output (Success)

```
======================================================================
  GitHub Chunked Backup Utility
======================================================================

[Step 0] Pre-flight Checks
✓ GitHub CLI (gh) is installed
✓ GitHub CLI authentication verified

[Step 1] Archiving
✓ Archive created: folder.zip (100.50 MB)

[Step 2] Splitting into Chunks
✓ Created 3 chunk file(s)

[Step 3] Uploading to GitHub
✓ All 3 chunk(s) uploaded successfully

[Step 4] Cleanup
✓ Deleted: temp_split_chunks
✓ Deleted: folder.zip

======================================================================
  Backup Completed Successfully!
======================================================================
✓ Original source preserved
✓ Uploaded 3 chunk(s) to GitHub
```

## Files in This Project

| File | Purpose |
|------|---------|
| `backup.py` | Main backup utility |
| `restore.py` | Restore utility |
| `README.md` | Full documentation |
| `EXAMPLES.md` | Detailed examples |
| `QUICK_REFERENCE.md` | This file |
| `test_validation.py` | Validation tests |
| `requirements.txt` | Dependencies (none) |

## Support Checklist

Before asking for help, verify:
- [ ] Python 3.7+ installed: `python --version`
- [ ] GitHub CLI installed: `gh --version`
- [ ] GitHub authenticated: `gh auth status`
- [ ] Source path exists: `Test-Path "path"`
- [ ] Enough disk space available
- [ ] Internet connection stable
- [ ] Repository access confirmed

---

**Version:** 1.0  
**Last Updated:** October 30, 2025
