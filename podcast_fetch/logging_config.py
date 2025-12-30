"""
Centralized logging configuration for PodcastFetch.

This module provides a single point of configuration for all logging
across the application, eliminating code duplication and ensuring
consistent logging behavior.
"""

import logging
import sys
from pathlib import Path
from podcast_fetch import config


def setup_logging(logger_name: str = None) -> logging.Logger:
    """
    Set up logging for a module with centralized configuration.
    
    This function ensures that logging is configured consistently across
    all modules. It checks if the logger already has handlers to avoid
    duplicate handlers.
    
    Parameters:
    logger_name: Name of the logger (typically __name__). If None, uses root logger.
    
    Returns:
    logging.Logger: Configured logger instance
    
    Example:
        >>> from podcast_fetch.logging_config import setup_logging
        >>> logger = setup_logging(__name__)
        >>> logger.info("This will be logged")
    """
    logger = logging.getLogger(logger_name)
    
    # Only configure if logger doesn't have handlers (avoid duplicates)
    if logger.handlers:
        return logger
    
    # Set log level
    log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add console handler (always present)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    # Add file handler if configured
    if config.LOG_FILE:
        try:
            # Ensure log file directory exists
            log_path = Path(config.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(config.LOG_FILE)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            # If file logging fails, log to console only
            # Use print since logger might not be fully configured yet
            print(f"Warning: Could not set up file logging to {config.LOG_FILE}: {e}")
    
    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with centralized configuration.
    
    This is a convenience function that calls setup_logging().
    Use this when you just need a logger without worrying about setup.
    
    Parameters:
    name: Name of the logger (typically __name__)
    
    Returns:
    logging.Logger: Configured logger instance
    
    Example:
        >>> from podcast_fetch.logging_config import get_logger
        >>> logger = get_logger(__name__)
    """
    return setup_logging(name)

