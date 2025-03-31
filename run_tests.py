#!/usr/bin/env python3
"""
Script to run all tests in the tests directory.
Can be run as a standalone script or imported as a module.
"""

import os
import sys
import glob
import subprocess
from pathlib import Path


def run_tests(verbose=True):
    """
    Run all test_*.py files in the tests directory.
    
    Args:
        verbose: Whether to print detailed output.
        
    Returns:
        bool: True if all tests passed, False otherwise.
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # Find all executable test_*.py files in the tests directory
    test_pattern = os.path.join('tests', 'test_*.py')
    test_files = glob.glob(test_pattern)
    
    if verbose:
        print(f"Found {len(test_files)} test files in tests/ directory...")
        print("----------------------------------------")
    
    all_passed = True
    
    # Run each test file
    for test_file in test_files:
        if verbose:
            print(f"\nRunning {test_file}...")
            print("----------------------------------------")
        
        # Ensure the file is executable
        file_path = Path(test_file)
        if not os.access(file_path, os.X_OK):
            os.chmod(file_path, 0o755)
        
        # Run the test
        result = subprocess.run([f'./{test_file}'], capture_output=not verbose)
        
        # Check the exit status
        if result.returncode == 0:
            if verbose:
                print(f"✓ {test_file} passed")
        else:
            all_passed = False
            if verbose:
                print(f"✗ {test_file} failed")
                if not verbose:
                    # If we're not showing verbose output, show error output when a test fails
                    print(result.stdout.decode('utf-8'))
                    print(result.stderr.decode('utf-8'))
    
    if verbose:
        print("\n----------------------------------------")
        print("Test run complete.")
        
        if all_passed:
            print("All tests passed!")
        else:
            print("Some tests failed.")
    
    return all_passed


if __name__ == "__main__":
    success = run_tests(verbose=True)
    sys.exit(0 if success else 1)