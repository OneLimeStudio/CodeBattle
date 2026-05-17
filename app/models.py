from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum,JSON,Text
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    elo = Column(Integer,default=1000)

class Problem(Base):
    __tablename__ = "problems"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    difficulty = Column(String(10))  
    test_cases = relationship("TestCase", back_populates="problem", cascade="all, delete-orphan")

class TestCase(Base):
    __tablename__ = "test_cases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    problem_id = Column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    input = Column(JSON, nullable=False)
    output = Column(JSON, nullable=False)
    is_hidden = Column(Integer, default=0) # 0 for public, 1 for hidden
    
    problem = relationship("Problem", back_populates="test_cases")

class Match(Base):
    __tablename__ = "matches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    problem_id = Column(UUID(as_uuid=True), ForeignKey("problems.id"), nullable=False)
    status = Column(Enum("waiting", "active", "finished", name="match_status"), default="waiting")
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    players = relationship("MatchPlayer", back_populates="match",cascade="all, delete-orphan")

class MatchPlayer(Base):
    __tablename__ = "match_players"
    
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    verdict = Column(Enum("accepted", "wrong", "tle", "pending", name="verdict_status"), default="pending")
    submitted_at = Column(DateTime, nullable=True)
    elo_delta = Column(Integer, default=0)
    
    match = relationship("Match", back_populates="players")
    user = relationship("User")