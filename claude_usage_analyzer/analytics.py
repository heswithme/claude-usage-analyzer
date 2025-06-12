"""Advanced analytics for Claude usage data."""

from typing import Dict, Any, List, Tuple
from collections import defaultdict
from datetime import datetime
import statistics


def calculate_cache_metrics(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate cache efficiency metrics."""
    metrics = {}
    
    # Overall cache metrics
    total_cache_read = stats.get('cache_read_input_tokens', 0)
    total_cache_write = stats.get('cache_creation_input_tokens', 0)
    total_input = stats.get('input_tokens', 0)
    
    # Cache hit rate
    total_non_cache_input = total_input + total_cache_read
    if total_non_cache_input > 0:
        metrics['cache_hit_rate'] = total_cache_read / total_non_cache_input
    else:
        metrics['cache_hit_rate'] = 0
    
    # Cache efficiency (read/write ratio)
    if total_cache_write > 0:
        metrics['cache_efficiency'] = total_cache_read / total_cache_write
    else:
        metrics['cache_efficiency'] = 0
    
    # Calculate savings
    # Cache read is ~90% cheaper than regular input
    # Assume average input cost of $3/1M tokens
    cache_read_cost = (total_cache_read / 1_000_000) * 0.30
    equivalent_input_cost = (total_cache_read / 1_000_000) * 3.00
    cache_savings = equivalent_input_cost - cache_read_cost
    
    # Cache creation extra cost (25% more than regular input)
    cache_creation_extra = (total_cache_write / 1_000_000) * (3.75 - 3.00)
    
    metrics['cache_roi'] = cache_savings - cache_creation_extra
    metrics['cache_total_savings'] = cache_savings
    metrics['cache_creation_cost'] = cache_creation_extra
    
    # Per-session cache metrics
    session_cache_metrics = {}
    for session_id, session_stats in stats.get('by_session', {}).items():
        session_cache_read = session_stats.get('cache_read_input_tokens', 0)
        session_cache_write = session_stats.get('cache_creation_input_tokens', 0)
        
        if session_cache_write > 0:
            session_efficiency = session_cache_read / session_cache_write
        else:
            session_efficiency = 0
            
        session_cache_metrics[session_id] = {
            'efficiency': session_efficiency,
            'cache_read': session_cache_read,
            'cache_write': session_cache_write
        }
    
    metrics['by_session'] = session_cache_metrics
    
    return metrics


def calculate_response_times(all_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate response time analytics."""
    response_times = []
    
    # Sort messages by timestamp
    sorted_messages = sorted(all_messages, key=lambda x: x.get('timestamp', ''))
    
    # Find user-assistant pairs
    for i in range(len(sorted_messages) - 1):
        msg = sorted_messages[i]
        next_msg = sorted_messages[i + 1]
        
        if (msg.get('type') == 'user' and 
            next_msg.get('type') == 'assistant' and
            next_msg.get('parentUuid') == msg.get('uuid')):
            
            try:
                # Parse timestamps
                time1 = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                time2 = datetime.fromisoformat(next_msg['timestamp'].replace('Z', '+00:00'))
                response_time = (time2 - time1).total_seconds()
                
                # Only include reasonable response times (< 5 minutes)
                if 0 < response_time < 300:
                    model = next_msg.get('message', {}).get('model', 'unknown')
                    tokens = next_msg.get('message', {}).get('usage', {}).get('output_tokens', 0)
                    
                    response_times.append({
                        'time': response_time,
                        'model': model,
                        'tokens': tokens,
                        'session_id': msg.get('sessionId'),
                        'timestamp': msg.get('timestamp')
                    })
            except Exception:
                continue
    
    if not response_times:
        return {
            'avg_response_time': 0,
            'median_response_time': 0,
            'p95_response_time': 0,
            'p99_response_time': 0,
            'min_response_time': 0,
            'max_response_time': 0,
            'by_model': {},
            'total_responses': 0
        }
    
    # Calculate overall metrics
    times = [r['time'] for r in response_times]
    times.sort()
    
    metrics = {
        'avg_response_time': statistics.mean(times),
        'median_response_time': statistics.median(times),
        'p95_response_time': times[int(len(times) * 0.95)] if len(times) > 20 else max(times),
        'p99_response_time': times[int(len(times) * 0.99)] if len(times) > 100 else max(times),
        'min_response_time': min(times),
        'max_response_time': max(times),
        'total_responses': len(response_times)
    }
    
    # Group by model
    by_model = defaultdict(list)
    for rt in response_times:
        by_model[rt['model']].append(rt['time'])
    
    metrics['by_model'] = {}
    for model, model_times in by_model.items():
        model_times.sort()
        metrics['by_model'][model] = {
            'avg': statistics.mean(model_times),
            'median': statistics.median(model_times),
            'p95': model_times[int(len(model_times) * 0.95)] if len(model_times) > 5 else max(model_times),
            'count': len(model_times)
        }
    
    return metrics


def analyze_tool_usage(all_messages: List[Dict[str, Any]], costs_by_message: Dict[str, float] = None) -> Dict[str, Any]:
    """Analyze tool usage patterns."""
    tool_stats = defaultdict(lambda: {
        'count': 0,
        'total_tokens': 0,
        'total_cost': 0,
        'messages': [],
        'combinations': defaultdict(int)
    })
    
    tool_sequences = []
    
    for msg in all_messages:
        if msg.get('type') == 'assistant' and 'message' in msg:
            message_content = msg['message'].get('content', [])
            tools_in_message = []
            
            for content in message_content:
                if isinstance(content, dict) and content.get('type') == 'tool_use':
                    tool_name = content.get('name', 'unknown')
                    tools_in_message.append(tool_name)
                    
                    # Get usage data
                    usage = msg['message'].get('usage', {})
                    tokens = usage.get('output_tokens', 0)
                    
                    # Estimate cost for this message
                    if costs_by_message and msg['uuid'] in costs_by_message:
                        cost = costs_by_message[msg['uuid']]
                    else:
                        # Simple estimation
                        cost = (tokens / 1_000_000) * 15.0  # Assuming average cost
                    
                    tool_stats[tool_name]['count'] += 1
                    tool_stats[tool_name]['total_tokens'] += tokens
                    tool_stats[tool_name]['total_cost'] += cost
                    tool_stats[tool_name]['messages'].append(msg['uuid'])
            
            # Track tool combinations
            if len(tools_in_message) > 1:
                tool_sequences.append(tools_in_message)
                for i, tool1 in enumerate(tools_in_message):
                    for tool2 in tools_in_message[i+1:]:
                        tool_stats[tool1]['combinations'][tool2] += 1
                        tool_stats[tool2]['combinations'][tool1] += 1
    
    # Calculate averages and clean up
    result = {}
    for tool, stats in tool_stats.items():
        if stats['count'] > 0:
            avg_tokens = stats['total_tokens'] / stats['count']
            avg_cost = stats['total_cost'] / stats['count']
        else:
            avg_tokens = 0
            avg_cost = 0
            
        # Find top combinations
        top_combinations = sorted(
            stats['combinations'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        result[tool] = {
            'count': stats['count'],
            'total_tokens': stats['total_tokens'],
            'total_cost': stats['total_cost'],
            'avg_tokens': avg_tokens,
            'avg_cost': avg_cost,
            'top_combinations': top_combinations
        }
    
    # Sort by usage count
    sorted_tools = sorted(result.items(), key=lambda x: x[1]['count'], reverse=True)
    
    return {
        'tools': dict(sorted_tools),
        'total_tool_uses': sum(s['count'] for s in result.values()),
        'unique_tools': len(result),
        'tool_sequences': tool_sequences[:10]  # Top 10 sequences
    }