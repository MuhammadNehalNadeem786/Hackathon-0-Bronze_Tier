"""
AI Employee Demo with Qwen Code

This script demonstrates the Bronze Tier workflow:
1. Creates a test file in the Drop folder
2. Filesystem Watcher detects it and creates an action file
3. Qwen Code processes the action file
4. File is moved to Done

Run this script to see the AI Employee in action!
"""

import sys
import time
from pathlib import Path

# Add watchers directory to path
sys.path.insert(0, str(Path(__file__).parent / 'watchers'))

from filesystem_watcher import FilesystemWatcher
from orchestrator import Orchestrator


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60 + "\n")


def print_step(step_num, text):
    """Print a step in the process."""
    print(f"\n[Step {step_num}] {text}")
    print("-" * 40)


def main():
    """Run the AI Employee demo."""
    print_header("AI Employee v0.1 (Bronze Tier) - Qwen Code Demo")
    
    # Get vault path
    vault_path = Path(__file__).parent.parent / 'AI_Employee_Vault'
    
    if not vault_path.exists():
        print(f"ERROR: Vault not found at {vault_path}")
        print("Please ensure the AI_Employee_Vault folder exists.")
        return 1
    
    print(f"Vault Path: {vault_path}")
    
    # Step 1: Create a test file
    print_step(1, "Creating a test file in the Drop folder")
    
    drop_folder = vault_path / 'Drop'
    drop_folder.mkdir(parents=True, exist_ok=True)
    
    test_file = drop_folder / 'demo_task.txt'
    test_content = """This is a demo task for the AI Employee.

Please analyze this text and:
1. Summarize the content
2. Identify any action items
3. Create a plan to process this task
4. Move the file to Done when complete

Thank you, AI Employee!
"""
    
    test_file.write_text(test_content, encoding='utf-8')
    print(f"✓ Created: {test_file}")
    print(f"  Content: {len(test_content)} characters")
    
    # Step 2: Initialize and run the Filesystem Watcher
    print_step(2, "Starting Filesystem Watcher to detect the file")
    
    watcher = FilesystemWatcher(
        vault_path=str(vault_path),
        check_interval=5  # Check every 5 seconds for demo
    )
    
    print("Watcher initialized. Checking for new files...")
    
    # Check for new files (simulating the watcher loop)
    items = watcher.check_for_updates()
    
    if items:
        print(f"✓ Detected {len(items)} new file(s)")
        for item in items:
            print(f"  - {item.name} ({item.size} bytes)")
            
            # Create action file
            print("\nCreating action file...")
            action_file = watcher.create_action_file(item)
            if action_file:
                print(f"✓ Action file created: {action_file.name}")
    else:
        print("⚠ No new files detected (may have been processed already)")
        action_file = None
    
    # Step 3: Initialize and run the Orchestrator
    print_step(3, "Starting Orchestrator to process the action file")
    
    orchestrator = Orchestrator(
        vault_path=str(vault_path),
        check_interval=5,  # Check every 5 seconds for demo
        ai_agent='qwen'    # Use Qwen Code
    )
    
    print(f"Orchestrator initialized (AI Agent: {orchestrator.ai_agent})")
    print(f"AI Available: {orchestrator.ai_available}")
    
    # Process Needs_Action folder
    print("\nProcessing Needs_Action folder...")
    orchestrator._process_needs_action()
    
    # Step 4: Check results
    print_step(4, "Checking results")
    
    # Check if plan was created
    plans_folder = vault_path / 'Plans'
    plan_files = list(plans_folder.glob('PLAN_*.md'))
    
    if plan_files:
        latest_plan = max(plan_files, key=lambda p: p.stat().st_mtime)
        print(f"✓ Plan created: {latest_plan.name}")
        
        # Read and display plan content
        plan_content = latest_plan.read_text(encoding='utf-8')
        print("\nPlan Content:")
        print("-" * 40)
        print(plan_content[:500] + "..." if len(plan_content) > 500 else plan_content)
    else:
        print("⚠ No plan files created yet")
    
    # Check logs
    print("\n" + "-" * 40)
    print("Recent Log Entries:")
    print("-" * 40)
    
    logs_folder = vault_path / 'Logs'
    log_files = sorted(logs_folder.glob('orchestrator_*.log'))
    
    if log_files:
        latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
        log_content = latest_log.read_text(encoding='utf-8')
        # Show last 10 lines
        lines = log_content.strip().split('\n')
        for line in lines[-10:]:
            print(f"  {line}")
    else:
        print("  No log entries yet")
    
    # Step 5: Summary
    print_header("Demo Summary")
    
    print("Folders:")
    print(f"  /Drop: {len(list(drop_folder.iterdir()))} items")
    print(f"  /Needs_Action: {len(list((vault_path / 'Needs_Action').iterdir()))} items")
    print(f"  /Plans: {len(list(plans_folder.iterdir()))} items")
    print(f"  /Done: {len(list((vault_path / 'Done').iterdir()))} items")
    
    print("\n✓ Demo completed!")
    print("\nNext Steps:")
    print("  1. Open the Obsidian vault to see the files")
    print("  2. Review the action file in /Needs_Action")
    print("  3. Review the plan file in /Plans")
    print("  4. Qwen Code can now process the action file")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
