#!/usr/bin/env python
"""
TiDB Vector Document Processing System Entry File

This script serves as a convenient entry point for launching the Web UI, located in the rag directory.
"""

import os
import sys
import argparse
import subprocess


def main():
    """Process command line arguments and launch the Web UI"""
    # Get the directory of the current file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    web_ui_dir = os.path.join(current_dir, 'web_ui')
    
    # Check if the web_ui directory exists
    if not os.path.exists(web_ui_dir):
        print(f"Error: Cannot find web_ui directory: {web_ui_dir}")
        return 1
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Launch TiDB Vector Document Processing System')
    parser.add_argument('--host', default='127.0.0.1', help='Server host address, default is 127.0.0.1')
    parser.add_argument('--port', type=int, default=5000, help='Server port, default is 5000')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Display startup information
    print(f"""
======================================
   TiDB Vector Document Processing System
======================================

Service will start at: http://{args.host}:{args.port}
Debug mode: {'Enabled' if args.debug else 'Disabled'}

Press Ctrl+C to stop the service
    """)
    
    # Start web_ui/run.py
    run_script = os.path.join(web_ui_dir, 'run.py')
    
    # Build command line arguments
    command = [
        sys.executable,  # Current Python interpreter
        run_script,
        '--host', args.host,
        '--port', str(args.port)
    ]
    
    if args.debug:
        command.append('--debug')
    
    try:
        # Execute command
        subprocess.run(command, check=True)
        return 0
    except KeyboardInterrupt:
        print("\nService stopped")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\nError starting service: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
