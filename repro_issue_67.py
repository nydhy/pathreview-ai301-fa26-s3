"""
Standalone reproduction for issue #67: Review creation does not verify
profile ownership.

Run with: .venv/bin/python repro_issue_67.py (after `pip install -e ".[dev]"`)

Uses the same mocked-async-session pattern as the repo's own
tests/unit/test_review_service.py (no live Postgres/Docker required).
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from core.services.review_service import create_review, get_review


async def main():
    db = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()

    user_a = uuid4()  # the authenticated caller
    user_b = uuid4()  # a different user
    profile_of_b = uuid4()  # a profile that belongs to user_b, not user_a

    print(f"user_a (caller):        {user_a}")
    print(f"user_b (profile owner): {user_b}")
    print(f"profile_of_b:           {profile_of_b}")
    print()

    # --- Exploit: user_a calls create_review with user_b's profile_id ---
    with patch("core.services.review_service.Review") as MockReview:
        instance = MockReview.return_value
        instance.status = "pending"
        result = await create_review(db, profile_id=profile_of_b, user_id=user_a)

        call_kwargs = MockReview.call_args[1]
        print("=== create_review(profile_id=profile_of_b, user_id=user_a) ===")
        print(f"Review constructed with profile_id={call_kwargs['profile_id']}")
        print(f"db.execute call count during create_review: {db.execute.call_count}")
        print(f"-> Review created for user_b's profile while acting as user_a,")
        print(f"   with ZERO queries against the profiles table to check ownership.")
    print()

    # --- Control: get_review DOES check ownership via a Profile.user_id join ---
    db2 = AsyncMock()
    mock_result = Mock()
    mock_result.scalars.return_value.first.return_value = None
    db2.execute = AsyncMock(return_value=mock_result)

    review_id = uuid4()
    await get_review(db2, review_id, user_id=user_a)

    executed_stmt = db2.execute.call_args[0][0]
    compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": False}))
    print("=== get_review(review_id, user_id=user_a) [control] ===")
    print(f"db.execute call count during get_review: {db2.execute.call_count}")
    print("Compiled SQL WHERE clause references Profile.user_id:")
    print(f"  {'profiles.user_id' in compiled}")
    print(compiled)


if __name__ == "__main__":
    asyncio.run(main())
