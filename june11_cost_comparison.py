#!/usr/bin/env python3
"""Calculate June 11 costs using different pricing models."""

# Token counts for June 11
tokens = {
    "input_tokens": 1577,
    "output_tokens": 27779,
    "cache_creation_input_tokens": 1993463,
    "cache_read_input_tokens": 62292922,
}

# Pricing models (per 1M tokens)
claude_usage_analyzer_pricing = {
    "input": 15.00,
    "output": 75.00,
    "cache_write": 18.75,
    "cache_read": 1.875
}

litellm_pricing = {
    "input": 15.00,
    "output": 75.00,
    "cache_write": 18.75,
    "cache_read": 1.50  # This is the difference
}

def calculate_cost(tokens, pricing):
    """Calculate total cost based on token counts and pricing."""
    input_cost = (tokens["input_tokens"] / 1_000_000) * pricing["input"]
    output_cost = (tokens["output_tokens"] / 1_000_000) * pricing["output"]
    cache_write_cost = (tokens["cache_creation_input_tokens"] / 1_000_000) * pricing["cache_write"]
    cache_read_cost = (tokens["cache_read_input_tokens"] / 1_000_000) * pricing["cache_read"]
    
    total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "cache_write_cost": cache_write_cost,
        "cache_read_cost": cache_read_cost,
        "total_cost": total_cost
    }

# Calculate costs with both pricing models
print("June 11 Token Breakdown:")
print("========================")
print(f"Input tokens: {tokens['input_tokens']:,}")
print(f"Output tokens: {tokens['output_tokens']:,}")
print(f"Cache creation tokens: {tokens['cache_creation_input_tokens']:,}")
print(f"Cache read tokens: {tokens['cache_read_input_tokens']:,}")
print(f"Total tokens: {sum(tokens.values()):,}")

print("\n\nClaude-Usage-Analyzer Pricing (cache_read=$1.875 per 1M):")
print("========================================================")
analyzer_costs = calculate_cost(tokens, claude_usage_analyzer_pricing)
for key, value in analyzer_costs.items():
    print(f"{key}: ${value:.2f}")

print("\n\nLiteLLM/ccusage Pricing (cache_read=$1.50 per 1M):")
print("===================================================")
litellm_costs = calculate_cost(tokens, litellm_pricing)
for key, value in litellm_costs.items():
    print(f"{key}: ${value:.2f}")

print(f"\n\nDifference: ${analyzer_costs['total_cost'] - litellm_costs['total_cost']:.2f}")

# Show detailed cache read calculation
print("\n\nDetailed Cache Read Calculation:")
print("================================")
cache_read_tokens = tokens["cache_read_input_tokens"]
print(f"Cache read tokens: {cache_read_tokens:,}")
print(f"Claude-usage-analyzer: {cache_read_tokens:,} / 1M × $1.875 = ${analyzer_costs['cache_read_cost']:.2f}")
print(f"LiteLLM/ccusage: {cache_read_tokens:,} / 1M × $1.50 = ${litellm_costs['cache_read_cost']:.2f}")
print(f"Difference in cache read alone: ${analyzer_costs['cache_read_cost'] - litellm_costs['cache_read_cost']:.2f}")