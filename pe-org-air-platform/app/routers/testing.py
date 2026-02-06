from fastapi import APIRouter, HTTPException
import subprocess
import os
import json
from datetime import datetime

router = APIRouter()

@router.post("/run-tests")
async def run_system_tests():
    """
    Triggers the internal test suite and returns the captured output.
    """
    try:
        # Run pytest on the tests directory
        # We use -v for verbose output so we can see each test case
        process = subprocess.run(
            ["pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120 # 2 minute timeout
        )
        
        # Analyze the output to provide a summary
        output = process.stdout + process.stderr
        success = process.returncode == 0
        
        # Simple parsing for a summary
        lines = output.split('\n')
        summary = "No summary found"
        for line in reversed(lines):
            if "passed" in line and "failed" in line:
                summary = line
                break
        
        return {
            "status": "success" if success else "failed",
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "raw_output": output,
            "exit_code": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Tests timed out after 120 seconds",
            "raw_output": "Timeout exceeded while running tests."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
