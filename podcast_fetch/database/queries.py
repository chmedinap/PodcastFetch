"""
Database query utility functions.
"""

import sqlite3
import re
from typing import Optional, Tuple
from podcast_fetch.config import EPISODE_STATUS_DOWNLOADED


def validate_and_quote_table_name(table_name: str) -> str:
    """
    Validate and safely quote a table name for use in SQL queries.
    
    This function prevents SQL injection by ensuring table names contain only
    safe characters (alphanumeric and underscores) and then quotes them properly.
    
    Parameters:
    table_name: The table name to validate and quote
    
    Returns:
    A safely quoted table name
    
    Raises:
    ValueError: If the table name contains invalid characters
    
    Example:
        >>> validate_and_quote_table_name("my_podcast")
        '"my_podcast"'
        >>> validate_and_quote_table_name("invalid-name")
        ValueError: Invalid table name
    """
    if not table_name or not isinstance(table_name, str):
        raise ValueError(f"Table name must be a non-empty string, got: {type(table_name)}")
    
    # Table names should only contain alphanumeric characters and underscores
    # This matches the normalization function in collection.py
    if not re.match(r'^[a-z0-9_]+$', table_name):
        raise ValueError(
            f"Invalid table name '{table_name}'. "
            f"Table names must contain only lowercase letters, numbers, and underscores."
        )
    
    # SQLite supports double quotes for identifiers
    # This safely quotes the table name even if it's a reserved word
    return f'"{table_name}"'


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """
    Check if a table exists in the SQLite database.
    
    Parameters:
    conn: SQLite connection object
    table_name: Name of the table to check
    
    Returns:
    True if table exists, False otherwise
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (table_name,))
        result = cursor.fetchone()
        return result is not None
    except (sqlite3.DatabaseError, sqlite3.Error) as e:
        print(f"Error checking table existence: {e}")
        return False


def summary_exists(conn: sqlite3.Connection, podcast_name: str) -> bool:
    """
    Check if a summary for a specific podcast already exists in the summary table.
    
    Parameters:
    conn: SQLite connection object
    podcast_name: Name of the podcast to check
    
    Returns:
    True if summary exists, False otherwise
    """
    if not table_exists(conn, 'summary'):
        return False
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM summary 
        WHERE name=?
    """, (podcast_name,))
    result = cursor.fetchone()
    return result is not None


def has_downloaded_episodes(conn: sqlite3.Connection, podcast_name: str) -> bool:
    """
    Check if a podcast has any episodes marked as downloaded in the database.
    
    Parameters:
    conn: SQLite connection object
    podcast_name: Name of the podcast (table name)
    
    Returns:
    True if there are downloaded episodes, False otherwise
    """
    if not table_exists(conn, podcast_name):
        return False
    
    cursor = conn.cursor()
    safe_table_name = validate_and_quote_table_name(podcast_name)
    cursor.execute(f"""
        SELECT COUNT(*) 
        FROM {safe_table_name} 
        WHERE status = ?
    """, (EPISODE_STATUS_DOWNLOADED,))
    count = cursor.fetchone()[0]
    return count > 0


def verify_downloaded_files_exist(conn: sqlite3.Connection, podcast_name: str) -> Tuple[bool, int, int]:
    """
    Verify if downloaded episode files actually exist on disk.
    
    Parameters:
    conn: SQLite connection object
    podcast_name: Name of the podcast (table name)
    
    Returns:
    Tuple of (all_exist, total_downloaded, files_found)
    - all_exist: True if all downloaded episodes have files on disk
    - total_downloaded: Total number of episodes marked as downloaded
    - files_found: Number of files that actually exist on disk
    """
    from pathlib import Path
    
    if not table_exists(conn, podcast_name):
        return (False, 0, 0)
    
    cursor = conn.cursor()
    safe_table_name = validate_and_quote_table_name(podcast_name)
    cursor.execute(f"""
        SELECT Saved_Path 
        FROM {safe_table_name} 
        WHERE status = ? AND Saved_Path IS NOT NULL
    """, (EPISODE_STATUS_DOWNLOADED,))
    
    results = cursor.fetchall()
    total_downloaded = len(results)
    
    if total_downloaded == 0:
        return (True, 0, 0)  # No downloads, so nothing to verify
    
    files_found = 0
    for (saved_path,) in results:
        if saved_path and Path(saved_path).exists():
            files_found += 1
    
    all_exist = (files_found == total_downloaded)
    return (all_exist, total_downloaded, files_found)

