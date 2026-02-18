"""asyncpg connection pool management."""

import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def create_pool(database_url: str, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """Create and return the global asyncpg connection pool.

    Args:
        database_url: PostgreSQL connection string.
        min_size: Minimum number of connections in the pool.
        max_size: Maximum number of connections in the pool.

    Returns:
        The asyncpg connection pool.
    """
    global _pool
    if _pool is not None:
        return _pool

    logger.info("Creating database connection pool (min=%d, max=%d)", min_size, max_size)
    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=min_size,
        max_size=max_size,
    )
    logger.info("Database connection pool created successfully")
    return _pool


def get_pool() -> asyncpg.Pool:
    """Return the global connection pool. Raises if not initialised."""
    if _pool is None:
        raise RuntimeError("Database pool has not been initialised. Call create_pool() first.")
    return _pool


async def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        logger.info("Closing database connection pool")
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")
