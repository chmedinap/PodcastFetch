"""
Database utility modules for connection management, queries, and schema operations.
"""

from podcast_fetch.database.connection import (
    is_valid_database,
    get_db_connection,
    clean_dataframe_for_sqlite
)
from podcast_fetch.database.queries import (
    table_exists,
    summary_exists,
    has_downloaded_episodes,
    verify_downloaded_files_exist
)
from podcast_fetch.database.schema import (
    add_download_columns_to_table,
    update_download_info,
    update_all_tables_with_download_columns,
    add_indexes_to_table,
    update_all_tables_with_indexes,
    explain_query_plan
)

__all__ = [
    'is_valid_database',
    'get_db_connection',
    'clean_dataframe_for_sqlite',
    'table_exists',
    'summary_exists',
    'has_downloaded_episodes',
    'verify_downloaded_files_exist',
    'add_download_columns_to_table',
    'update_download_info',
    'update_all_tables_with_download_columns',
    'add_indexes_to_table',
    'update_all_tables_with_indexes',
    'explain_query_plan',
]


