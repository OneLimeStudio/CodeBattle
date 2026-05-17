# CodeBattle: In-Depth Technical Architecture & Design Decisions

This document breaks down every technical aspect of the CodeBattle project, explaining not only **how** things are implemented, but **why** specific architectural and design choices were made.

---

## 1. Distributed Execution Architecture

**What it is:** The application is split into a Web Server (FastAPI) and a Background Worker (Celery), using Redis as a message broker to pass tasks between them.

**Why it's done this way:**
- **Non-blocking web requests:** Code execution is inherently unpredictable. User submissions might take seconds to run (or time out). If the FastAPI server executed code synchronously, the web server would quickly run out of worker threads, blocking all other users from joining queues or loading pages.
- **Security & Isolation:** By deferring execution to a separate Celery worker, the execution environment can be physically separated (e.g., a different Docker container or server) from the database and web API, minimizing the blast radius if a user escapes the sandbox.

---

## 2. Matchmaking Engine (`app/main.py`)

**What it is:** A system that pairs two users with similar ELO ratings. Currently implemented using an in-memory dictionary (`a = {}`) keyed by ELO rating and an `asyncio.Lock()`.

**Why it's done this way:**
- **In-Memory Speed:** Matchmaking queues require extremely frequent read/write operations as users poll for status or join/leave. An in-memory dictionary is exponentially faster than querying a PostgreSQL database.
- **Concurrency Control (`asyncio.Lock`):** Because multiple HTTP requests can try to match users simultaneously, the lock ensures that a user isn't accidentally matched in two different games at the exact same millisecond. 
- **Tolerance Band (`threshold = 200`):** It checks `abs(waiting_elo - elo) < threshold`. This ensures matches are competitive.

*Trade-off:* Currently, scaling the FastAPI server to multiple instances (e.g., 4 Gunicorn workers) would break the in-memory queue. In a production environment with multiple web nodes, this dictionary would be replaced by Redis.

---

## 3. Database Design (`app/models.py`)

### 3.1. UUID Primary Keys
**What it is:** Every table (`users`, `problems`, `matches`) uses UUIDv4 instead of auto-incrementing integers (1, 2, 3...).
**Why:** 
- **Security (IDOR Prevention):** If match IDs were `1`, `2`, `3`, users could easily guess the IDs of other private matches and poll their states. UUIDs are unguessable.

### 3.2. JSON Columns for Test Cases
**What it is:** In `TestCase`, the `input` and `output` fields are stored as JSON data types.
**Why:**
- **Flexibility:** Coding problems have wildly different inputs. One problem might take an array of integers and a single integer target (`{"nums": [2, 7], "target": 9}`), while another takes a string (`{"s": "test"}`). Using a JSON column allows the schema to handle any data structure without needing complex, normalized relationship tables for every possible parameter type.

### 3.3. Enums for Status States
**What it is:** The database enforces states: `Enum("waiting", "active", "finished")` for matches and `Enum("accepted", "wrong", "tle", "pending")` for submission verdicts.
**Why:**
- **Data Integrity:** It physically prevents the application code from accidentally setting a match status to a typo like `"finisehd"`, ensuring database-level strictness.

---

## 4. The Secure Code Sandbox (`app/worker/task.py`)

This is the most critical and complex part of a competitive programming judge. Because users submit arbitrary, untrusted code, it must be executed aggressively constrained.

### 4.1. OS-Level Resource Limits (`resource.setrlimit`)
Before the user's code executes, the worker process invokes `resource.setrlimit` (which interacts with Linux kernel limits).
**Why:**
- `RLIMIT_CPU (5 seconds)`: Prevents infinite loops (`while True: pass`) from tying up the server forever. If it hits 5 seconds, the OS kills it (Time Limit Exceeded - TLE).
- `RLIMIT_AS (256MB)`: Prevents Memory Limit Exceeded attacks. If a user tries to allocate `[0] * 10**10`, the kernel kills the process before it crashes the Celery worker.
- `RLIMIT_NOFILE (64)`: Restricts the number of file descriptors. Prevents the user from performing denial-of-service attacks by trying to open thousands of files or network sockets.

### 4.2. Smart Code Wrapping (`wrap_python`, `wrap_javascript`)
**What it is:** The system uses AST (Abstract Syntax Trees) in Python or Regex in JS to detect if the user wrote a standalone script or a function (e.g., `def twoSum(nums, target):`). It then dynamically injects boilerplate code invisibly around the user's code.
**Why:**
- **Developer Experience (DX):** Users expect to just write a function and return a value (like on LeetCode). The injected code handles reading `stdin` as JSON, extracting the variables, passing them to the user's function, and printing the returned value as a JSON string to `stdout`.

### 4.3. Standard I/O Process Communication (`subprocess.run`)
**What it is:** The judge passes the `TestCase.input` JSON as a string into the standard input (`stdin`) of the executed process and captures the `stdout`.
**Why:**
- Universal compatibility. Instead of trying to inject Python objects directly into an isolated process, text streams (stdin/stdout) are universally understood by all languages (Python, JS, C++, Java), making it easy to add new languages.

### 4.4 ELO Calculation in the Worker
**What it is:** The actual +20 / -20 ELO point calculation is processed at the end of `judge_submission` in `task.py`.
**Why:**
- This prevents concurrency issues where a user might submit multiple times rapidly. By doing it immediately after the final test case evaluates to 'accepted' and marking the match as 'finished' within the same database transaction, it prevents players from getting double points for double submissions.

---

## 5. Security & Authentication (`auth.py`)

**What it is:** The system uses JWT (JSON Web Tokens) rather than session cookies stored in the database.
**Why:**
- **Statelessness:** The FastAPI server can verify who the user is using purely cryptographic math. It doesn't have to look up the database for every single API request just to check if a session ID is valid. This heavily reduces database load.
- **Passwords:** Passwords are hashed before database insertion. A breached database will only reveal hashes, protecting users who reuse passwords.

---

## Summary of the Engineering Philosophy

The entire stack is designed around three goals:
1. **Asynchronous Execution:** Never block a user waiting on someone else's code to run (FastAPI + Celery).
2. **Zero-Trust Input:** Never trust user code. Limit what it can access and use OS kernel limits to kill it if it misbehaves (`resource.setrlimit`).
3. **Frictionless UX:** Wrap the code automatically so the user just focuses on the algorithm, not writing standard I/O parsers (`wrap_python`).
