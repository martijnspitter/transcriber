#!/usr/bin/env python
"""
Backend execution wrapper that ensures proper cleanup of Python resources.
This script wraps the main application startup to provide proper signal handling
and resource cleanup when the application is terminated.
"""

import sys
import signal
import atexit
import logging
import multiprocessing

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Dictionary to keep track of active processes/threads/resources
active_resources = {
    "processes": [],
    "threads": []
}

def cleanup_resources():
    """Clean up all registered resources before exit"""
    logger.info("Cleaning up resources...")

    # Clean up processes
    for proc in active_resources["processes"]:
        if proc.is_alive():
            logger.info(f"Terminating process {proc.name}")
            proc.terminate()
            proc.join(timeout=1.0)
            if proc.is_alive():
                logger.warning(f"Force killing process {proc.name}")
                proc.kill()

    # Clean up threads in active_resources
    for thread in active_resources["threads"]:
        if thread.is_alive():
            logger.info(f"Thread {thread.name} is still running")
            # Threads cannot be forcibly terminated in Python
            # Just log that they're still running for diagnostic purposes

    # Use the correct way to clean up multiprocessing resources
    try:
        # Access the children through the process object properly
        # to avoid the attribute error with _children
        children = multiprocessing.active_children()
        for child in children:
            if child.is_alive():
                logger.info(f"Terminating child process {child.name}")
                child.terminate()
                child.join(timeout=1.0)
    except Exception as e:
        logger.warning(f"Could not clear multiprocessing children: {e}")

    logger.info("Cleanup complete")

def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {sig}, shutting down...")
    cleanup_resources()
    sys.exit(0)

def register_process(process):
    """Register a process for cleanup"""
    active_resources["processes"].append(process)

def register_thread(thread):
    """Register a thread for cleanup"""
    active_resources["threads"].append(thread)

def main():
    """Main entry point that runs the application with proper cleanup"""
    # Register cleanup handlers
    atexit.register(cleanup_resources)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Import and run the main application
    logger.info("Starting application...")

    try:
        # Run the uvicorn server directly
        import uvicorn
        import multiprocessing

        # Use multiprocessing to start uvicorn in its own process
        server_process = multiprocessing.Process(
            target=uvicorn.run,
            kwargs={
                "app": "app.main:app",
                "host": "0.0.0.0",
                "port": 8000,
                "reload": True,
                "log_level": "info"
            },
            daemon=True,
            name="uvicorn-server"
        )

        # Register process for cleanup
        register_process(server_process)

        # Start the server
        server_process.start()
        logger.info(f"Started Uvicorn server (PID: {server_process.pid})")

        # Wait for the server process to finish
        server_process.join()

    except Exception as e:
        logger.error(f"Failed to run application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
