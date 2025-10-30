# GitHub Chunked Backup Utility - Usage Examples

This document provides detailed examples and common use cases for the backup utility.

## Quick Start

### 1. First-Time Setup

Before using the utility for the first time:

```powershell
# Install GitHub CLI (if not already installed)
winget install GitHub.cli

# Authenticate with GitHub
gh auth login

# Verify authentication
gh auth status
```

### 2. Run Your First Backup

```powershell
# Backup a file
python backup.py "C:\backups\important_data.zip"

# Backup a folder
python backup.py "C:\Users\Dan\Downloads\MyFolder"
```

## Detailed Examples

### Example 1: Backup a Large ZIP File

```powershell
python backup.py "C:\backups\my_archive.zip"
```

**What happens:**
1. ✓ Validates the file exists
2. ✓ Checks GitHub CLI authentication
3. ✓ Splits the ZIP into 50MB chunks
4. ✓ Uploads each chunk to GitHub
5. ✓ Cleans up temporary chunk files
6. ✓ Original ZIP remains untouched

**Output:**
```
======================================================================
  GitHub Chunked Backup Utility
======================================================================

  → Source: C:\backups\my_archive.zip
  → Target Repository: https://github.com/jam06452/LargeFileStorage
  → Chunk Size: 50 MB

[Step 0] Pre-flight Checks
----------------------------------------------------------------------
✓ GitHub CLI (gh) is installed
✓ GitHub CLI authentication verified

[Step 1] Archiving (Skipped - source is a file)

[Step 2] Splitting into Chunks
----------------------------------------------------------------------
  → File size: 157.43 MB
  → Will create 4 chunk(s) of max 50 MB each
  → Created chunk 1/4: my_archive.zip.part001 (50.00 MB)
  → Created chunk 2/4: my_archive.zip.part002 (50.00 MB)
  → Created chunk 3/4: my_archive.zip.part003 (50.00 MB)
  → Created chunk 4/4: my_archive.zip.part004 (7.43 MB)
✓ Created 4 chunk file(s)

[Step 3] Uploading to GitHub
----------------------------------------------------------------------
  → Cloning repository to temporary location...
✓ Repository cloned
  → Uploading chunk 1/4: my_archive.zip.part001
✓ Uploaded: my_archive.zip.part001
  → Uploading chunk 2/4: my_archive.zip.part002
✓ Uploaded: my_archive.zip.part002
  → Uploading chunk 3/4: my_archive.zip.part003
✓ Uploaded: my_archive.zip.part003
  → Uploading chunk 4/4: my_archive.zip.part004
✓ Uploaded: my_archive.zip.part004
✓ All 4 chunk(s) uploaded successfully

[Step 4] Cleanup
----------------------------------------------------------------------
  → Cleaning up temporary files...
✓ Deleted: temp_split_chunks
✓ Backup Completed Successfully!
✓ Original source preserved: C:\backups\my_archive.zip
✓ Uploaded 4 chunk(s) to GitHub
  → Repository: https://github.com/jam06452/LargeFileStorage
```

### Example 2: Backup a Folder (CloverPit Example)

```powershell
python backup.py "C:\Users\Dan\Downloads\Compressed\Games\CloverPit"
```

**What happens:**
1. ✓ Validates the folder exists
2. ✓ Creates a temporary ZIP: `CloverPit.zip`
3. ✓ Splits the ZIP into chunks
4. ✓ Uploads chunks to GitHub
5. ✓ Deletes `CloverPit.zip` and chunks
6. ✓ Original `CloverPit` folder remains untouched

**Directory State During Process:**

```
Before:
C:\Users\Dan\Downloads\Compressed\Games\
    └── CloverPit\
            ├── file1.dat
            ├── file2.dat
            └── ...

During Processing:
C:\Users\Dan\Downloads\Compressed\Games\
    ├── CloverPit\              (original - untouched)
    ├── CloverPit.zip           (temp archive)
    └── temp_split_chunks\      (temp folder)
            ├── CloverPit.zip.part001
            ├── CloverPit.zip.part002
            └── ...

After Completion:
C:\Users\Dan\Downloads\Compressed\Games\
    └── CloverPit\              (original - untouched)
```

### Example 3: Backup with Spaces in Path

```powershell
# Always use quotes for paths with spaces
python backup.py "C:\My Documents\Project Files\Large Dataset"
```

### Example 4: Using Relative Paths

```powershell
# Navigate to the directory first
cd "C:\Users\Dan\Downloads"

# Use relative path
python backup.py ".\MyFolder"
```

## Common Scenarios

### Scenario 1: Large Game Backup

You have a 200GB game folder to backup:

```powershell
python backup.py "C:\Games\MyLargeGame"
```

This will:
- Create a ZIP archive (may take 30+ minutes)
- Split into ~4,000 chunks (200GB / 50MB)
- Upload to GitHub (may take several hours)

**Tip:** Be patient! Large backups take time.

### Scenario 2: Multiple Files

To backup multiple separate files, run the utility multiple times:

```powershell
python backup.py "C:\Data\file1.zip"
python backup.py "C:\Data\file2.zip"
python backup.py "C:\Data\file3.zip"
```

Each will be chunked and uploaded separately.

### Scenario 3: Incremental Backups

To backup different versions:

```powershell
# Backup version 1
python backup.py "C:\Project\v1.0"

# Later, backup version 2
python backup.py "C:\Project\v2.0"
```

Both versions will be stored in the GitHub repository.

## Checking Upload Progress

During upload, you can check your GitHub repository to see chunks appearing:

1. Open: https://github.com/jam06452/LargeFileStorage
2. You'll see files like:
   - `my_archive.zip.part001`
   - `my_archive.zip.part002`
   - etc.

## Troubleshooting Examples

### Error: "gh: command not found"

**Solution:**
```powershell
# Install GitHub CLI
winget install GitHub.cli

# Restart PowerShell, then authenticate
gh auth login
```

### Error: "Not authenticated with GitHub CLI"

**Solution:**
```powershell
gh auth login
# Follow the prompts to authenticate
```

### Error: "Source path does not exist"

**Solution:**
```powershell
# Check the path exists
Test-Path "C:\your\path\here"

# Use quotes for paths with spaces
python backup.py "C:\My Folder\file.zip"
```

### Error: "Permission denied"

**Solution:**
- Ensure you have read access to the source
- Ensure you have write access to the target repository
- Check folder permissions

## Performance Tips

### For Very Large Files/Folders:

1. **Free up disk space:** You need enough space for:
   - Original file/folder
   - Temporary ZIP (if backing up a folder)
   - Temporary chunks (max 50MB at a time)

2. **Be patient:** Large uploads take time. Don't interrupt!

3. **Check your internet:** Uploads are network-intensive

4. **Monitor progress:** Watch the console output

### Optimal Use:

- **Best for:** Files/folders up to several hundred GB
- **Chunk size:** 50MB balances upload reliability and commit count
- **Network:** Stable internet connection recommended

## Advanced Usage

### Check Version

```powershell
python backup.py --version
```

### Get Help

```powershell
python backup.py --help
```

### Dry Run (Manual)

To see what would be backed up without actually uploading:

1. Comment out the upload step in `backup.py` (line with `upload_chunks_to_github`)
2. Run the backup
3. Check the `temp_split_chunks` folder to see the chunks
4. Manually delete the temp folder when done

## Restoring Backups (Manual Process)

This utility does **not** include automatic restore. To restore manually:

1. **Download chunks from GitHub:**
   ```powershell
   gh repo clone jam06452/LargeFileStorage
   cd LargeFileStorage
   ```

2. **Reassemble chunks:** (Windows PowerShell)
   ```powershell
   # Combine all .part files back into the original
   cmd /c copy /b "CloverPit.zip.part*" "CloverPit.zip"
   ```

3. **Extract (if folder backup):**
   ```powershell
   Expand-Archive -Path "CloverPit.zip" -DestinationPath ".\CloverPit"
   ```

## Best Practices

✅ **DO:**
- Verify your GitHub CLI is authenticated before starting
- Use absolute paths when possible
- Keep an eye on disk space
- Test with a small file first
- Ensure stable internet for large uploads

❌ **DON'T:**
- Interrupt the upload process
- Delete the source until you verify the backup
- Run multiple backups simultaneously
- Modify files while backup is in progress

## Support

For issues or questions:
- Check the README.md
- Verify GitHub CLI installation: `gh --version`
- Verify authentication: `gh auth status`
- Check repository access: https://github.com/jam06452/LargeFileStorage
