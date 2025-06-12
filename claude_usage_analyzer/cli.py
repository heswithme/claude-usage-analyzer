"""CLI interface for Claude Usage Analyzer."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import click
from dateutil import parser as date_parser
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .parser import UsageParser
from .pricing import CostCalculator

console = Console()


def format_number(num: int) -> str:
    """Format large numbers with commas."""
    return f"{num:,}"


def format_cost(cost: float) -> str:
    """Format cost with dollar sign and appropriate decimal places."""
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def format_duration(start: str, end: str) -> str:
    """Format duration between two timestamps."""
    try:
        start_dt = date_parser.parse(start)
        end_dt = date_parser.parse(end)
        duration = end_dt - start_dt
        
        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
            
        return " ".join(parts)
    except Exception:
        return "N/A"


def find_docker_claude_dirs() -> List[Tuple[str, str, str]]:
    """Find Claude directories in Docker containers."""
    docker_dirs = []
    
    try:
        # Get all running containers
        result = subprocess.run(
            ['docker', 'ps', '-q'],
            capture_output=True,
            text=True,
            check=True
        )
        container_ids = result.stdout.strip().split('\n')
        
        for container_id in container_ids:
            if not container_id:
                continue
                
            # Get container name
            name_result = subprocess.run(
                ['docker', 'inspect', '-f', '{{.Name}}', container_id],
                capture_output=True,
                text=True,
                check=True
            )
            container_name = name_result.stdout.strip().lstrip('/')
            
            # Find .claude directories in the container
            find_result = subprocess.run(
                ['docker', 'exec', container_id, 'sh', '-c', 
                 'find / -maxdepth 4 -name .claude -type d 2>/dev/null || true'],
                capture_output=True,
                text=True
            )
            
            # Check both stdout and stderr
            output = find_result.stdout or find_result.stderr
            if output:
                claude_paths = output.strip().split('\n')
                for claude_path in claude_paths:
                    if claude_path and '/.claude' in claude_path:
                        claude_path = claude_path.strip()
                        # Skip system paths
                        if '/proc/' not in claude_path and '/sys/' not in claude_path:
                            # Determine location type
                            if '/root/' in claude_path:
                                location = "root"
                            elif '/home/' in claude_path:
                                parts = claude_path.split('/')
                                if len(parts) >= 3 and parts[1] == 'home':
                                    location = parts[2]
                                else:
                                    location = "home"
                            else:
                                location = "other"
                            
                            docker_dirs.append((
                                f"{container_name} ({container_id[:12]}) [{location}]",
                                container_id,
                                claude_path
                            ))
                
    except subprocess.CalledProcessError:
        pass
    
    return docker_dirs


@click.command()
@click.option(
    '--claude-dir',
    default='~/.claude',
    help='Path to Claude directory (default: ~/.claude)'
)
@click.option(
    '--docker',
    is_flag=True,
    help='Search for Claude directories in Docker containers'
)
@click.option(
    '--output',
    '-o',
    type=click.Path(),
    help='Export results to JSON file'
)
@click.option(
    '--summary-only',
    is_flag=True,
    help='Show only the summary statistics'
)
@click.option(
    '--tools',
    '-t',
    is_flag=True,
    help='Show tool usage statistics'
)
@click.option(
    '--limit',
    '-l',
    type=int,
    default=10,
    help='Limit number of items shown in tables (default: 10)'
)
def main(
    claude_dir: str,
    docker: bool,
    output: Optional[str],
    summary_only: bool,
    tools: bool,
    limit: int
):
    """Analyze Claude AI usage logs and calculate costs."""
    
    console.print(Panel.fit(
        "[bold cyan]Claude Usage Analyzer[/bold cyan]\n"
        "Analyzing your Claude AI usage and costs",
        border_style="cyan"
    ))
    
    # Collect all stats and costs
    all_stats = []
    all_costs = []
    sources = []
    
    # Always analyze local directory first
    local_stats, local_costs = analyze_claude_dir_raw(claude_dir)
    if local_stats and local_costs:
        all_stats.append(local_stats)
        all_costs.append(local_costs)
        sources.append("local")
    
    # Additionally analyze Docker if requested
    if docker:
        docker_stats, docker_costs = handle_docker_analysis_raw()
        if docker_stats and docker_costs:
            all_stats.append(docker_stats)
            all_costs.append(docker_costs)
            sources.append("docker")
    
    # Merge and display results
    if all_stats:
        merged_stats, merged_costs = merge_stats_and_costs(all_stats, all_costs)
        
        # Export if requested
        if output:
            with open(output, 'w') as f:
                json.dump({
                    'stats': merged_stats, 
                    'costs': merged_costs,
                    'sources': sources
                }, f, indent=2)
            console.print(f"\n[green]✓[/green] Results exported to {output}")
        
        # Display results with source indicators
        display_results(merged_stats, merged_costs, sources, summary_only, tools, limit)
    else:
        console.print("[red]No Claude usage data found[/red]")


def analyze_claude_dir_raw(claude_dir: str) -> Tuple[Optional[dict], Optional[dict]]:
    """Analyze a Claude directory and return raw stats and costs."""
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Parsing local usage logs...", total=None)
            
            parser = UsageParser(claude_dir)
            stats = parser.parse_all_logs()
            
            if not stats.get('total_messages'):
                return None, None
            
            
            progress.update(task, description="Calculating costs...")
            calculator = CostCalculator()
            costs = calculator.calculate_costs(stats)
            
            progress.update(task, completed=True)
            
        return stats, costs
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to analyze local directory: {e}[/yellow]")
        return None, None


def handle_docker_analysis_raw() -> Tuple[Optional[dict], Optional[dict]]:
    """Handle Docker container analysis and return raw stats and costs."""
    console.print("\n[yellow]Searching for Claude directories in Docker containers...[/yellow]")
    docker_containers = find_docker_claude_dirs()
    
    if not docker_containers:
        console.print("[yellow]No Claude directories found in Docker containers[/yellow]")
        return None, None
    
    console.print(f"Found {len(docker_containers)} Claude directories in Docker containers:")
    for i, (container_info, _, claude_path) in enumerate(docker_containers):
        console.print(f"  [{i+1}] {container_info} - {claude_path}")
    
    # Select container
    if len(docker_containers) > 1:
        choice = click.prompt("Select container", type=int, default=1)
        if not 1 <= choice <= len(docker_containers):
            choice = 1
        container_name, container_id, container_claude_path = docker_containers[choice - 1]
    else:
        container_name, container_id, container_claude_path = docker_containers[0]
    
    console.print(f"\nUsing: {container_name}")
    
    # Copy .claude directory from container to temp location
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_claude = Path(temp_dir) / '.claude'
        
        console.print(f"Copying {container_claude_path} from container...")
        copy_result = subprocess.run(
            ['docker', 'cp', f"{container_id}:{container_claude_path}", str(temp_claude)],
            capture_output=True,
            text=True
        )
        
        if copy_result.returncode == 0:
            # Analyze the copied directory
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Parsing Docker usage logs...", total=None)
                
                parser = UsageParser(str(temp_claude))
                stats = parser.parse_all_logs()
                
                if not stats.get('total_messages'):
                    return None, None
                
                
                progress.update(task, description="Calculating costs...")
                calculator = CostCalculator()
                costs = calculator.calculate_costs(stats)
                
                progress.update(task, completed=True)
                
            return stats, costs
        else:
            console.print(f"[red]Failed to copy .claude directory: {copy_result.stderr}[/red]")
            return None, None


def merge_stats_and_costs(all_stats: List[dict], all_costs: List[dict]) -> Tuple[dict, dict]:
    """Merge multiple stats and costs dictionaries."""
    merged_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "total_messages": 0,
        "by_model": {},
        "by_session": {},
        "by_date": {},
        "errors": [],
        "tool_usage": {},
        "hourly_distribution": {}
    }
    
    merged_costs = {
        'by_model': {},
        'by_session': {},
        'by_date': {},
        'total': {
            'input_cost': 0,
            'output_cost': 0,
            'cache_write_cost': 0,
            'cache_read_cost': 0,
            'total_cost': 0
        }
    }
    
    # Merge stats
    for stats in all_stats:
        # Merge totals
        for key in ['input_tokens', 'output_tokens', 'cache_creation_input_tokens', 
                    'cache_read_input_tokens', 'total_messages']:
            merged_stats[key] += stats.get(key, 0)
        
        # Merge by_model
        for model, model_stats in stats.get('by_model', {}).items():
            if model not in merged_stats['by_model']:
                merged_stats['by_model'][model] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "messages": 0,
                    "requests": []
                }
            for key in ['input_tokens', 'output_tokens', 'cache_creation_input_tokens', 
                       'cache_read_input_tokens', 'messages']:
                merged_stats['by_model'][model][key] += model_stats.get(key, 0)
            merged_stats['by_model'][model]['requests'].extend(model_stats.get('requests', []))
        
        # Merge sessions
        for session_id, session_stats in stats.get('by_session', {}).items():
            merged_stats['by_session'][session_id] = session_stats
        
        # Merge by_date
        for date, date_stats in stats.get('by_date', {}).items():
            if date not in merged_stats['by_date']:
                merged_stats['by_date'][date] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "messages": 0,
                    "sessions": []
                }
            for key in ['input_tokens', 'output_tokens', 'cache_creation_input_tokens', 
                       'cache_read_input_tokens', 'messages']:
                merged_stats['by_date'][date][key] += date_stats.get(key, 0)
            merged_stats['by_date'][date]['sessions'].extend(date_stats.get('sessions', []))
        
        # Merge tool usage
        for tool, count in stats.get('tool_usage', {}).items():
            merged_stats['tool_usage'][tool] = merged_stats['tool_usage'].get(tool, 0) + count
        
        # Merge errors
        merged_stats['errors'].extend(stats.get('errors', []))
    
    # Merge costs
    for costs in all_costs:
        # Merge totals
        for key in ['input_cost', 'output_cost', 'cache_write_cost', 'cache_read_cost', 'total_cost']:
            merged_costs['total'][key] += costs.get('total', {}).get(key, 0)
        
        # Merge by_model costs
        for model, model_costs in costs.get('by_model', {}).items():
            if model not in merged_costs['by_model']:
                merged_costs['by_model'][model] = {
                    'input_cost': 0,
                    'output_cost': 0,
                    'cache_write_cost': 0,
                    'cache_read_cost': 0,
                    'total_cost': 0
                }
            for key in ['input_cost', 'output_cost', 'cache_write_cost', 'cache_read_cost', 'total_cost']:
                merged_costs['by_model'][model][key] += model_costs.get(key, 0)
        
        # Merge session costs
        merged_costs['by_session'].update(costs.get('by_session', {}))
        
        # Merge date costs
        for date, date_costs in costs.get('by_date', {}).items():
            if date not in merged_costs['by_date']:
                merged_costs['by_date'][date] = {
                    'input_cost': 0,
                    'output_cost': 0,
                    'cache_write_cost': 0,
                    'cache_read_cost': 0,
                    'total_cost': 0
                }
            for key in ['input_cost', 'output_cost', 'cache_write_cost', 'cache_read_cost', 'total_cost']:
                merged_costs['by_date'][date][key] += date_costs.get(key, 0)
    
    return merged_stats, merged_costs


def display_results(stats: dict, costs: dict, sources: List[str], summary_only: bool, tools: bool, limit: int):
    """Display merged results with source indicators."""
    # Add source indicator to title if includes Docker
    source_text = ""
    if len(sources) > 1:
        source_text = " (local + docker)"
    elif "docker" in sources:
        source_text = " (docker only)"
    
    # Display overall statistics
    display_overall_stats(stats, costs, source_text)
    
    if not summary_only:
        display_model_breakdown(stats, costs, limit)
        display_daily_breakdown(stats, costs, limit)
        display_session_breakdown(stats, costs, limit)
        
        if tools:
            display_tool_usage(stats, limit)
    
    # Display errors if any
    if stats.get('errors'):
        console.print(f"\n[yellow]⚠[/yellow] Found {len(stats['errors'])} errors while parsing logs")




def display_overall_stats(stats: dict, costs: dict, source_text: str = ""):
    """Display overall usage statistics."""
    total_tokens = (
        stats['input_tokens'] + 
        stats['output_tokens'] + 
        stats['cache_creation_input_tokens'] + 
        stats['cache_read_input_tokens']
    )
    
    title = "Overall Usage Statistics" + source_text
    table = Table(title=title, show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    
    table.add_row("Total Messages", format_number(stats['total_messages']))
    table.add_row("Input Tokens", format_number(stats['input_tokens']))
    table.add_row("Output Tokens", format_number(stats['output_tokens']))
    table.add_row("Cache Creation Tokens", format_number(stats['cache_creation_input_tokens']))
    table.add_row("Cache Read Tokens", format_number(stats['cache_read_input_tokens']))
    table.add_row("Total Tokens", f"[bold]{format_number(total_tokens)}[/bold]")
    table.add_row("", "")
    table.add_row("Total Cost", f"[bold green]{format_cost(costs['total']['total_cost'])}[/bold green]")
    
    console.print("\n", table)


def display_model_breakdown(stats: dict, costs: dict, limit: int):
    """Display breakdown by model."""
    console.print("\n[bold]Model Usage Breakdown[/bold]")
    
    table = Table(show_header=True)
    table.add_column("Model", style="cyan")
    table.add_column("Messages", justify="right")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Cache", justify="right")
    table.add_column("Cost", justify="right", style="green")
    
    # Sort models by total cost
    sorted_models = sorted(
        costs['by_model'].items(),
        key=lambda x: x[1]['total_cost'],
        reverse=True
    )
    
    for model, model_costs in sorted_models[:limit]:
        model_stats = stats['by_model'][model]
        cache_tokens = (
            model_stats.get('cache_creation_input_tokens', 0) +
            model_stats.get('cache_read_input_tokens', 0)
        )
        
        # Shorten model name for display
        display_model = model
        if len(model) > 30:
            display_model = model[:27] + "..."
        
        table.add_row(
            display_model,
            format_number(model_stats['messages']),
            format_number(model_stats['input_tokens']),
            format_number(model_stats['output_tokens']),
            format_number(cache_tokens),
            format_cost(model_costs['total_cost'])
        )
    
    console.print(table)


def display_daily_breakdown(stats: dict, costs: dict, limit: int):
    """Display daily usage breakdown."""
    console.print("\n[bold]Daily Usage[/bold]")
    
    table = Table(show_header=True)
    table.add_column("Date", style="cyan")
    table.add_column("Messages", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right", style="green")
    
    # Sort dates
    sorted_dates = sorted(costs['by_date'].items(), reverse=True)
    
    for date, date_costs in sorted_dates[:limit]:
        date_stats = stats['by_date'][date]
        total_tokens = (
            date_stats.get('input_tokens', 0) +
            date_stats.get('output_tokens', 0) +
            date_stats.get('cache_creation_input_tokens', 0) +
            date_stats.get('cache_read_input_tokens', 0)
        )
        
        table.add_row(
            date,
            format_number(date_stats['messages']),
            str(len(date_stats.get('sessions', []))),
            format_number(total_tokens),
            format_cost(date_costs['total_cost'])
        )
    
    console.print(table)


def display_session_breakdown(stats: dict, costs: dict, limit: int):
    """Display breakdown by session."""
    console.print("\n[bold]Session Breakdown[/bold]")
    
    table = Table(show_header=True)
    table.add_column("Session ID", style="cyan")
    table.add_column("Messages", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Models", justify="left")
    table.add_column("Cost", justify="right", style="green")
    
    # Sort sessions by total cost
    sorted_sessions = sorted(
        costs['by_session'].items(),
        key=lambda x: x[1]['total_cost'],
        reverse=True
    )
    
    for session_id, session_costs in sorted_sessions[:limit]:
        session_stats = stats['by_session'][session_id]
        
        # Format models used
        models = session_stats.get('models_used', [])
        if models:
            # Shorten model names
            short_models = []
            for m in models[:2]:
                if '-' in m:
                    parts = m.split('-')
                    if len(parts) > 2:
                        short_models.append(parts[1])
                    else:
                        short_models.append(m)
                else:
                    short_models.append(m)
            models_str = ", ".join(short_models)
            if len(models) > 2:
                models_str += f", +{len(models)-2}"
        else:
            models_str = ""
        
        table.add_row(
            session_id[:8] + "...",
            format_number(session_stats['messages']),
            format_duration(
                session_stats.get('start_time', ''),
                session_stats.get('end_time', '')
            ),
            models_str,
            format_cost(session_costs['total_cost'])
        )
    
    console.print(table)


def display_tool_usage(stats: dict, limit: int):
    """Display tool usage statistics."""
    console.print("\n[bold]Tool Usage[/bold]")
    
    table = Table(show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Usage Count", justify="right")
    table.add_column("Percentage", justify="right")
    
    tool_usage = stats.get('tool_usage', {})
    total_tool_uses = sum(tool_usage.values())
    
    # Sort tools by usage
    sorted_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)
    
    for tool, count in sorted_tools[:limit]:
        percentage = (count / total_tool_uses * 100) if total_tool_uses > 0 else 0
        table.add_row(
            tool,
            format_number(count),
            f"{percentage:.1f}%"
        )
    
    console.print(table)


if __name__ == "__main__":
    main()