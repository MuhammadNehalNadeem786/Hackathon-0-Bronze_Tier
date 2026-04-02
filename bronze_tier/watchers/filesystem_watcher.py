"""
File System Watcher Module

Monitors a drop folder for new files and creates action files
for Claude Code to process.

Bronze Tier Implementation: File system monitoring watcher.
"""

import shutil
import hashlib
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from base_watcher import BaseWatcher


class FileDropItem:
    """Represents a file dropped into the monitoring folder."""

    def __init__(self, source_path: Path, file_hash: str):
        self.source_path = source_path
        self.file_hash = file_hash
        self.name = source_path.name
        self.size = source_path.stat().st_size
        self.created = datetime.fromtimestamp(source_path.stat().st_ctime)
        self.modified = datetime.fromtimestamp(source_path.stat().st_mtime)


class FilesystemWatcher(BaseWatcher):
    """
    Watches a drop folder for new files and creates action files.

    Usage:
        watcher = FilesystemWatcher(vault_path='/path/to/vault')
        watcher.run()
    """

    def __init__(self, vault_path: str, drop_folder: Optional[str] = None, check_interval: int = 30):
        """
        Initialize the filesystem watcher.

        Args:
            vault_path: Path to the Obsidian vault root
            drop_folder: Path to the drop folder (default: vault/Drop)
            check_interval: Seconds between checks (default: 30)
        """
        super().__init__(vault_path, check_interval)

        self.drop_folder = Path(drop_folder) if drop_folder else self.vault_path / 'Drop'
        self.processed_folder = self.vault_path / 'Drop' / '.processed'

        # Ensure directories exist
        self.drop_folder.mkdir(parents=True, exist_ok=True)
        self.processed_folder.mkdir(parents=True, exist_ok=True)

        # Track processed file hashes to avoid duplicates
        self._load_processed_hashes()

    def _load_processed_hashes(self) -> None:
        """Load hashes of already processed files."""
        self.processed_hashes = set()
        hash_file = self.processed_folder / '.processed_hashes.txt'
        if hash_file.exists():
            with open(hash_file, 'r') as f:
                self.processed_hashes = set(line.strip() for line in f)

    def _save_hash(self, file_hash: str) -> None:
        """Save a file hash to the processed list."""
        self.processed_hashes.add(file_hash)
        hash_file = self.processed_folder / '.processed_hashes.txt'
        with open(hash_file, 'a') as f:
            f.write(f'{file_hash}\n')

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def update_dashboard(self) -> None:
        """Update dashboard.md with current status (fire-and-forget)."""
        try:
            script_path = Path(__file__).parent / 'update_dashboard.py'
            subprocess.Popen(
                ['python', str(script_path), str(self.vault_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            self.logger.debug(f'Dashboard update failed: {e}')

    def check_for_updates(self) -> List[FileDropItem]:
        """
        Check the drop folder for new files.

        Returns:
            List of new FileDropItem objects
        """
        new_items = []

        try:
            # Get all files in drop folder (not directories, not hidden)
            files = [
                f for f in self.drop_folder.iterdir()
                if f.is_file() and not f.name.startswith('.')
            ]

            for file_path in files:
                file_hash = self._calculate_hash(file_path)

                # Skip if already processed
                if file_hash in self.processed_hashes:
                    self.logger.debug(f'File already processed: {file_path.name}')
                    continue

                # Create item and add to list
                item = FileDropItem(file_path, file_hash)
                new_items.append(item)
                self.logger.info(f'New file detected: {file_path.name} ({item.size} bytes)')

            if new_items:
                self.logger.info(f'Found {len(new_items)} new file(s)')
                self.update_dashboard()  # Refresh dashboard whenever new files are detected

            return new_items

        except Exception as e:
            self.logger.error(f'Error checking drop folder: {e}', exc_info=True)
            return []

    def create_action_file(self, item: FileDropItem) -> Optional[Path]:
        """
        Create a .md action file in the Needs_Action folder.

        The action file contains metadata about the dropped file
        and suggested actions for Claude Code.

        Args:
            item: The FileDropItem to create an action file for

        Returns:
            Path to the created file, or None if failed
        """
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = self.safe_filename(item.name)
            action_filename = f'FILE_DROP_{safe_name}_{timestamp}.md'
            filepath = self.needs_action / action_filename

            # Copy file to inbox for reference
            inbox_copy = self.inbox / f'{timestamp}_{item.name}'
            shutil.copy2(item.source_path, inbox_copy)

            # Determine file type and suggested actions
            file_ext = item.source_path.suffix.lower()
            suggested_actions = self._get_suggested_actions(file_ext)

            # Generate content
            content = self.generate_frontmatter(
                item_type='file_drop',
                original_name=f'"{item.name}"',
                file_size=item.size,
                file_hash=f'"{item.file_hash}"',
                inbox_copy=f'"{inbox_copy.name}"',
                priority='normal'
            )

            content += f'''

# File Drop: {item.name}

## File Information
- **Original Name:** {item.name}
- **Size:** {self._format_size(item.size)}
- **Detected:** {item.created.strftime('%Y-%m-%d %H:%M')}
- **Inbox Copy:** `{inbox_copy.name}`
- **SHA256:** `{item.file_hash}`

## Content Preview
<!-- AI Employee: Analyze the file content and summarize here -->

## Suggested Actions
{chr(10).join(f'- [ ] {action}' for action in suggested_actions)}

## Processing Notes
<!-- AI Employee: Add notes about processing this file -->

---
*Created by FilesystemWatcher v0.1*
'''

            # Write action file
            filepath.write_text(content, encoding='utf-8')

            # Mark file as processed
            self._save_hash(item.file_hash)

            # Move original file to processed folder
            processed_dest = self.processed_folder / item.name
            shutil.move(str(item.source_path), str(processed_dest))

            self.logger.info(f'Action file created: {filepath.name}')
            self.update_dashboard()  # Refresh dashboard after each action file is created

            return filepath

        except Exception as e:
            self.logger.error(f'Error creating action file: {e}', exc_info=True)
            return None

    def _get_suggested_actions(self, file_ext: str) -> List[str]:
        """
        Get suggested actions based on file extension.

        Args:
            file_ext: File extension (e.g., '.pdf', '.txt')

        Returns:
            List of suggested action descriptions
        """
        action_map = {
            '.pdf': [
                'Extract and summarize content',
                'Categorize document type',
                'Extract key dates or deadlines',
                'File in appropriate folder'
            ],
            '.txt': [
                'Read and summarize content',
                'Extract action items',
                'Respond if needed'
            ],
            '.docx': [
                'Extract and summarize content',
                'Identify action items',
                'Check for signatures required'
            ],
            '.xlsx': [
                'Analyze data structure',
                'Extract key metrics',
                'Create summary report'
            ],
            '.csv': [
                'Parse and analyze data',
                'Import to accounting system',
                'Generate insights'
            ],
            '.jpg': [
                'Analyze image content',
                'Extract text if present (OCR)',
                'Categorize image type'
            ],
            '.jpeg': [
                'Analyze image content',
                'Extract text if present (OCR)',
                'Categorize image type'
            ],
            '.png': [
                'Analyze image content',
                'Extract text if present (OCR)',
                'Categorize image type'
            ],
            '.md': [
                'Read and process content',
                'Update dashboard if relevant',
                'File appropriately'
            ],
        }

        return action_map.get(file_ext, [
            'Analyze file content',
            'Determine appropriate action',
            'Process or file accordingly'
        ])

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f'{size_bytes:.2f} {unit}'
            size_bytes /= 1024.0 # type: ignore
        return f'{size_bytes:.2f} TB'


def main():
    """Main entry point for running the filesystem watcher."""
    import argparse

    parser = argparse.ArgumentParser(description='File System Watcher for AI Employee')
    parser.add_argument(
        '--vault', '-v',
        type=str,
        required=True,
        help='Path to the Obsidian vault'
    )
    parser.add_argument(
        '--drop-folder', '-d',
        type=str,
        default=None,
        help='Path to the drop folder (default: vault/Drop)'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=30,
        help='Check interval in seconds (default: 30)'
    )

    args = parser.parse_args()

    watcher = FilesystemWatcher(
        vault_path=args.vault,
        drop_folder=args.drop_folder,
        check_interval=args.interval
    )
    watcher.run()


if __name__ == '__main__':
    main()