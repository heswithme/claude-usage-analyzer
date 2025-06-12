"""Core parser for Claude usage logs."""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

from dateutil import parser as date_parser


class UsageParser:
    """Parse Claude usage logs from JSONL files."""

    def __init__(self, claude_dir: str = "~/.claude"):
        self.claude_dir = Path(claude_dir).expanduser()
        
    def parse_all_logs(self) -> Dict[str, Any]:
        """Parse all JSONL files in the Claude directory."""
        stats = self._initialize_stats()
        jsonl_files = self._find_jsonl_files()
        
        for file_path in jsonl_files:
            self._parse_file(file_path, stats)
            
        # Convert defaultdicts to regular dicts and sets to lists for JSON serialization
        return self._finalize_stats(stats)
    
    def _initialize_stats(self) -> Dict[str, Any]:
        """Initialize the statistics structure."""
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "total_messages": 0,
            "by_model": defaultdict(lambda: {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "messages": 0,
                "requests": set()
            }),
            "by_session": defaultdict(lambda: {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "messages": 0,
                "user_messages": 0,
                "start_time": None,
                "end_time": None,
                "cwd": None,
                "models_used": set()
            }),
            "by_date": defaultdict(lambda: {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "messages": 0,
                "sessions": set()
            }),
            "errors": [],
            "tool_usage": defaultdict(int),
            "hourly_distribution": defaultdict(int)
        }
    
    def _find_jsonl_files(self) -> List[Path]:
        """Find all JSONL files in the Claude directory."""
        if not self.claude_dir.exists():
            return []
            
        jsonl_files = []
        for root, _, files in os.walk(self.claude_dir):
            for file in files:
                if file.endswith('.jsonl'):
                    jsonl_files.append(Path(root) / file)
                    
        return jsonl_files
    
    def _parse_file(self, file_path: Path, stats: Dict[str, Any]) -> None:
        """Parse a single JSONL file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            self._process_entry(data, stats)
                        except (json.JSONDecodeError, KeyError) as e:
                            stats["errors"].append({
                                "file": str(file_path),
                                "line": line_num,
                                "error": str(e)
                            })
        except Exception as e:
            stats["errors"].append({
                "file": str(file_path),
                "error": f"Failed to read file: {e}"
            })
    
    def _process_entry(self, data: Dict[str, Any], stats: Dict[str, Any]) -> None:
        """Process a single log entry."""
        entry_type = data.get('type')
        session_id = data.get('sessionId', 'unknown')
        
        # Handle user messages
        if entry_type == 'user' and 'message' in data:
            self._process_user_message(data, stats, session_id)
        
        # Handle assistant messages
        elif entry_type == 'assistant' and 'message' in data:
            self._process_assistant_message(data, stats, session_id)
    
    def _process_user_message(self, data: Dict[str, Any], stats: Dict[str, Any], session_id: str) -> None:
        """Process a user message entry."""
        session_stats = stats['by_session'][session_id]
        session_stats['user_messages'] += 1
        
        # Track CWD
        if 'cwd' in data and not session_stats['cwd']:
            session_stats['cwd'] = data['cwd']
            
        # Update timestamps
        self._update_timestamps(data, session_stats)
    
    def _process_assistant_message(self, data: Dict[str, Any], stats: Dict[str, Any], session_id: str) -> None:
        """Process an assistant message entry."""
        message = data['message']
        usage = message.get('usage', {})
        
        if not usage:
            return
            
        # Extract token counts
        tokens = {
            'input': usage.get('input_tokens', 0),
            'output': usage.get('output_tokens', 0),
            'cache_creation': usage.get('cache_creation_input_tokens', 0),
            'cache_read': usage.get('cache_read_input_tokens', 0)
        }
        
        # Update total stats
        stats['input_tokens'] += tokens['input']
        stats['output_tokens'] += tokens['output']
        stats['cache_creation_input_tokens'] += tokens['cache_creation']
        stats['cache_read_input_tokens'] += tokens['cache_read']
        stats['total_messages'] += 1
        
        # Update model stats
        model = message.get('model', 'unknown')
        self._update_model_stats(stats['by_model'][model], tokens, data.get('requestId'))
        
        # Update session stats
        session_stats = stats['by_session'][session_id]
        self._update_session_stats(session_stats, tokens, model)
        self._update_timestamps(data, session_stats)
        
        # Update date stats
        if 'timestamp' in data:
            self._update_date_stats(data['timestamp'], stats, tokens, session_id)
            
        # Track tool usage
        self._track_tool_usage(message.get('content', []), stats)
    
    def _update_model_stats(self, model_stats: Dict[str, Any], tokens: Dict[str, int], request_id: str = None) -> None:
        """Update statistics for a specific model."""
        model_stats['input_tokens'] += tokens['input']
        model_stats['output_tokens'] += tokens['output']
        model_stats['cache_creation_input_tokens'] += tokens['cache_creation']
        model_stats['cache_read_input_tokens'] += tokens['cache_read']
        model_stats['messages'] += 1
        
        if request_id:
            model_stats['requests'].add(request_id)
    
    def _update_session_stats(self, session_stats: Dict[str, Any], tokens: Dict[str, int], model: str) -> None:
        """Update statistics for a specific session."""
        session_stats['input_tokens'] += tokens['input']
        session_stats['output_tokens'] += tokens['output']
        session_stats['cache_creation_input_tokens'] += tokens['cache_creation']
        session_stats['cache_read_input_tokens'] += tokens['cache_read']
        session_stats['messages'] += 1
        session_stats['models_used'].add(model)
    
    def _update_timestamps(self, data: Dict[str, Any], session_stats: Dict[str, Any]) -> None:
        """Update session timestamps."""
        if 'timestamp' in data:
            timestamp = data['timestamp']
            if not session_stats['start_time']:
                session_stats['start_time'] = timestamp
            session_stats['end_time'] = timestamp
    
    def _update_date_stats(self, timestamp: str, stats: Dict[str, Any], tokens: Dict[str, int], session_id: str) -> None:
        """Update daily statistics."""
        try:
            dt = date_parser.parse(timestamp)
            date_str = dt.strftime('%Y-%m-%d')
            hour = dt.hour
            
            date_stats = stats['by_date'][date_str]
            date_stats['input_tokens'] += tokens['input']
            date_stats['output_tokens'] += tokens['output']
            date_stats['cache_creation_input_tokens'] += tokens['cache_creation']
            date_stats['cache_read_input_tokens'] += tokens['cache_read']
            date_stats['messages'] += 1
            date_stats['sessions'].add(session_id)
            
            stats['hourly_distribution'][hour] += 1
        except Exception:
            pass
    
    def _track_tool_usage(self, content: List[Any], stats: Dict[str, Any]) -> None:
        """Track tool usage from message content."""
        if not isinstance(content, list):
            return
            
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'tool_use':
                tool_name = item.get('name', 'unknown')
                stats['tool_usage'][tool_name] += 1
    
    def _finalize_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Convert defaultdicts and sets to regular types for JSON serialization."""
        stats["by_model"] = dict(stats["by_model"])
        stats["by_session"] = dict(stats["by_session"])
        stats["by_date"] = dict(stats["by_date"])
        stats["tool_usage"] = dict(stats["tool_usage"])
        stats["hourly_distribution"] = dict(stats["hourly_distribution"])
        
        # Convert sets to lists
        for model_data in stats["by_model"].values():
            model_data["requests"] = list(model_data["requests"])
            
        for session_data in stats["by_session"].values():
            session_data["models_used"] = list(session_data["models_used"])
            
        for date_data in stats["by_date"].values():
            date_data["sessions"] = list(date_data["sessions"])
            
        return stats