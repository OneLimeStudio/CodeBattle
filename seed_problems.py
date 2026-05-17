from uuid import uuid4
from app.database import SessionLocal, Base, engine
from app.models import Problem, TestCase

def seed_problems():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Two Sum
    p1 = Problem(
        id=uuid4(),
        title="Two Sum",
        description="""Given an array of integers nums and an integer target,return the indices of the two numbers such that they add up to target. You may assume that each input has exactly one solution,and you may not use the same element twice.""",
        difficulty="Easy"
    )
    p1.test_cases = [
        TestCase(input={"nums": [2, 7, 11, 15], "target": 9}, output=[0, 1]),
        TestCase(input={"nums": [3, 2, 4], "target": 6}, output=[1, 2])
    ]

    # 2. Valid Palindrome
    p2 = Problem(
        id=uuid4(),
        title="Valid Palindrome",
        description="""Given a string s, determine if it is a palindrome,considering only alphanumeric characters and ignoring cases.""",
        difficulty="Easy"
    )
    p2.test_cases = [
        TestCase(input={"s": "A man, a plan, a canal: Panama"}, output=True),
        TestCase(input={"s": "race a car"}, output=False)
    ]

    # 3. Maximum Subarray
    p3 = Problem(
        id=uuid4(),
        title="Maximum Subarray",
        description="""Given an integer array nums,find the contiguous subarray with the largest sum,and return its sum.""",
        difficulty="Medium"
    )
    p3.test_cases = [
        TestCase(input={"nums": [-2,1,-3,4,-1,2,1,-5,4]}, output=6),
        TestCase(input={"nums": [1]}, output=1)
    ]

    # 4. Valid Parentheses
    p4 = Problem(
        id=uuid4(),
        title="Valid Parentheses",
        description="""Given a string s containing just the characters'(', ')', '{', '}', '[' and ']',determine if the input string is valid.""",
        difficulty="Medium"
    )
    p4.test_cases = [
        TestCase(input={"s": "()"}, output=True),
        TestCase(input={"s": "()[]{}"}, output=True),
        TestCase(input={"s": "(]"}, output=False)
    ]

    problems = [p1, p2, p3, p4]

    db.add_all(problems)
    db.commit()
    db.close()

    print("✅ Problems seeded successfully!")


if __name__ == "__main__":
    seed_problems()