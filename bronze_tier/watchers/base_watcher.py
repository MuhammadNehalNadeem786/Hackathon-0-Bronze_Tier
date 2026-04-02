"""
Base Watcher Module

Abstract base class for all watcher scripts in the AI Employee system.
All watchers follow the same pattern: monitor -> detect -> create action file.
"""

import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Any, Optional


class BaseWatcher(ABC):
    """
    Abstract base class for all watcher scripts.
    
    Watchers are lightweight Python scripts that run continuously,
    monitoring various inputs and creating actionable files for
    Claude Code to process.
    """
    
    def __init__(self, vault_path: str, check_interval: int = 60):
        """
        Initialize the watcher.
        
        Args:
            vault_path: Path to the Obsidian vault root
            check_interval: Seconds between checks (default: 60)
        """
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.inbox = self.vault_path / 'Inbox'
        self.logs = self.vault_path / 'Logs'
        self.check_interval = check_interval
        
        # Ensure directories exist
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Track processed items to avoid duplicates
        self.processed_ids: set = set()
        
    def _setup_logging(self) -> None:
        """Setup logging to file and console."""
        log_file = self.logs / f'watcher_{datetime.now().strftime("%Y-%m-%d")}.log'
        
        # Create a logger for this instance
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Only add handlers if logger doesn't have any
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            # Console handler (always add)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            # File handler (only if log folder is accessible)
            try:
                file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception:
                # Silently skip file logging if not possible (e.g., temp dirs in tests)
                pass
    
    @abstractmethod
    def check_for_updates(self) -> List[Any]:
        """
        Check for new items to process.
        
        Returns:
            List of new items that need action
        """
        pass
    
    @abstractmethod
    def create_action_file(self, item: Any) -> Optional[Path]:
        """
        Create a .md action file in the Needs_Action folder.
        
        Args:
            item: The item to create an action file for
            
        Returns:
            Path to the created file, or None if failed
        """
        pass
    
    def run(self) -> None:
        """
        Main run loop for the watcher.
        Continuously checks for updates and creates action files.
        """
        self.logger.info(f'Starting {self.__class__.__name__}')
        self.logger.info(f'Vault path: {self.vault_path}')
        self.logger.info(f'Check interval: {self.check_interval}s')
        
        try:
            while True:
                try:
                    items = self.check_for_updates()
                    if items:
                        self.logger.info(f'Found {len(items)} new item(s) to process')
                        for item in items:
                            filepath = self.create_action_file(item)
                            if filepath:
                                self.logger.info(f'Created action file: {filepath.name}')
                    else:
                        self.logger.debug('No new items found')
                except Exception as e:
                    self.logger.error(f'Error processing items: {e}', exc_info=True)
                
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.logger.info(f'{self.__class__.__name__} stopped by user')
        except Exception as e:
            self.logger.error(f'Fatal error: {e}', exc_info=True)
            raise
    
    def generate_frontmatter(self, item_type: str, **kwargs) -> str:
        """
        Generate YAML frontmatter for action files.
        
        Args:
            item_type: Type of item (email, file_drop, whatsapp, etc.)
            **kwargs: Additional metadata fields
            
        Returns:
            Formatted YAML frontmatter string
        """
        lines = [
            '---',
            f'type: {item_type}',
            f'created: {datetime.now().isoformat()}',
            'status: pending',
        ]
        
        for key, value in kwargs.items():
            lines.append(f'{key}: {value}')
        
        lines.append('---')
        return '\n'.join(lines)
    
    def safe_filename(self, name: str) -> str:
        """
        Create a safe filename by removing/replacing invalid characters.
        
        Args:
            name: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|？*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name.strip()
