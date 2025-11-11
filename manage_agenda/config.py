"""
Centralized configuration management for manage-agenda.
"""
import os
from pathlib import Path
from typing import Optional
import logging

# Base directories
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = Path.home() / ".config" / "manage-agenda"
DATA_DIR = Path.home() / ".local" / "share" / "manage-agenda"

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    """Application configuration with environment variable support."""
    
    # Default timezone
    DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "Europe/Berlin")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(DATA_DIR / "manage_agenda.log"))
    
    # Email
    DEFAULT_EMAIL_TAG: str = os.getenv("DEFAULT_EMAIL_TAG", "zAgenda")
    
    # API Keys
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    MISTRAL_API_KEY: Optional[str] = os.getenv("MISTRAL_API_KEY")
    
    # Ollama
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_DEFAULT_MODEL: str = os.getenv("OLLAMA_DEFAULT_MODEL", "llama2")
    
    # Paths
    GOOGLE_CREDENTIALS_DIR: Path = CONFIG_DIR
    
    @classmethod
    def validate(cls) -> bool:
        """Validate critical configuration values."""
        issues = []
        
        # Check timezone validity
        try:
            import pytz
            pytz.timezone(cls.DEFAULT_TIMEZONE)
        except Exception as e:
            issues.append(f"Invalid timezone '{cls.DEFAULT_TIMEZONE}': {e}")
        
        # Log level validation
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if cls.LOG_LEVEL.upper() not in valid_levels:
            issues.append(f"Invalid LOG_LEVEL '{cls.LOG_LEVEL}'. Must be one of {valid_levels}")
        
        if issues:
            for issue in issues:
                logging.warning(f"Configuration issue: {issue}")
            return False
        
        return True
    
    @classmethod
    def get_api_key(cls, service: str) -> Optional[str]:
        """Get API key for a specific service with validation."""
        key_map = {
            "gemini": cls.GEMINI_API_KEY,
            "mistral": cls.MISTRAL_API_KEY,
        }
        
        key = key_map.get(service.lower())
        if not key:
            logging.warning(f"No API key configured for {service}")
        return key


# Singleton instance
config = Config()
