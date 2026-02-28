"""
Test & Debug, Test Writer, and QA subagents.
Tools: read/write files, run pytest, list files, inspect failures.
Main agent routes here when the task is writing tests, debugging, or verification.
"""

import os
import subprocess
from pathlib import Path


def list_files(path: str, max_entries: int = 100) -> dict:
    """List files under path (workspace root or subdir). Returns list of relative paths."""
    root = Path(path).resolve()
    if not root.exists():
        return {"error": f"Path does not exist: {root}", "files": []}
    files = []
    for p in root.rglob("*"):
        if len(files) >= max_entries:
            break
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts:
            try:
                files.append(str(p.relative_to(root)))
            except ValueError:
                files.append(str(p))
    return {"path": str(root), "files": files[:max_entries]}


def read_file(path: str, max_lines: int = 500) -> dict:
    """Read file contents. path can be relative to workspace root."""
    p = Path(path).resolve()
    if not p.exists() or not p.is_file():
        return {"error": f"File not found or not a file: {p}", "content": None}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        return {"path": str(p), "content": "\n".join(lines[:max_lines]), "total_lines": len(lines)}
    except Exception as e:
        return {"error": str(e), "content": None}


def write_file(path: str, content: str) -> dict:
    """Write content to file. path can be relative to workspace root."""
    p = Path(path).resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"path": str(p), "written": True}
    except Exception as e:
        return {"error": str(e), "written": False}


def run_pytest(workspace_root: str, args: str = "-v --tb=short") -> dict:
    """Run pytest in workspace_root. Returns stdout, stderr, returncode."""
    root = Path(workspace_root).resolve()
    if not root.exists():
        return {"error": f"Workspace does not exist: {root}", "returncode": -1}
    cmd = ["pytest", *args.split()]
    try:
        r = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "returncode": r.returncode,
            "stdout": r.stdout[-5000:] if r.stdout else "",
            "stderr": r.stderr[-2000:] if r.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"error": "pytest timed out (120s)", "returncode": -1}
    except FileNotFoundError:
        return {"error": "pytest not found", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}


def run_test_debug(question: str, workspace_root: str) -> dict:
    """
    Test & Debug subagent: write tests, debug code, inspect errors.
    Uses list_files, read_file, write_file, run_pytest.
    """
    q = (question or "").lower()
    result = {"action": "test_debug", "summary": "", "details": {}}
    if "run test" in q or "run pytest" in q or "run tests" in q:
        details = run_pytest(workspace_root)
        result["details"] = details
        result["summary"] = f"pytest returncode={details.get('returncode', -1)}; " + (details.get("stdout", "")[:200] or details.get("error", ""))
    elif "list" in q or "files" in q:
        details = list_files(workspace_root)
        result["details"] = details
        result["summary"] = f"Listed {len(details.get('files', []))} files under {details.get('path', '')}"
    else:
        result["summary"] = "Test & Debug ready. Use tools: list_files, read_file, write_file, run_pytest. Ask to 'run tests' or 'list files'."
    return result


def run_test_writer(question: str, workspace_root: str) -> dict:
    """
    Test Writer subagent: create and maintain test suites, expand coverage.
    """
    result = {"action": "test_writer", "summary": "", "details": {}}
    details = list_files(workspace_root)
    result["details"] = details
    result["summary"] = f"Test Writer: {len(details.get('files', []))} files in workspace. Use read_file to inspect modules, write_file to add test files, run_pytest to verify."
    return result


def run_qa(question: str, workspace_root: str) -> dict:
    """
    QA and Verification subagent: run tests, reproduce bugs, verify fixes.
    """
    details = run_pytest(workspace_root)
    return {
        "action": "qa",
        "summary": f"QA: pytest returncode={details.get('returncode', -1)}",
        "details": details,
    }
