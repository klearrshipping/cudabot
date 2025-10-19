import json
from typing import Dict, Any, Optional
from datetime import datetime


class LogFormatter:
    """Utility for formatting structured logs with clear section headers and JSON output."""
    
    @staticmethod
    def print_section_header(section_number: int, section_title: str):
        """Print a clearly formatted section header."""
        separator = "=" * 80
        print(f"\n{separator}")
        print(f"## {section_number}. {section_title.upper()}")
        print(separator)
    
    @staticmethod
    def print_subsection_header(subsection_number: str, subsection_title: str):
        """Print a subsection header."""
        print(f"\n### {subsection_number} {subsection_title}")
        print("-" * 60)
    
    @staticmethod
    def print_json(data: Dict[str, Any], indent: int = 2):
        """Print data in formatted JSON."""
        print(json.dumps(data, indent=indent, ensure_ascii=False))
    
    @staticmethod
    def log_event(event_name: str, data: Dict[str, Any], print_json: bool = True):
        """Log an event with optional JSON output."""
        event_data = {
            "event": event_name,
            "timestamp": datetime.now().isoformat(),
            **data
        }
        if print_json:
            LogFormatter.print_json(event_data)
        return event_data
    
    @staticmethod
    def print_separator(char: str = "-", length: int = 60):
        """Print a separator line."""
        print(char * length)
    
    @staticmethod
    def print_status(message: str, status: str = "info"):
        """Print a status message with emoji indicator."""
        emoji_map = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "processing": "🔄"
        }
        emoji = emoji_map.get(status, "•")
        print(f"{emoji} {message}")

