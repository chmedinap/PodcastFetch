# PodcastFetch Architecture & Technical Documentation

This document provides a detailed technical overview of the PodcastFetch application architecture, design decisions, and implementation details.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Design](#architecture-design)
3. [Module Structure](#module-structure)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [Key Algorithms](#key-algorithms)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)
9. [Extension Points](#extension-points)

## System Overview

PodcastFetch is a modular Python application designed to:
- Parse RSS feeds and extract podcast metadata
- Store metadata in a SQLite database
- Download podcast episodes with organized file structure
- Update MP3 ID3 tags with complete metadata
- Provide statistics and management capabilities

### Core Principles

1. **Modularity**: Clear separation of concerns across modules
2. **Extensibility**: Easy to add new features or modify behavior
3. **Robustness**: Comprehensive error handling and retry logic
4. **Performance**: Optimized database operations and batch processing
5. **User Experience**: Clear feedback and progress reporting

## Architecture Design

### High-Level Architecture

```
┌─────────────────┐
│   User/CLI      │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────────┐
│         Application Layer           │
│  (CLI / notebook.ipynb for devs)  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│         Business Logic Layer       │
│  ┌──────────┐  ┌──────────┐       │
│  │   Data   │  │ Download │       │
│  │ Collection│  │ Operations│     │
│  └──────────┘  └──────────┘       │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│         Data Access Layer           │
│  ┌──────────┐  ┌──────────┐       │
│  │ Database │  │  File    │       │
│  │  Access  │  │  System  │       │
│  └──────────┘  └──────────┘       │
└─────────────────────────────────────┘
```

### Module Dependencies

```
podcast_fetch/
├── config.py (no dependencies)
├── cli.py → argparse, sqlite3, all other modules
├── data/
│   ├── collection.py → config, feedparser, requests
│   └── summary.py → pandas
├── database/
│   ├── connection.py → sqlite3, config
│   ├── queries.py → sqlite3
│   └── schema.py → sqlite3
└── download/
    ├── downloader.py → requests, sqlite3, config
    ├── id3_tags.py → mutagen, sqlite3
    ├── metadata.py → sqlite3
    └── utils.py → pathlib, sqlite3
```

**Note**: The `notebook.ipynb` file is provided for developers who want to use PodcastFetch programmatically or for advanced use cases. End users should use the command-line interface (`cli.py`).

## Module Structure

### 1. Configuration (`config.py`)

Centralized configuration management. All constants are defined here to enable easy customization.

**Key Settings:**
- Database paths and timeouts
- Download settings (folder, delays, timeouts)
- Retry configuration (exponential backoff)
- Logging configuration
- File size limits

**Design Decision**: Centralized config allows for easy environment-specific configurations and future environment variable support.

### 2. Data Collection (`data/collection.py`)

Handles RSS feed parsing and data extraction.

#### Key Functions

**`normalize_feed_url(feed_url: str) -> str`**
- Detects Apple Podcast URLs vs RSS feeds
- Converts Apple Podcast links using iTunes Search API
- Returns normalized RSS feed URL

**`get_rss_from_apple_podcast(apple_url: str) -> str`**
- Uses iTunes Search API to resolve Apple Podcast links
- Extracts RSS feed URL from API response
- Handles API errors gracefully

**`collect_data(feed) -> pd.DataFrame`**
- Parses RSS feed using `feedparser`
- Extracts episode metadata:
  - Title, link, published date
  - Summary/description
  - Episode number, season number
  - Episode image URL
  - Podcast image URL
- Normalizes podcast name for database table
- Stores original podcast name in `author_raw`
- Returns cleaned DataFrame with all metadata

**`get_episode_xml_from_rss(rss_url, episode_id, ...) -> str`**
- Downloads RSS feed as XML
- Extracts specific episode entry XML
- Preserves original metadata format
- Used for archival purposes

#### Data Processing Flow

```
RSS Feed URL
    ↓
[feedparser.parse()]
    ↓
Parsed Feed Object
    ↓
[Extract Metadata]
    ↓
[Create DataFrame]
    ↓
[Normalize & Clean]
    ↓
DataFrame with Episode Data
```

### 3. Database Layer (`database/`)

#### Connection Management (`connection.py`)

**`get_db_connection(db_path: str) -> sqlite3.Connection`**
- Context manager for database connections
- Automatic connection cleanup
- Timeout configuration

**`is_valid_database(db_path: str) -> bool`**
- Validates database integrity
- Checks for corruption
- Returns True if database is usable

**`clean_dataframe_for_sqlite(df: pd.DataFrame) -> pd.DataFrame`**
- Removes unsupported data types
- Converts complex types to strings
- Handles NaN values
- Prepares DataFrame for SQLite storage

#### Query Utilities (`queries.py`)

Helper functions for common database operations:
- `table_exists()`: Check if table exists
- `summary_exists()`: Check if summary row exists
- `has_downloaded_episodes()`: Check download status
- `verify_downloaded_files_exist()`: Validate file existence

#### Schema Management (`schema.py`)

Handles database schema evolution and migrations.

**Key Functions:**
- `add_download_columns_to_table()`: Adds download metadata columns
- `add_author_raw_column_to_table()`: Adds original podcast name column
- `add_episode_metadata_columns_to_table()`: Adds episode/season number columns
- `add_podcast_image_url_to_summary()`: Adds image URL columns to summary
- `add_indexes_to_table()`: Creates performance indexes

**Design Decision**: Schema migrations are handled gracefully - columns are added only if they don't exist, ensuring backward compatibility.

### 4. Download Operations (`download/`)

#### Main Downloader (`downloader.py`)

**`download_all_episodes(conn, podcast_name, ...) -> Tuple[int, int]`**
- Retrieves episodes from database
- Downloads with retry logic
- Updates database status
- Downloads images
- Updates ID3 tags
- Returns (successful, failed) counts

**Download Process:**
```
1. Query database for undownloaded episodes
2. For each episode:
   a. Create folder structure
   b. Download MP3 file (with retry)
   c. Download episode image (if available)
   d. Update ID3 tags
   e. Download podcast image (once)
   f. Save episode metadata XML
   g. Update database status
3. Batch commit database updates
4. Update summary statistics
```

**`download_last_episode(conn, podcast_name, ...) -> bool`**
- Downloads only the most recent episode
- Simplified version of `download_all_episodes`
- Returns success/failure

**`_download_with_retry(url, file_path, ...) -> None`**
- Implements exponential backoff retry logic
- Handles transient network failures
- Logs retry attempts
- Raises exception after max retries

**`_download_image(image_url, image_path) -> bool`**
- Downloads image from URL
- Detects file extension from Content-Type or URL
- Saves with correct extension
- Returns success/failure

#### ID3 Tag Management (`id3_tags.py`)

**`update_mp3_id3_tags(file_path, title, artist, ...) -> bool`**
- Updates MP3 file ID3 tags using `mutagen`
- Maps database fields to ID3 tag fields:
  - `title` → TIT2 (Title)
  - `artist` → TPE1 (Artist)
  - `album` → TALB (Album)
  - `year` → TDRC (Date)
  - `track` → TRCK (Track Number)
  - `disc_number` → TPOS (Disc Number)
  - `comment` → COMM (Comment)
  - `cover_image_path` → APIC (Cover Art)
  - `genre` → TCON (Genre)
- Handles encoding (UTF-8)
- Returns success/failure

**`update_episode_id3_tags_from_db(conn, podcast_name, episode_id, file_path, episode_folder) -> bool`**
- Retrieves episode metadata from database
- Extracts year from published date
- Finds cover image (episode image preferred, podcast image fallback)
- Calls `update_mp3_id3_tags()` with all data
- Comprehensive error handling

**Image Search Logic:**
```
1. Search episode folder for "episode_image.*"
   - Uses glob pattern matching
   - Finds any extension (.jpg, .png, .webp, etc.)
2. If not found, search podcast base folder for "podcast_image.*"
3. Use found image or None
```

#### Metadata Updates (`metadata.py`)

**`update_summary(conn, podcast_name, ...) -> None`**
- Calculates podcast statistics using SQL aggregation
- Updates summary table with:
  - Total episodes
  - Downloaded episodes
  - Not downloaded episodes
  - Percentage downloaded
  - Last downloaded date
  - Podcast image URL
  - RSS feed URL
- Uses UPSERT pattern (UPDATE or INSERT)
- Optimized to avoid full table reads

#### Utilities (`utils.py`)

**`sanitize_filename(filename: str) -> str`**
- Removes invalid characters for file systems
- Handles length limits
- Preserves readability

**`parse_episode_date(conn, podcast_name, episode_id, published_date) -> datetime`**
- Parses various date formats
- Caches parsed dates in database
- Handles timezone information

**`show_podcast_summary(conn, podcast_names) -> dict`**
- Displays download statistics
- Formats output for readability

## Data Flow

### Feed Processing Flow

```
1. User provides feed URL (RSS or Apple Podcast)
   ↓
2. normalize_feed_url() detects type and converts if needed
   ↓
3. collect_data() parses RSS feed
   ↓
4. Extract metadata:
   - Episode titles, links, dates
   - Summaries
   - Episode/season numbers
   - Image URLs
   ↓
5. Create DataFrame with normalized data
   ↓
6. Store in SQLite database (table = normalized podcast name)
   ↓
7. Update summary table with statistics
```

### Download Flow

```
1. Query database for undownloaded episodes
   ↓
2. For each episode:
   a. Create folder: downloads/podcast/year/date - title/
   b. Download MP3 → episode_folder/episode.mp3
   c. Download episode image → episode_folder/episode_image.jpg
   d. Update ID3 tags (reads from database, writes to MP3)
   e. Download podcast image → podcast_folder/podcast_image.jpg (once)
   f. Save metadata XML → episode_folder/episode_metadata.xml
   g. Update database: status = 'downloaded'
   ↓
3. Batch commit database updates (every 10 episodes)
   ↓
4. Update summary statistics
```

### ID3 Tag Update Flow

```
1. Retrieve episode data from database:
   - title, author_raw, episode_number, season_number
   - summary, published, episode_image_url
   ↓
2. Extract year from published date
   ↓
3. Find cover image:
   a. Search episode_folder for "episode_image.*"
   b. If not found, search podcast_folder for "podcast_image.*"
   ↓
4. Convert episode_number/season_number to integers
   ↓
5. Update MP3 file:
   - Open file with mutagen
   - Set all ID3 tag fields
   - Add cover art (if found)
   - Save file
```

## Database Schema

### Episode Tables (One per Podcast)

Each podcast gets its own table named after the normalized podcast name.

**Columns:**
- `title` (TEXT): Episode title
- `link` (TEXT): Episode URL
- `link_direct` (TEXT): Direct audio download URL
- `published` (TEXT): Publication date string
- `published_parsed` (TEXT): ISO format date
- `summary` (TEXT): Episode description
- `id` (TEXT): Episode unique identifier (usually GUID)
- `status` (TEXT): 'downloaded' or 'not downloaded'
- `author` (TEXT): Normalized podcast name
- `author_raw` (TEXT): Original podcast name (before normalization)
- `episode_number` (INTEGER): Episode number (nullable)
- `season_number` (INTEGER): Season number (nullable)
- `episode_image_url` (TEXT): Episode image URL (nullable)
- `Saved_Path` (TEXT): File path where episode is saved
- `Size` (INTEGER): File size in bytes
- `File_name` (TEXT): Filename

**Indexes:**
- `idx_status`: On `status` column (for fast queries)
- `idx_published`: On `published` column (for sorting)

### Summary Table

Single table with one row per podcast.

**Columns:**
- `name` (TEXT, PRIMARY KEY): Normalized podcast name
- `num_episodes` (INTEGER): Total episodes
- `num_episodes_downloaded` (INTEGER): Downloaded count
- `num_episodes_not_downloaded` (INTEGER): Not downloaded count
- `pct_episodes_downloaded` (REAL): Percentage downloaded
- `dataframe_name` (TEXT): DataFrame variable name
- `last_episode_downloaded_date` (TEXT): Last download date
- `podcast_image_url` (TEXT): Podcast cover art URL
- `rss_feed_url` (TEXT): RSS feed URL

## Key Algorithms

### 1. Exponential Backoff Retry

```python
retry_delay = RETRY_DELAY_BASE
for attempt in range(MAX_RETRIES):
    try:
        # Attempt operation
        return success
    except TransientError:
        if attempt < MAX_RETRIES - 1:
            sleep(retry_delay)
            retry_delay = min(retry_delay * 2, RETRY_DELAY_MAX)
```

**Rationale**: Handles transient network failures gracefully without overwhelming servers.

### 2. Batch Database Commits

```python
pending_updates = []
for episode in episodes:
    # Process episode
    pending_updates.append(update)
    if len(pending_updates) >= BATCH_SIZE:
        conn.commit()
        pending_updates = []
conn.commit()  # Final commit
```

**Rationale**: Reduces disk I/O by batching commits. Significantly faster for large downloads.

### 3. SQL Aggregation for Statistics

Instead of:
```python
df = pd.read_sql_query("SELECT * FROM table", conn)
stats = df.groupby('status').count()
```

We use:
```python
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'downloaded' THEN 1 ELSE 0 END) as downloaded
    FROM table
""")
```

**Rationale**: Calculates statistics in database, avoiding full table reads. 80-95% faster.

### 4. Image Search with Glob Patterns

```python
episode_image_files = list(episode_folder.glob("episode_image.*"))
```

**Rationale**: Finds images regardless of extension (.jpg, .png, .webp, etc.), making the system robust to different image formats.

## Error Handling

### Exception Hierarchy

1. **Network Errors** (`requests.RequestException`):
   - `requests.Timeout`: Network timeout
   - `requests.ConnectionError`: Connection failure
   - `requests.HTTPError`: HTTP error responses
   - **Handling**: Retry with exponential backoff

2. **Database Errors** (`sqlite3.Error`):
   - `sqlite3.OperationalError`: Table/column issues
   - `sqlite3.ProgrammingError`: SQL syntax errors
   - **Handling**: Log error, attempt reconnection, graceful degradation

3. **File System Errors** (`OSError`):
   - Permission errors
   - Disk full errors
   - **Handling**: Log error, skip file, continue processing

4. **Data Errors** (`ValueError`, `TypeError`, `IndexError`):
   - Invalid data formats
   - Missing required fields
   - **Handling**: Log warning, use defaults, continue processing

### Logging Strategy

- **DEBUG**: Detailed information for troubleshooting
- **INFO**: Important operations (downloads, updates)
- **WARNING**: Non-critical issues (missing images, failed retries)
- **ERROR**: Critical failures (database errors, download failures)

Logs include:
- Timestamps
- Function names
- Error messages
- Stack traces (for errors)

## Performance Considerations

### Database Optimizations

1. **Indexes**: Created on frequently queried columns (`status`, `published`)
2. **Batch Commits**: Reduces disk I/O by 90% for large downloads
3. **SQL Aggregation**: Statistics calculated in database, not in Python
4. **Connection Pooling**: (Future) Reuse database connections

### Download Optimizations

1. **Streaming Downloads**: Large files downloaded in chunks
2. **Retry Logic**: Handles transient failures without manual intervention
3. **Delay Between Downloads**: Prevents server overload
4. **Batch Processing**: Multiple operations grouped together

### Memory Optimizations

1. **DataFrame Chunking**: (Future) Process large feeds in chunks
2. **Lazy Loading**: Only load data when needed
3. **Garbage Collection**: Explicit cleanup of large objects

## Extension Points

### Adding New Metadata Fields

1. Add column to database schema in `schema.py`
2. Extract field in `collection.py` → `collect_data()`
3. Update ID3 tags in `id3_tags.py` → `update_mp3_id3_tags()`
4. Run migration to add column to existing tables

### Adding New Feed Sources

1. Create new function in `collection.py` similar to `get_rss_from_apple_podcast()`
2. Add detection logic in `normalize_feed_url()`
3. Integrate with `collect_data()`

### Custom Download Logic

1. Extend `downloader.py` with new functions
2. Follow existing patterns (retry logic, error handling)
3. Update database status appropriately

### Custom ID3 Tag Fields

1. Add field to `update_mp3_id3_tags()` function
2. Map to appropriate ID3 tag frame (see mutagen documentation)
3. Extract data in `update_episode_id3_tags_from_db()`

## Future Enhancements

### Planned Features

1. **Connection Pooling**: Reuse database connections
2. **Resume Downloads**: Resume partial downloads
3. **Checksum Validation**: Verify downloaded file integrity
4. **Progress Reporting**: Real-time download progress
5. **Web Interface**: Browser-based UI
6. **Scheduled Downloads**: Automatic periodic updates
7. **Episode Filtering**: Download by date range, keywords, etc.

### Performance Improvements

1. **Parallel Downloads**: Download multiple episodes simultaneously
2. **Caching**: Cache RSS feed responses
3. **Incremental Updates**: Only fetch new episodes
4. **Database Optimization**: Query plan analysis and optimization

## Testing Strategy

### Unit Tests

- Test individual functions in isolation
- Mock external dependencies (network, file system)
- Verify error handling paths

### Integration Tests

- Test full workflows (feed → database → download)
- Verify database schema migrations
- Test ID3 tag updates

### End-to-End Tests

- Test complete user workflows
- Verify file organization
- Check metadata accuracy

## Security Considerations

1. **Input Validation**: All user inputs validated and sanitized
2. **File Path Safety**: Prevents directory traversal attacks
3. **SQL Injection Prevention**: Parameterized queries only
4. **Network Security**: HTTPS for all downloads
5. **File Permissions**: Appropriate file system permissions

## Conclusion

PodcastFetch is designed with modularity, extensibility, and robustness in mind. The architecture supports easy maintenance and future enhancements while providing a solid foundation for podcast management.

## User Interfaces

### Command-Line Interface (Primary)

The primary interface for end users is the command-line interface (`cli.py`). This provides:
- Simple, intuitive commands
- No programming knowledge required
- Full access to all features
- Clear error messages and help text

### Jupyter Notebook (Developer)

The `notebook.ipynb` file is provided for developers who want to:
- Use PodcastFetch programmatically
- Customize workflows
- Perform advanced data analysis
- Integrate with other tools

**Note**: End users should use the CLI. The notebook is for development and advanced use cases only.

For user-facing documentation, see [README.md](README.md).

