#!/usr/bin/env python
"""
TiDB Vector Document Processing System Startup Script

Usage:
    python run.py [--host HOST] [--port PORT] [--debug]

Parameters:
    --host HOST     Specify host address, default is 127.0.0.1
    --port PORT     Specify port, default is 5000
    --debug         Enable debug mode
"""

import argparse
from app import app


def main():
    """Parse command line arguments and start the Flask application"""
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

Service started at: http://{args.host}:{args.port}
Debug mode: {'Enabled' if args.debug else 'Disabled'}

Press Ctrl+C to stop the service
    """)
    
    # Start Flask application
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == "__main__":
    main() 