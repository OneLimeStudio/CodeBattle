from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import SessionLocal
from . import models
from uuid import UUID
from asyncio import Lock
from .auth import create_token, get_current_user
from .encrypt import hash_password, verify_password
from .schemas import SubmissionRequest, UserCreate, LoginRequest
from .worker import task
from typing import Optional

lock = Lock()
default_elo = 1000
app = FastAPI()
matched_players = {}
a = {}
threshold = 200

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_random_problem(db: Session):
    return (
        db.query(models.Problem)
        .order_by(func.random())
        .first()
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/users/")
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    enc = hash_password(body.password)
    user = models.User(name=body.name, email=body.email, password=enc,elo=default_elo)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": str(user.id), "name": user.name, "email": user.email}


@app.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "name": user.name, "email": user.email}
    }


@app.get("/me")
def get_me(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": str(user.id), "name": user.name, "email": user.email}


# ── Problems ──────────────────────────────────────────────────────────────────

@app.get("/problems")
def list_problems(db: Session = Depends(get_db)):
    problems = db.query(models.Problem).all()
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "description": p.description,
            "difficulty": p.difficulty,
        }
        for p in problems
    ]


# ── Match ─────────────────────────────────────────────────────────────────────

@app.get("/match/{id}")
def get_match(id: UUID, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.id == id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    problem = db.query(models.Problem).filter(models.Problem.id == match.problem_id).first()
    players = []
    for mp in match.players:
        user = db.query(models.User).filter(models.User.id == mp.user_id).first()
        players.append({
            "user_id": str(mp.user_id),
            "name": user.name if user else "Unknown",
            "verdict": mp.verdict,
            "elo_delta": mp.elo_delta,
        })
    return {
        "match_id": str(match.id),
        "status": match.status,
        "players": players,
        "problem": {
            "id": str(problem.id),
            "title": problem.title,
            "description": problem.description,
            "difficulty": problem.difficulty,
        } if problem else None
    }


@app.get("/match/{id}/result/{user_id}")
def get_match_result(id: UUID, user_id: UUID, db: Session = Depends(get_db)):
    """Poll this to check if submission has been judged."""
    match = db.query(models.Match).filter(models.Match.id == id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    players = []
    my_verdict = None
    for mp in match.players:
        user = db.query(models.User).filter(models.User.id == mp.user_id).first()
        entry = {
            "user_id": str(mp.user_id),
            "name": user.name if user else "Unknown",
            "verdict": mp.verdict,
            "elo_delta": mp.elo_delta,
        }
        players.append(entry)
        if str(mp.user_id) == str(user_id):
            my_verdict = mp.verdict

    all_judged = all(p["verdict"] != "pending" for p in players)

    return {
        "match_id": str(match.id),
        "status": match.status,
        "my_verdict": my_verdict,
        "all_judged": all_judged,
        "players": players,
    }


def make_match(waiting_id: UUID, matching_id: UUID, db: Session):
    if waiting_id == matching_id:
        raise HTTPException(status_code=404, detail="Same Matching and waiting ID")
    problem = get_random_problem(db)
    if not problem:
        return None

    match = models.Match(
        problem_id=problem.id,
        status="active"
    )
    match.players = [
        models.MatchPlayer(user_id=waiting_id),
        models.MatchPlayer(user_id=matching_id)
    ]
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@app.post("/match/{id}/submit")
def submit(
    id: UUID,
    req: SubmissionRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    match = db.query(models.Match).filter(models.Match.id == id).first()
    if match.status == "finished":
        raise HTTPException(status_code=400, detail="Match already finished")
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    problem = db.query(models.Problem).filter(models.Problem.id == match.problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    task.judge_submission.delay(req.code, req.language, str(match.id), problem.test_cases)
    return {
        "message": "Submission received",
        "match_id": str(id),
        "problem_id": str(problem.id),
    }

@app.get("/queue/status")
async def queue_status(user_id: str = Depends(get_current_user)):
    if user_id in matched_players:
        match_id = matched_players.pop(user_id)  # consume it
        return {"status": "matched", "match_id": match_id}
    if UUID(user_id) in a.values():
        return {"status": "waiting"}
    return {"status": "not_in_queue"}
@app.post("/queue/join")
async def join_queue(
    user_id: str = Depends(get_current_user),
    elo: int = 1000,
    db: Session = Depends(get_db)
):
    """Join matchmaking queue. Returns match_id if matched, else 'waiting'."""
    matching_id = UUID(user_id)
    async with lock:
        for waiting_elo, waiting_id in list(a.items()):
            if abs(waiting_elo - elo) < threshold:
                del a[waiting_elo]
                match = make_match(waiting_id=waiting_id, matching_id=matching_id, db=db)
                matched_players[str(waiting_id)] = str(match.id)
                matched_players[str(matching_id)] = str(match.id)
                return {
                    "status": "matched",
                    "match_id": str(match.id) if match else None,
                }
        a[elo] = matching_id
        return {"status": "waiting", "message": "In queue, waiting for opponent..."}


@app.delete("/queue/leave")
async def leave_queue(user_id: str = Depends(get_current_user)):
    """Remove self from queue."""
    uid = UUID(user_id)
    async with lock:
        for elo, uid_in_queue in list(a.items()):
            if uid_in_queue == uid:
                del a[elo]
                return {"status": "removed"}
    return {"status": "not_in_queue"}


# ── Solo Practice (no opponent needed) ───────────────────────────────────────
@app.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.elo.desc()).all()
    return users


@app.post("/practice/{problem_id}/submit")
def practice_submit(
    problem_id: UUID,
    req: SubmissionRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit code against a single problem without a match."""
    problem = db.query(models.Problem).filter(models.Problem.id == problem_id).first()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Create a solo match for tracking
    match = models.Match(problem_id=problem.id, status="active")
    match.players = [models.MatchPlayer(user_id=UUID(user_id))]
    db.add(match)
    db.commit()
    db.refresh(match)

    task.judge_submission.delay(req.code, req.language, str(match.id), problem.test_cases)
    return {
        "message": "Submission received",
        "match_id": str(match.id),
        "problem_id": str(problem.id),
    }