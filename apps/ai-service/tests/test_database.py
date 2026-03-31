"""Database module tests (unit, no live DB)."""
from app.core.database import Base, get_db


def test_base_exists() -> None:
    assert Base is not None


def test_get_db_is_async_generator_function() -> None:
    import inspect
    assert inspect.isasyncgenfunction(get_db)
