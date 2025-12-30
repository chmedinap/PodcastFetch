"""
Configuration constants for PodcastFetch application.
"""

# Database Configuration
DB_PATH = 'podcast_data.db'
DB_TIMEOUT = 30.0
ENABLE_BACKUP = True

# Download Configuration
DOWNLOADS_FOLDER = 'downloads'
DEFAULT_DELAY_SECONDS = 5
DOWNLOAD_TIMEOUT = 30
CHUNK_SIZE = 8192
BATCH_COMMIT_SIZE = 10  # Number of episodes to process before committing transaction

# Retry Configuration
MAX_RETRIES = 3  # Maximum number of retry attempts for transient failures
RETRY_DELAY_BASE = 1  # Base delay in seconds for exponential backoff
RETRY_DELAY_MAX = 60  # Maximum delay in seconds for exponential backoff

# Logging Configuration
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = None  # Set to a file path to enable file logging, None for console only

# RSS Feed Cache Configuration
RSS_CACHE_TTL_HOURS = 1  # Time-to-live for cached RSS feeds in hours
RSS_CACHE_MAX_ENTRIES = 50  # Maximum number of RSS feeds to cache
RSS_CACHE_MAX_SIZE_MB = 100  # Maximum total cache size in megabytes

# File Configuration
MAX_FILENAME_LENGTH = 200
FEEDS_FILE = 'feeds.txt'

# Episode Status Constants
EPISODE_STATUS_NOT_DOWNLOADED = 'not downloaded'
EPISODE_STATUS_DOWNLOADED = 'downloaded'

# Database Table Names
SUMMARY_TABLE_NAME = 'summary'

# Plotting Configuration
PLOTTING_STYLE = 'seaborn-v0_8'
SEABORN_PALETTE = "husl"

