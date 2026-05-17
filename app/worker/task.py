from celery import Celery
import resource
import json
import subprocess
import tempfile
import os
from uuid import UUID
from .. import models
from ..database import SessionLocal
from sqlalchemy.orm import Session

import os
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
cel = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
@cel.task
def judge_submission(code: str, language: str, match_id: str, test_cases: list):
    results = []
    db: Session = SessionLocal()
    try:
        for tc in test_cases:
            stdin = json.dumps(tc['input'])
            expected = tc['output']
            result = run_in_sandbox(code, language, stdin, expected)
            results.append(result)
            if result['verdict'] != 'accepted':
                break

        final_verdict = (
            'accepted'
            if all(r['verdict'] == 'accepted' for r in results)
            else results[-1]['verdict']
        )

        match_uuid = UUID(match_id)

        match_player = (
            db.query(models.MatchPlayer)
            .filter(
                models.MatchPlayer.match_id == match_uuid,
                models.MatchPlayer.verdict == 'pending',
            )
            .first()
        )

        if match_player:
            match_player.verdict = final_verdict

            if final_verdict == "accepted":
                match_player.elo_delta = 20
                winner = db.query(models.User).filter(
                    models.User.id == match_player.user_id
                ).first()
                if winner:
                    winner.elo += 20

                loser_player = (
                    db.query(models.MatchPlayer)
                    .filter(
                        models.MatchPlayer.match_id == match_uuid,
                        models.MatchPlayer.user_id != match_player.user_id
                    )
                    .first()
                )
                if loser_player:
                    loser_player.elo_delta = -20
                    loser = db.query(models.User).filter(
                        models.User.id == loser_player.user_id
                    ).first()
                    if loser:
                        loser.elo -= 20

                match = (
                    db.query(models.Match)
                    .filter(models.Match.id == match_uuid)
                    .first()
                )
                if match:
                    match.status = "finished"
                print(f"DEBUG: winner elo before commit: {winner.elo}")
        db.commit()
        return {"verdict": final_verdict, "results": results}

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
def detect_function_name(code: str):
    """Return the first top-level function name, or None if code is a plain script."""
    import ast
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                return node.name
    except SyntaxError:
        pass
    return None


def wrap_python(code: str):
    fn_name = detect_function_name(code)

    if fn_name is None:
        # Plain script: inject input data via patched input() and run as-is
        return """
import json, builtins as _builtins

_input_data = json.loads(_builtins.input())
_builtins.input = lambda *a: json.dumps(_input_data)

""" + code
    else:
        return f"""
import json

{code}

data = json.loads(input())

if isinstance(data, dict):
    result = {fn_name}(**data)
elif isinstance(data, list):
    result = {fn_name}(*data)
else:
    result = {fn_name}(data)

print(json.dumps(result))
"""
def wrap_javascript(code: str):
    import re
    # Look for function name in "function name(...) {" or "const name = (...) => {"
    match = re.search(r"function\s+([a-zA-Z0-9_]+)\s*\(", code)
    if not match:
        match = re.search(r"const\s+([a-zA-Z0-9_]+)\s*=\s*(async\s+)?\(", code)
    
    fn_name = match.group(1) if match else None

    if fn_name is None:
        return f"""
const fs = require('fs');
const _input_data = JSON.parse(fs.readFileSync(0, 'utf8'));
// Mock global input
global.input = () => JSON.stringify(_input_data);
{code}
"""
    else:
        return f"""
{code}
const fs = require('fs');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
let result;
if (typeof data === 'object' && !Array.isArray(data)) {{
    result = {fn_name}(data);
}} else if (Array.isArray(data)) {{
    result = {fn_name}(...data);
}} else {{
    result = {fn_name}(data);
}}
process.stdout.write(JSON.stringify(result));
"""

def run_in_sandbox(code: str, lang: str, stdin: str, expected) -> dict:

    with tempfile.NamedTemporaryFile(suffix=lang_suffix(lang), mode='w', delete=False) as f:
        if lang == "python":
            code = wrap_python(code)
        elif lang == "javascript":
            code = wrap_javascript(code)

    try:
        cmd = build_command(lang, fname)
        if cmd is None:
            return {'verdict': 'unsupported_language'}

        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=5,
            preexec_fn=set_resource_limits,
        )

        if proc.returncode != 0:
            return {'verdict': 'wrong', 'stderr': proc.stderr[:300]}

        output_raw = proc.stdout.strip()

        
        try:
            output_parsed = json.loads(output_raw)
            if output_parsed == expected:
                return {'verdict': 'accepted'}
        except (json.JSONDecodeError, ValueError):
            pass

        
        expected_str = json.dumps(expected, separators=(',', ':')) if not isinstance(expected, str) else expected.strip()
        if output_raw == expected_str:
            return {'verdict': 'accepted'}

        
        if output_raw == str(expected):
            return {'verdict': 'accepted'}

        return {'verdict': 'wrong', 'got': output_raw, 'expected': str(expected)}

    except subprocess.TimeoutExpired:
        return {'verdict': 'tle'}
    finally:
        
        os.unlink(fname)
        
        base = fname.rsplit('.', 1)[0]
        for ext in ['', '.class', '.out']:
            path = base + ext
            if path != fname and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass


def lang_suffix(lang: str) -> str:
    return {
        'python': '.py',
        'javascript': '.js',
        'cpp': '.cpp',
        'java': '.java',
    }.get(lang, '.py')


def build_command(lang: str, fname: str):
    """Return the subprocess command list for the given language."""
    if lang == 'python':
        return ['python3', fname]
    if lang == 'javascript':
        return ['node', fname]
    if lang == 'cpp':
        out = fname.replace('.cpp', '.out')
        # compile first (blocking), then return run command
        compile_proc = subprocess.run(
            ['g++', '-O2', '-o', out, fname],
            capture_output=True, text=True, timeout=10
        )
        if compile_proc.returncode != 0:
            # surface compile error as runtime_error upstream
            raise RuntimeError(f"Compile error: {compile_proc.stderr[:200]}")
        return [out]
    if lang == 'java':
        compile_proc = subprocess.run(
            ['javac', fname],
            capture_output=True, text=True, timeout=10
        )
        if compile_proc.returncode != 0:
            raise RuntimeError(f"Compile error: {compile_proc.stderr[:200]}")
        classdir = os.path.dirname(fname)
        return ['java', '-cp', classdir, 'Solution']
    return None


def set_resource_limits():
    try:
        resource.setrlimit(resource.RLIMIT_AS,    (256 * 1024 * 1024, 256 * 1024 * 1024))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU,   (5, 5))
    except (ValueError, resource.error):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    except (ValueError, resource.error):
        pass