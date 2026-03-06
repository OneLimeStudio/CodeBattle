from uuid import uuid4
from app.database import SessionLocal
from app.models import Problem  # adjust import if needed

def seed_problems():
    db = SessionLocal()
    
    problems = [

        Problem(
            id=uuid4(),
            title="Two Sum",
            description="""Given an array of integers nums and an integer target,return the indices of the two numbers such that they add up to target. You may assume that each input has exactly one solution,and you may not use the same element twice.""",
            difficulty="Easy",
            test_cases=[
                {
                    "input": {"nums": [2, 7, 11, 15], "target": 9},
                    "output": [0, 1]
                },
                {
                    "input": {"nums": [3, 2, 4], "target": 6},
                    "output": [1, 2]
                }
            ]
        ),

        Problem(
            id=uuid4(),
            title="Valid Palindrome",
            description="""Given a string s, determine if it is a palindrome,considering only alphanumeric characters and ignoring cases.""",
            difficulty="Easy",
            test_cases=[
                {
                    "input": {"s": "A man, a plan, a canal: Panama"},
                    "output": True
                },
                {
                    "input": {"s": "race a car"},
                    "output": False
                }
            ]
        ),

        Problem(
            id=uuid4(),
            title="Maximum Subarray",
            description="""Given an integer array nums,find the contiguous subarray with the largest sum,and return its sum.""",
            difficulty="Medium",
            test_cases=[
                {
                    "input": {"nums": [-2,1,-3,4,-1,2,1,-5,4]},
                    "output": 6
                },
                {
                    "input": {"nums": [1]},
                    "output": 1
                }
            ]
        ),

        Problem(
            id=uuid4(),
            title="Valid Parentheses",
            description="""Given a string s containing just the characters'(', ')', '{', '}', '[' and ']',determine if the input string is valid.""",
            difficulty="Medium",
            test_cases=[
                {
                    "input": {"s": "()"},
                    "output": True
                },
                {
                    "input": {"s": "()[]{}"},
                    "output": True
                },
                {
                    "input": {"s": "(]"},
                    "output": False
                }
            ]
        ),
    ]

    db.add_all(problems)
    db.commit()
    db.close()

    print("✅ Problems seeded successfully!")


seed_problems()