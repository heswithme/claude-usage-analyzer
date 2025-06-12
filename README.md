# Claude Usage Analyzer

Analyze your Claude AI usage logs and calculate costs from `~/.claude` or Docker containers.

## Quick Start

### Option 1: Run directly with uvx (recommended)
```bash
uvx claude-usage-analyzer
```

### Option 2: Clone and run
```bash
git clone https://github.com/heswithme/claude-usage-analyzer.git
cd claude-usage-analyzer
uv run .
```

## Usage

```bash
# Analyze local ~/.claude directory (default)
uvx claude-usage-analyzer

# Analyze Docker containers
uvx claude-usage-analyzer --docker

# Export results to JSON
uvx claude-usage-analyzer --output results.json

# Show only summary
uvx claude-usage-analyzer --summary-only

# Show tool usage statistics
uvx claude-usage-analyzer --tools

# Limit items shown in tables
uvx claude-usage-analyzer --limit 5
```

## Features

- **Zero Installation**: Just clone and run with `uv`
- **Comprehensive Stats**: Token usage, costs, sessions, daily trends
- **Docker Support**: Analyze usage from devcontainers
- **Rich Terminal UI**: Beautiful tables and formatting
- **Cost Tracking**: Automatic calculation based on current Claude API pricing

## Example Output

```
╭──────────────────────────────────────────╮
│     Claude Usage Analyzer                │
│ Analyzing your Claude AI usage and costs │
╰──────────────────────────────────────────╯

      Overall Usage Statistics      
 Total Messages               1,213 
 Input Tokens                 2,661 
 Output Tokens               68,265 
 Cache Creation Tokens    3,257,802 
 Cache Read Tokens       98,725,473 
 Total Tokens           102,054,201 
                                    
 Total Cost                 $251.35 

Model Usage Breakdown
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Model                  ┃ Messages  ┃ Input  ┃ Output ┃      Cache ┃    Cost ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━┩
│ claude-opus-4-20250514 │     1,204 │  2,661 │ 68,265 │ 101,983,275 │ $251.35 │
└────────────────────────┴───────────┴────────┴────────┴─────────────┴─────────┘

Daily Usage
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Date       ┃ Messages ┃ Sessions ┃      Tokens ┃    Cost ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━┩
│ 2025-06-12 │       82 │        1 │   3,602,253 │  $11.10 │
│ 2025-06-11 │    1,209 │        2 │ 101,998,767 │ $251.10 │
└────────────┴──────────┴──────────┴─────────────┴─────────┘

Session Breakdown
┏━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Session ID  ┃ Messages ┃ Duration ┃ Models            ┃    Cost ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ 3885ab53... │      768 │    3h 1m │ opus, <synthetic> │ $159.41 │
│ 7701daad... │      441 │   2h 34m │ opus, <synthetic> │  $91.69 │
│ ca45556d... │       82 │      34m │ opus              │  $11.10 │
└─────────────┴──────────┴──────────┴───────────────────┴─────────┘
```

## Requirements

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker (optional, for container support)

## License

MIT