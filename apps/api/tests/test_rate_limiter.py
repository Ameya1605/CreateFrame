import pytest
from fastapi import HTTPException
from main import UserRateLimiter

def test_user_rate_limiter():
    limiter = UserRateLimiter(max_requests=3, window_seconds=60)
    user_id = 999
    
    # 3 allowed
    limiter.check(user_id)
    limiter.check(user_id)
    limiter.check(user_id)
    
    # 4th should raise HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(user_id)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail

    # Another user is not affected
    other_user = 1000
    limiter.check(other_user)  # Does not raise
