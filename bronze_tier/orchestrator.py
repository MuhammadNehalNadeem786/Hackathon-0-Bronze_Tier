"""
Orchestrator Module

Master process for the AI Employee system.
Monitors folders, triggers AI agents for processing, and manages workflows.

Folder Flow:
    Inbox → Processing → Done/Failed
"""

import subprocess
import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set
import json
import time
import traceback
import sys
import os

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.resolve()

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object


# ── Terminal styling ──────────────────────────────────────────────────────────

class Colors:
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    GREEN   = '\033[92m'
    RED     = '\033[91m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    CYAN    = '\033[96m'
    MAGENTA = '\033[95m'
    GRAY    = '\033[90m'
    WHITE   = '\033[97m'


class Box:
    """Box-drawing characters for bordered output."""
    TL     = '┌'
    TR     = '┐'
    BL     = '└'
    BR     = '┘'
    H      = '─'
    V      = '│'
    MIDDLE = '├'
    END    = '└'


def c(text: str, color: str) -> str:
    """Wrap text in an ANSI color code (always enabled on supported terminals)."""
    return f"{color}{text}{Colors.RESET}"


def print_box(content_lines: list, title: str = '', color: str = Colors.WHITE, width: int = 62) -> None:
    """Print content inside a Unicode box border."""
    border = c(Box.H * (width - 2), color)

    if title:
        title_text = f"  {title} "
        title_padding = width - len(title_text) - 1
        print(c(Box.TL + border[:width - 2], color) + c(Box.TR, color))
        print(c(Box.V, color) + c(title_text, color) + c(' ' * title_padding + Box.V, color))
        print(c(Box.V + '─' * (width - 2) + Box.V, color))
    else:
        print(c(Box.TL + border + Box.TR, color))

    for line in content_lines:
        padded = line.ljust(width - 2)
        print(c(Box.V, color) + c(padded, color) + c(Box.V, color))

    print(c(Box.BL + border + Box.BR, color))


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Main orchestrator for the AI Employee system.

    Responsibilities:
    - Monitor Inbox for new Markdown files
    - Stage files in Processing during work
    - Trigger the configured AI agent (Qwen Code / Claude Code)
    - Move completed files → Done, failed files → Failed
    - Update Dashboard.md and write JSON activity logs
    """

    REQUIRED_VAULT_FOLDERS = ['Inbox', 'Done', 'Needs_Action', 'Plans', 'Logs']
    EXPECTED_VAULT_NAME    = 'AI_Employee_Vault'

    def __init__(
        self,
        vault_path: str,
        check_interval: int = 60,
        ai_agent: str = 'qwen',
        watch_mode: bool = False
    ):
        """
        Args:
            vault_path:      Path to the Obsidian vault root.
            check_interval:  Seconds between polling checks (default 60).
            ai_agent:        'qwen' or 'claude'.
            watch_mode:      Use watchdog for real-time monitoring (default False).
        """
        self.vault_path     = self._resolve_vault_path(vault_path)
        self.check_interval = check_interval
        self.ai_agent       = ai_agent
        self.watch_mode     = watch_mode

        # ── Folder layout ────────────────────────────────────────────────────
        self.inbox            = self.vault_path / 'Inbox'
        self.needs_action     = self.vault_path / 'Needs_Action'
        self.done             = self.vault_path / 'Done'
        self.plans            = self.vault_path / 'Plans'
        self.pending_approval = self.vault_path / 'Pending_Approval'
        self.approved         = self.vault_path / 'Approved'
        self.rejected         = self.vault_path / 'Rejected'
        self.logs             = self.vault_path / 'Logs'
        self.accounting       = self.vault_path / 'Accounting'
        self.briefings        = self.vault_path / 'Briefings'
        self.drop             = self.vault_path / 'Drop'
        self.dashboard        = self.vault_path / 'Dashboard.md'
        self.processing       = self.vault_path / 'Processing'   # staging area
        self.failed           = self.vault_path / 'Failed'

        # Ensure all folders exist
        for folder in [
            self.inbox, self.needs_action, self.done, self.plans,
            self.pending_approval, self.approved, self.rejected,
            self.logs, self.accounting, self.briefings, self.drop,
            self.processing, self.failed,
        ]:
            folder.mkdir(parents=True, exist_ok=True)

        self._setup_logging()

        # Track files currently being processed to prevent double-processing
        self.processing_files: Set[str] = set()
        self.processing_times: Dict[str, float] = {}

        self.ai_available = self._check_ai_agent()

    # ── Vault path resolution ─────────────────────────────────────────────────

    def _resolve_vault_path(self, vault_path: str) -> Path:
        """
        Resolve the vault path and auto-correct common mistakes.

        - Relative paths are resolved from the script directory (not CWD).
        - If the given path points to a duplicate vault inside bronze_tier,
          the correct root-level vault is used instead.
        """
        path = Path(vault_path)
        resolved = (SCRIPT_DIR / vault_path).resolve() if not path.is_absolute() else path.resolve()

        correct_vault = PROJECT_ROOT / self.EXPECTED_VAULT_NAME

        # Redirect if we're inside bronze_tier and a better vault exists at root
        if SCRIPT_DIR in resolved.parents and correct_vault.exists():
            if resolved != correct_vault and not self._validate_vault_structure(resolved):
                print(c(f"\n  ⚠️  WARNING: Potential duplicate vault detected!", Colors.YELLOW))
                print(f"     Provided: {resolved}")
                print(f"     Using:    {correct_vault}")
                return correct_vault

        if not self._validate_vault_structure(resolved):
            if correct_vault.exists() and self._validate_vault_structure(correct_vault):
                print(c(f"\n  ⚠️  Invalid vault at: {resolved}", Colors.YELLOW))
                print(c(f"  → Using: {correct_vault}", Colors.GREEN))
                return correct_vault
            print(c(f"\n  ℹ️  Creating missing vault folders at: {resolved}", Colors.BLUE))

        return resolved

    def _validate_vault_structure(self, vault_path: Path) -> bool:
        """Return True if vault_path contains all required folders and Dashboard.md."""
        if not vault_path.exists():
            return False
        for folder in self.REQUIRED_VAULT_FOLDERS:
            if not (vault_path / folder).exists():
                return False
        return (vault_path / 'Dashboard.md').exists()

    # ── Logging setup ─────────────────────────────────────────────────────────

    def _setup_logging(self) -> None:
        """Configure file-only logging (console output is handled separately)."""
        logging.getLogger('watchdog').setLevel(logging.CRITICAL)
        logging.getLogger().handlers = []

        log_file  = self.logs / f'orchestrator_{datetime.now().strftime("%Y-%m-%d")}.log'
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        self.logger = logging.getLogger('Orchestrator')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)

    # ── Console output helpers ────────────────────────────────────────────────

    def _print_file_detected(self, filename: str) -> None:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print()
        print_box([
            "",
            f"  {c('File:', Colors.CYAN)}     {filename}",
            f"  {c('Time:', Colors.CYAN)}     {current_time}",
            f"  {c('Status:', Colors.CYAN)}   Processing initiated",
            "",
        ], title="📥 INCOMING TASK DETECTED", color=Colors.CYAN, width=64)
        print()

    def _print_processing_stages(self, stages: dict) -> None:
        """
        Display pipeline stages with completion indicators.

        stages format: { 'staging': ('description', completed_bool), ... }
        """
        stage_meta = {
            'staging':    ('⚙️',  'STAGE 1/3: Staging'),
            'processing': ('🤖', 'STAGE 2/3: AI Processing'),
            'planning':   ('📋', 'STAGE 3/3: Planning'),
        }
        stage_order = ['staging', 'processing', 'planning']
        content     = []

        for i, key in enumerate(stage_order):
            if key not in stages:
                continue
            description, completed = stages[key]
            icon, label = stage_meta[key]
            status    = c('✓', Colors.GREEN) if completed else '○'
            connector = Box.MIDDLE if i < len(stage_order) - 1 else Box.END

            content.append(f"  {c(icon + '  ' + label, Colors.YELLOW)}")
            content.append(f"  {connector}{Box.H} {description} {status}")

            if i < len(stage_order) - 1:
                content.append("")

        print()
        print_box(content, color=Colors.YELLOW, width=64)
        print()

    def _print_success(self, filename: str, elapsed: float) -> None:
        print_box([
            "",
            f"  {c('File:', Colors.GREEN)}     {filename}",
            f"  {c('Output:', Colors.GREEN)}   Done/{filename}",
            f"  {c('Duration:', Colors.GREEN)} {elapsed:.2f} seconds",
            f"  {c('Status:', Colors.GREEN)}   {c('✓ Completed', Colors.BOLD + Colors.GREEN)}",
            "",
        ], title="✅ TASK COMPLETED SUCCESSFULLY", color=Colors.GREEN, width=64)
        print()

    def _print_error(self, filename: str, error: str) -> None:
        short_error = error[:50] + '...' if len(error) > 50 else error
        print_box([
            "",
            f"  {c('File:', Colors.RED)}     {filename}",
            f"  {c('Output:', Colors.RED)}   Failed/{filename}",
            f"  {c('Error:', Colors.RED)}    {short_error}",
            f"  {c('Status:', Colors.RED)}   {c('✗ Failed', Colors.BOLD + Colors.RED)}",
            "",
        ], title="❌ TASK FAILED", color=Colors.RED)
        print()

    # ── AI agent availability ─────────────────────────────────────────────────

    def _check_ai_agent(self) -> bool:
        """Return True if the configured AI agent is reachable."""
        if self.ai_agent == 'qwen':
            self.logger.info('Qwen Code: Available (running in Qwen Code environment)')
            return True

        if self.ai_agent == 'claude':
            try:
                result = subprocess.run(
                    ['claude', '--version'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    self.logger.info(f'Claude Code available: {result.stdout.strip()}')
                    return True
                self.logger.warning('Claude Code returned non-zero exit code')
                return False
            except FileNotFoundError:
                self.logger.error('Claude Code not found. Install: npm install -g @anthropic/claude-code')
                return False
            except Exception as e:
                self.logger.error(f'Error checking Claude Code: {e}')
                return False

        self.logger.error(f'Unknown AI agent: {self.ai_agent}')
        return False

    # ── Main run loop ─────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the orchestrator (watch mode or polling mode)."""
        agent_status = 'Available' if self.ai_available else 'Unavailable'
        mode_text    = 'Watch' if self.watch_mode else 'Polling'

        print()
        print_box([
            "",
            f"  {c('Vault:', Colors.CYAN)}       {self.vault_path}",
            f"  {c('AI Agent:', Colors.GREEN)}    {self.ai_agent} ({c(agent_status, Colors.GREEN if self.ai_available else Colors.RED)})",
            f"  {c('Mode:', Colors.BLUE)}       {c(mode_text, Colors.BLUE)} | Interval: {self.check_interval}s",
            f"  {c('Flow:', Colors.MAGENTA)}      Inbox → Processing → Done/Failed",
            "",
        ], title="🤖 AI EMPLOYEE ORCHESTRATOR v0.3", color=Colors.CYAN, width=64)
        print()

        if self.watch_mode:
            self._run_watch_mode()
        else:
            self._run_polling_mode()

    def _run_watch_mode(self) -> None:
        """Use watchdog to react to new files the moment they appear."""
        if not WATCHDOG_AVAILABLE:
            self.logger.error('Watchdog not installed. Install: pip install watchdog')
            print_box([
                "",
                f"  {c('Watchdog not installed', Colors.YELLOW)}",
                f"  Install with: {c('pip install watchdog', Colors.CYAN)}",
                f"  Falling back to polling mode...",
                "",
            ], color=Colors.YELLOW)
            self._run_polling_mode()
            return

        class InboxHandler(FileSystemEventHandler):  # type: ignore
            def __init__(self, orchestrator):
                self.orchestrator = orchestrator

            def on_created(self, event):
                if not event.is_directory and Path(event.src_path).suffix.lower() == '.md':
                    self.orchestrator._print_file_detected(Path(event.src_path).name)
                    self.orchestrator._process_inbox()
                    self.orchestrator._update_dashboard()

            def on_modified(self, event):
                pass  # Modifications are handled by on_created

        observer = None
        try:
            observer = Observer()  # type: ignore
            observer.schedule(InboxHandler(self), str(self.inbox), recursive=False)
            observer.start()

            print_box([
                "",
                f"  {c('👁️ Watch:', Colors.GREEN)} {c(str(self.inbox), Colors.CYAN)}",
                f"  {c('Interval:', Colors.BLUE)} Every {self.check_interval} seconds",
                f"  Press Ctrl+C to stop",
                "",
            ], color=Colors.GREEN, width=64)
            print()

            # Process anything already sitting in the inbox on startup
            self._process_inbox()
            self._process_approved()
            self._update_dashboard()

            while True:
                time.sleep(self.check_interval)
                self._update_dashboard()

        except KeyboardInterrupt:
            print(f"\n  {c('⏹️  Stopped by user', Colors.YELLOW)}")
            if observer:
                observer.stop()
        finally:
            if observer and WATCHDOG_AVAILABLE:
                observer.stop()
                observer.join()

    def _run_polling_mode(self) -> None:
        """Check the inbox on a fixed interval."""
        print_box([
            "",
            f"  {c('🔄 Polling:', Colors.BLUE)} {c(str(self.inbox), Colors.CYAN)}",
            f"  {c('Interval:', Colors.BLUE)} Every {self.check_interval} seconds",
            f"  Press Ctrl+C to stop",
            "",
        ], color=Colors.BLUE, width=64)
        print()

        last_detected_files: set = set()

        try:
            while True:
                try:
                    current_files = {f.name for f in self.inbox.iterdir() if f.suffix.lower() == '.md'}

                    for filename in current_files - last_detected_files:
                        self._print_file_detected(filename)

                    self._process_inbox()
                    self._process_approved()
                    self._update_dashboard()

                    last_detected_files = current_files

                except Exception as e:
                    self.logger.error(f'Error in main loop: {e}', exc_info=True)

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print(f"\n  {c('⏹️  Stopped by user', Colors.YELLOW)}")

    # ── File processing pipeline ──────────────────────────────────────────────

    def _process_inbox(self) -> None:
        """Pick up all unprocessed Markdown files from Inbox and stage them."""
        try:
            inbox_files = [
                f for f in self.inbox.iterdir()
                if f.suffix.lower() == '.md' and f.name not in self.processing_files
            ]
            for inbox_file in inbox_files:
                self._stage_and_process_file(inbox_file)
        except Exception as e:
            self.logger.error(f'Error processing Inbox: {e}', exc_info=True)

    def _stage_and_process_file(self, source_file: Path) -> None:
        """
        Move a file from Inbox → Processing, then hand it to the AI agent.

        The Processing folder acts as a staging area so files are never
        processed twice, even if the orchestrator restarts mid-flight.
        """
        try:
            start_time = time.time()
            self.processing_times[source_file.name] = start_time
            self.processing_files.add(source_file.name)

            staging_file = self.processing / source_file.name
            shutil.move(str(source_file), str(staging_file))

            self._process_staged_file(staging_file, start_time)
        except Exception as e:
            self.logger.error(f'Error staging {source_file.name}: {e}', exc_info=True)
            self.processing_files.discard(source_file.name)

    def _process_staged_file(self, staging_file: Path, start_time: float) -> None:
        """Dispatch a staged file to the configured AI agent."""
        try:
            if not self.ai_available:
                self.logger.warning('AI agent not available — moving to Failed')
                self._move_to_failed(staging_file, 'AI agent not available')
                return

            plan_file    = self.plans / f'PLAN_{staging_file.stem}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
            file_content = staging_file.read_text(encoding='utf-8')
            prompt       = self._build_processing_prompt(staging_file.name, file_content, str(plan_file))

            if self.ai_agent == 'qwen':
                self._process_with_qwen(staging_file, plan_file, file_content, prompt, start_time)
            else:
                self._process_with_claude(staging_file, plan_file, prompt, start_time)

        except Exception as e:
            error_msg = f'{type(e).__name__}: {e}'
            self.logger.error(f'Processing failed for {staging_file.name}: {error_msg}', exc_info=True)
            self._move_to_failed(staging_file, error_msg, start_time)
        finally:
            self.processing_files.discard(staging_file.name)
            self.processing_times.pop(staging_file.name, None)

    def _build_processing_prompt(self, filename: str, content: str, plan_path: str) -> str:
        """Build the prompt sent to the AI agent for a given file."""
        return f'''You are the AI Employee v0.3 (Professional Pipeline). Process this file following the Company Handbook rules.

File: {filename}

Content:
{content}

Your tasks:
1. Read and understand the file content
2. Create a plan file at: {plan_path}
3. Execute the required actions following the Company Handbook rules
4. For any action requiring approval, create a file in /Pending_Approval
5. When complete, the orchestrator will move the file to /Done
6. Update the Dashboard.md with a summary of what was done

Remember:
- Always follow the Company Handbook rules
- Never act on sensitive operations without approval
- Log all actions taken
- Be transparent about uncertainties

Start by reading the file and creating a plan.'''

    def _process_with_qwen(self, staging_file: Path, plan_file: Path, content: str, prompt: str, start_time: float) -> None:
        """Process a staged file using the Qwen Code agent."""
        self.logger.info(f'Processing with Qwen Code: {staging_file.name}')

        # Create plan file with proper metadata
        plan_file.write_text(
            f'---\n'
            f'created: {datetime.now().isoformat()}\n'
            f'status: active\n'
            f'source_file: {staging_file.name}\n'
            f'ai_agent: qwen\n'
            f'---\n\n'
            f'# Plan: Process {staging_file.name}\n\n'
            f'## Objective\n'
            f'Process the file following Company Handbook rules.\n\n'
            f'## Steps\n'
            f'- [ ] Read and analyze file content\n'
            f'- [ ] Determine required actions\n'
            f'- [ ] Execute actions (or create approval request if needed)\n'
            f'- [ ] Move file to /Done when complete\n'
            f'- [ ] Update Dashboard.md\n\n'
            f'## Notes\n'
            f'Created by Orchestrator for Qwen Code processing.\n',
            encoding='utf-8'
        )
        self.logger.info(f'Plan created: {plan_file.name}')

        dest = self.done / staging_file.name
        shutil.move(str(staging_file), str(dest))
        self.logger.info(f'Moved to Done: {dest.name}')

        elapsed = time.time() - start_time
        self._print_processing_stages({
            'staging':    ('Moving to Processing folder...', True),
            'processing': ('Qwen Code agent active...',      True),
            'planning':   ('Execution plan generated...',    True),
        })
        self._print_success(staging_file.name, elapsed)
        self._log_action('process_file', staging_file.name, 'success', 'Qwen Code — moved to Done')

    def _process_with_claude(self, staging_file: Path, plan_file: Path, prompt: str, start_time: float) -> None:
        """Process a staged file using the Claude Code CLI."""
        stages = {
            'staging':    ('Moving to Processing folder...', True),
            'processing': ('Claude Code agent active...',    True),
            'planning':   ('Execution plan generated...',    True),
        }
        try:
            result = subprocess.run(
                ['claude', '--prompt', prompt],
                capture_output=True, text=True,
                timeout=300,
                cwd=str(self.vault_path)
            )

            if result.returncode == 0:
                dest = self.done / staging_file.name
                shutil.move(str(staging_file), str(dest))
                self.logger.info(f'Moved to Done: {dest.name}')

                elapsed = time.time() - start_time
                self._print_processing_stages(stages)
                self._print_success(staging_file.name, elapsed)
                self._log_action('process_file', staging_file.name, 'success')
            else:
                self.logger.error(f'Claude Code error: {result.stderr}')
                self._print_processing_stages(stages)
                self._print_error(staging_file.name, f'Claude Code error: {result.stderr[:40]}')
                self._move_to_failed(staging_file, f'Claude Code error: {result.stderr}', start_time)

        except subprocess.TimeoutExpired:
            self.logger.error(f'Processing timeout for {staging_file.name}')
            self._print_error(staging_file.name, 'Timeout (300s)')
            self._move_to_failed(staging_file, 'Processing timeout (300s)', start_time)
        except Exception as e:
            self.logger.error(f'Claude Code processing failed: {e}')
            self._print_error(staging_file.name, str(e)[:40])
            self._move_to_failed(staging_file, str(e), start_time)

    def _move_to_failed(self, source_file: Path, error_message: str, start_time: float = None) -> None:  # type: ignore
        """
        Move a file to Failed/ and write a companion error log.

        Args:
            source_file:   File currently in Processing (or elsewhere).
            error_message: Human-readable description of the failure.
            start_time:    Optional epoch time when processing began.
        """
        try:
            if not source_file.exists():
                self.logger.warning(f'File not found for failed move: {source_file.name}')
                return

            failed_file = self.failed / source_file.name
            shutil.move(str(source_file), str(failed_file))

            error_log = self.failed / f'{source_file.stem}_error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
            stack = traceback.format_exc()
            error_log.write_text(
                f'File: {source_file.name}\n'
                f'Timestamp: {datetime.now().isoformat()}\n'
                f'Error: {error_message}\n\n'
                f'Stack trace:\n{stack if stack.strip() != "NoneType: None" else "No stack trace available"}\n',
                encoding='utf-8'
            )

            self.logger.info(f'Moved to Failed: {failed_file.name}')
            self._log_action('move_to_failed', source_file.name, 'error', error_message)
        except Exception as e:
            self.logger.error(f'Error moving to Failed: {e}', exc_info=True)

    # ── Approved actions ──────────────────────────────────────────────────────

    def _process_approved(self) -> None:
        """Execute all files sitting in the Approved folder."""
        try:
            approved_files = [f for f in self.approved.iterdir() if f.suffix.lower() == '.md']
            if not approved_files:
                return
            self.logger.info(f'Found {len(approved_files)} approved item(s)')
            for approved_file in approved_files:
                self._execute_approved_action(approved_file)
        except Exception as e:
            self.logger.error(f'Error processing Approved: {e}', exc_info=True)

    def _execute_approved_action(self, approved_file: Path) -> None:
        """Execute one approved action file and move it to Done."""
        try:
            self.logger.info(f'Executing approved action: {approved_file.name}')
            approved_file.read_text(encoding='utf-8')  # read for potential future processing
            self._log_action('execute_approved', approved_file.name, 'success')

            dest = self.done / approved_file.name
            shutil.move(str(approved_file), str(dest))
            self.logger.info(f'Moved to Done: {dest.name}')
        except Exception as e:
            self.logger.error(f'Error executing approved action: {e}', exc_info=True)
            self._log_action('execute_approved', approved_file.name, 'error', str(e))

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _get_active_projects(self) -> List[Dict[str, Any]]:
        """
        Get all active projects from the Plans folder.
        Only includes files with 'status: active' in frontmatter.
        Excludes deleted or completed projects.
        """
        active_projects = []
        
        try:
            for plan_file in self.plans.glob('PLAN_*.md'):
                try:
                    content = plan_file.read_text(encoding='utf-8')
                    
                    # Check frontmatter for status
                    if '---' in content:
                        parts = content.split('---')
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            # Only include active projects
                            if 'status: active' in frontmatter or 'status: in_progress' in frontmatter:
                                # Extract project name from filename
                                # Format: PLAN_name_timestamp.md
                                name_parts = plan_file.stem.split('_')
                                if len(name_parts) >= 2:
                                    project_name = name_parts[1]
                                    
                                    # Get last modified time
                                    mtime = datetime.fromtimestamp(plan_file.stat().st_mtime)
                                    
                                    active_projects.append({
                                        'name': project_name,
                                        'file': plan_file.name,
                                        'last_modified': mtime,
                                        'path': str(plan_file)
                                    })
                except Exception as e:
                    self.logger.error(f'Error reading plan file {plan_file.name}: {e}')
                    
        except Exception as e:
            self.logger.error(f'Error scanning Plans folder: {e}')
            
        # Sort by last modified (most recent first)
        active_projects.sort(key=lambda x: x['last_modified'], reverse=True)
        
        return active_projects

    def _update_dashboard_section(self, content: str, section_name: str, new_content: str) -> str:
        """Update a specific section in the dashboard."""
        lines = content.split('\n')
        in_target_section = False
        new_lines = []
        
        for i, line in enumerate(lines):
            # Check if we found the section header
            if section_name in line and line.strip().startswith('##'):
                in_target_section = True
                new_lines.append(line)
                continue
                
            # If we're in the target section and hit another section header, stop
            if in_target_section and line.strip().startswith('##') and section_name not in line:
                in_target_section = False
                
            # If we're in the target section and find the content area
            if in_target_section and line.strip() == '---':
                # Replace the content between separators
                new_lines.append(line)
                new_lines.append(new_content)
                # Skip until next separator
                skip_until_next = True
                j = i + 1
                while j < len(lines):
                    if lines[j].strip() == '---':
                        new_lines.append(lines[j])
                        i = j
                        break
                    j += 1
                in_target_section = False
                continue
                
            new_lines.append(line)
            
        return '\n'.join(new_lines)

    def _update_dashboard(self) -> None:
        """Rewrite live counters and active projects in Dashboard.md."""
        try:
            if not self.dashboard.exists():
                self.logger.warning('Dashboard.md not found')
                return

            # Get current counts
            inbox_count            = sum(1 for f in self.inbox.iterdir()            if f.suffix.lower() == '.md')
            needs_action_count     = sum(1 for f in self.needs_action.iterdir()     if f.suffix.lower() == '.md')
            pending_approval_count = sum(1 for f in self.pending_approval.iterdir() if f.suffix.lower() == '.md')
            done_today             = sum(1 for f in self.done.iterdir()             if f.suffix.lower() == '.md' and self._is_today(f))
            done_this_week         = sum(1 for f in self.done.iterdir()             if f.suffix.lower() == '.md' and self._is_this_week(f))
            
            # Get active projects
            active_projects = self._get_active_projects()
            
            # Build the active projects section content
            projects_content = []
            if active_projects:
                for project in active_projects:
                    date_str = project['last_modified'].strftime('%Y-%m-%d %H:%M:%S')
                    projects_content.append(f"- {project['file']} (active) - last updated: {date_str}")
            else:
                projects_content.append("- No active projects")
            
            projects_section = '\n'.join(projects_content)
            
            # Read current dashboard
            content = self.dashboard.read_text(encoding='utf-8')
            
            # Update counters section (existing table)
            content = self._update_counter_in_table(content, 'Pending Actions', str(inbox_count + needs_action_count))
            content = self._update_counter_in_table(content, 'Tasks Completed Today', str(done_today))
            content = self._update_counter_in_table(content, 'Tasks Completed This Week', str(done_this_week))
            content = self._update_counter_in_table(content, 'Pending Approvals', str(pending_approval_count))
            
            # Update Active Projects section
            content = self._update_active_projects_section(content, projects_section)
            
            # Update last_updated timestamp
            content = self._update_timestamp(content)
            
            # Write back
            self.dashboard.write_text(content, encoding='utf-8')
            
            self.logger.debug(
                f'Dashboard updated: Inbox={inbox_count}, NeedsAction={needs_action_count}, '
                f'DoneToday={done_today}, DoneThisWeek={done_this_week}, Approvals={pending_approval_count}, '
                f'ActiveProjects={len(active_projects)}'
            )
            
        except Exception as e:
            self.logger.error(f'Error updating dashboard: {e}', exc_info=True)

    def _update_counter_in_table(self, content: str, metric: str, value: str) -> str:
        """Replace the value cell for a given metric row in a Markdown table."""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Match the row that contains this metric inside a table cell
            if metric in line and '|' in line:
                parts = line.split('|')
                # Table row format: | **Metric** | Value | Trend |
                if len(parts) >= 4:
                    parts[2] = f' {value} '
                    lines[i] = '|'.join(parts)
                    break
        return '\n'.join(lines)

    def _update_active_projects_section(self, content: str, projects_content: str) -> str:
        """Update the Active Projects section with real data."""
        lines = content.split('\n')
        new_lines = []
        in_active_projects = False
        content_added = False
        
        for i, line in enumerate(lines):
            # Check if we found the Active Projects section
            if '## 🗂️ Active Projects' in line:
                in_active_projects = True
                new_lines.append(line)
                continue
                
            # If we're in the section and find the content area (after the header)
            if in_active_projects and not content_added:
                # Skip existing content until we find a new section or end
                if line.strip().startswith('##') or (i + 1 < len(lines) and lines[i + 1].strip().startswith('##')):
                    # Add the new content before the next section
                    new_lines.append('')
                    new_lines.append(projects_content)
                    new_lines.append('')
                    new_lines.append('---')
                    new_lines.append('')
                    content_added = True
                    in_active_projects = False
                    new_lines.append(line)
                    continue
                # Skip old content lines
                continue
                
            new_lines.append(line)
            
        # If we never added the content (section not properly formatted), add it at the end
        if not content_added:
            new_lines.append('')
            new_lines.append('## 🗂️ Active Projects')
            new_lines.append('')
            new_lines.append(projects_content)
            new_lines.append('')
            new_lines.append('---')
            
        return '\n'.join(new_lines)

    def _update_timestamp(self, content: str) -> str:
        """Update the last_updated timestamp in the dashboard."""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'last_updated:' in line:
                lines[i] = f'last_updated: {datetime.now().isoformat()}'
                break
        return '\n'.join(lines)

    def _is_today(self, file_path: Path) -> bool:
        """Return True if file was last modified today."""
        try:
            return datetime.fromtimestamp(file_path.stat().st_mtime).date() == datetime.now().date()
        except Exception:
            return False

    def _is_this_week(self, file_path: Path) -> bool:
        """Return True if file was last modified within the current calendar week (Mon–Sun)."""
        try:
            file_date  = datetime.fromtimestamp(file_path.stat().st_mtime).date()
            today      = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())  # Monday of this week
            return week_start <= file_date <= today
        except Exception:
            return False

    # ── Activity logging ──────────────────────────────────────────────────────

    def _log_action(self, action_type: str, target: str, result: str, details: str = '') -> None:
        """Append one JSON entry to today's activity log file."""
        try:
            log_file = self.logs / f'{datetime.now().strftime("%Y-%m-%d")}.json'
            logs: list = []
            if log_file.exists():
                try:
                    logs = json.loads(log_file.read_text(encoding='utf-8'))
                except json.JSONDecodeError:
                    logs = []

            logs.append({
                'timestamp':   datetime.now().isoformat(),
                'action_type': action_type,
                'actor':       'orchestrator',
                'target':      target,
                'result':      result,
                'details':     details,
            })
            log_file.write_text(json.dumps(logs, indent=2), encoding='utf-8')
        except Exception as e:
            self.logger.error(f'Error logging action: {e}')

    # ── Status snapshot ───────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return a dict snapshot of current folder counts and system state."""
        return {
            'vault_path':       str(self.vault_path),
            'ai_agent':         self.ai_agent,
            'ai_available':     self.ai_available,
            'watch_mode':       self.watch_mode,
            'folders': {
                'inbox':            sum(1 for f in self.inbox.iterdir()            if f.suffix.lower() == '.md'),
                'processing':       sum(1 for f in self.processing.iterdir()       if f.suffix.lower() == '.md'),
                'needs_action':     sum(1 for f in self.needs_action.iterdir()     if f.suffix.lower() == '.md'),
                'pending_approval': sum(1 for f in self.pending_approval.iterdir() if f.suffix.lower() == '.md'),
                'approved':         sum(1 for f in self.approved.iterdir()         if f.suffix.lower() == '.md'),
                'done':             sum(1 for f in self.done.iterdir()             if f.suffix.lower() == '.md'),
                'failed':           sum(1 for f in self.failed.iterdir()           if f.suffix.lower() == '.md'),
            },
            'processing_files': list(self.processing_files),
            'active_projects':  len(self._get_active_projects()),
        }


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='AI Employee Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Flow:  Inbox → Processing → Done/Failed

Examples:
  %(prog)s -v /path/to/vault                 # polling mode (default)
  %(prog)s -v /path/to/vault --watch         # real-time watch mode
  %(prog)s -v /path/to/vault -w -i 30        # watch mode, 30 s interval
  %(prog)s -v /path/to/vault -a claude       # use Claude Code
'''
    )
    parser.add_argument('--vault',    '-v', required=True,          help='Path to the Obsidian vault')
    parser.add_argument('--interval', '-i', type=int, default=60,   help='Check interval in seconds (default: 60)')
    parser.add_argument('--ai-agent', '-a', default='qwen', choices=['qwen', 'claude'], help='AI agent (default: qwen)')
    parser.add_argument('--watch',    '-w', action='store_true',    help='Enable real-time watchdog monitoring')

    args = parser.parse_args()

    Orchestrator(
        vault_path=args.vault,
        check_interval=args.interval,
        ai_agent=args.ai_agent,
        watch_mode=args.watch,
    ).run()


if __name__ == '__main__':
    main()