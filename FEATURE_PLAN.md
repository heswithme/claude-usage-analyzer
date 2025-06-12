# Enhanced Analytics Features

## 1. Cache Efficiency Analytics

### Metrics to Add:
- **Cache Hit Rate**: `cache_read_tokens / (cache_read_tokens + input_tokens)` 
- **Cache Efficiency Score**: How much cache saves vs creates
- **Cache ROI**: Dollar savings from cache usage
- **Wasted Cache**: Cache created but rarely read

### Implementation:
```python
def calculate_cache_metrics(stats):
    metrics = {}
    
    # Overall cache metrics
    total_cache_read = stats.get('cache_read_input_tokens', 0)
    total_cache_write = stats.get('cache_creation_input_tokens', 0)
    total_input = stats.get('input_tokens', 0)
    
    # Cache hit rate
    if total_input + total_cache_read > 0:
        metrics['cache_hit_rate'] = total_cache_read / (total_input + total_cache_read)
    else:
        metrics['cache_hit_rate'] = 0
    
    # Cache efficiency (read/write ratio)
    if total_cache_write > 0:
        metrics['cache_efficiency'] = total_cache_read / total_cache_write
    else:
        metrics['cache_efficiency'] = 0
    
    # Calculate savings (cache read is 90% cheaper than input)
    cache_savings = total_cache_read * 0.001875 * 0.9  # Approximate savings
    cache_cost = total_cache_write * 0.01875 * 0.25  # Extra cost for cache creation
    metrics['cache_roi'] = cache_savings - cache_cost
    
    return metrics
```

### Display in CLI:
```
Cache Analytics
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Metric                 ┃ Value         ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Cache Hit Rate         │ 97.3%         │
│ Cache Efficiency       │ 30.3x         │
│ Cache ROI              │ $185.42       │
│ Avg Cache Lifetime     │ 2.5 sessions  │
└────────────────────────┴───────────────┘
```

## 2. Response Time Analysis

### Metrics to Add:
- **Average Response Time**: Time between user message and assistant response
- **P95 Response Time**: 95th percentile response time
- **Response Time by Model**: Compare performance across models
- **Slow Response Detection**: Flag unusually slow responses

### Implementation:
```python
from datetime import datetime
import statistics

def calculate_response_times(messages):
    response_times = []
    
    # Group messages by session
    for i in range(len(messages) - 1):
        if messages[i]['type'] == 'user' and messages[i+1]['type'] == 'assistant':
            if messages[i+1]['parentUuid'] == messages[i]['uuid']:
                time1 = datetime.fromisoformat(messages[i]['timestamp'].replace('Z', '+00:00'))
                time2 = datetime.fromisoformat(messages[i+1]['timestamp'].replace('Z', '+00:00'))
                response_time = (time2 - time1).total_seconds()
                response_times.append({
                    'time': response_time,
                    'model': messages[i+1]['message'].get('model', 'unknown'),
                    'tokens': messages[i+1]['message']['usage']['output_tokens']
                })
    
    return {
        'avg_response_time': statistics.mean([r['time'] for r in response_times]),
        'median_response_time': statistics.median([r['time'] for r in response_times]),
        'p95_response_time': sorted([r['time'] for r in response_times])[int(len(response_times) * 0.95)],
        'by_model': group_by_model(response_times)
    }
```

### Display in CLI:
```
Response Time Analysis
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Metric                 ┃ Time (s)      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Average Response       │ 3.8           │
│ Median Response        │ 3.2           │
│ 95th Percentile        │ 8.4           │
│ Slowest Response       │ 15.2          │
└────────────────────────┴───────────────┘

By Model:
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ Model                  ┃ Avg    ┃ P95     ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━┩
│ claude-opus-4          │ 3.8s   │ 8.4s    │
│ claude-sonnet-4        │ 2.1s   │ 4.2s    │
└────────────────────────┴────────┴─────────┘
```

## 3. Advanced Tool Analytics

### Metrics to Add:
- **Tool Usage Frequency**: Which tools are used most
- **Tool Cost Attribution**: Cost per tool usage
- **Tool Combinations**: Which tools are used together
- **Tool Efficiency**: Tokens consumed per tool

### Implementation:
```python
def analyze_tool_usage(messages):
    tool_stats = defaultdict(lambda: {
        'count': 0,
        'total_tokens': 0,
        'total_cost': 0,
        'avg_tokens': 0,
        'combinations': defaultdict(int)
    })
    
    for msg in messages:
        if msg['type'] == 'assistant' and 'content' in msg['message']:
            tools_in_message = []
            for content in msg['message']['content']:
                if content.get('type') == 'tool_use':
                    tool_name = content['name']
                    tools_in_message.append(tool_name)
                    
                    # Calculate cost for this tool use
                    usage = msg['message']['usage']
                    tokens = usage['output_tokens']
                    cost = calculate_single_message_cost(msg)
                    
                    tool_stats[tool_name]['count'] += 1
                    tool_stats[tool_name]['total_tokens'] += tokens
                    tool_stats[tool_name]['total_cost'] += cost
            
            # Track tool combinations
            if len(tools_in_message) > 1:
                for i, tool1 in enumerate(tools_in_message):
                    for tool2 in tools_in_message[i+1:]:
                        tool_stats[tool1]['combinations'][tool2] += 1
                        tool_stats[tool2]['combinations'][tool1] += 1
    
    # Calculate averages
    for tool in tool_stats:
        if tool_stats[tool]['count'] > 0:
            tool_stats[tool]['avg_tokens'] = tool_stats[tool]['total_tokens'] / tool_stats[tool]['count']
    
    return tool_stats
```

### Display in CLI:
```
Tool Usage Analytics
┏━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ Tool           ┃ Count ┃ Avg Tokens┃ Total $ ┃ $/Use   ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ Bash           │ 342   │ 125       │ $32.10  │ $0.094  │
│ Read           │ 289   │ 85        │ $18.37  │ $0.064  │
│ Edit           │ 156   │ 210       │ $24.53  │ $0.157  │
│ TodoWrite      │ 89    │ 180       │ $11.99  │ $0.135  │
│ Grep           │ 67    │ 95        │ $4.77   │ $0.071  │
└────────────────┴───────┴───────────┴─────────┴─────────┘

Top Tool Combinations:
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Tool Pair              ┃ Count   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Read + Edit            │ 142     │
│ Grep + Read            │ 58      │
│ Bash + Read            │ 47      │
└────────────────────────┴─────────┘
```

## CLI Interface Updates

Add new command options:
```bash
# Show cache analytics
claude-usage-analyzer --cache

# Show response time analysis  
claude-usage-analyzer --response-times

# Show tool analytics
claude-usage-analyzer --tools

# Show everything
claude-usage-analyzer --full
```

## Implementation Priority

1. **Cache Analytics** - Most valuable for cost optimization
2. **Tool Analytics** - Helps understand usage patterns
3. **Response Time** - Good for performance monitoring

All three can be implemented without breaking existing functionality by adding them as optional displays.