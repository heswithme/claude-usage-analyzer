"""Pricing calculations for Claude models."""

from typing import Dict, Any, List, Optional


# Pricing per 1M tokens (in USD)
PRICING = {
    'claude-3-opus-20240229': {
        'input': 15.00,
        'output': 75.00,
        'cache_write': 18.75,
        'cache_read': 1.875
    },
    'claude-opus-4-20250514': {
        'input': 15.00,
        'output': 75.00,
        'cache_write': 18.75,
        'cache_read': 1.875
    },
    'claude-3-5-sonnet-20241022': {
        'input': 3.00,
        'output': 15.00,
        'cache_write': 3.75,
        'cache_read': 0.30
    },
    'claude-3-5-haiku-20241022': {
        'input': 1.00,
        'output': 5.00,
        'cache_write': 1.25,
        'cache_read': 0.10
    },
    'claude-3-haiku-20240307': {
        'input': 0.25,
        'output': 1.25,
        'cache_write': 0.30,
        'cache_read': 0.03
    },
    # Default pricing for unknown models
    'default': {
        'input': 3.00,
        'output': 15.00,
        'cache_write': 3.75,
        'cache_read': 0.30
    }
}


class CostCalculator:
    """Calculate costs based on token usage."""
    
    def __init__(self, custom_pricing: Dict[str, Dict[str, float]] = None):
        self.pricing = PRICING.copy()
        if custom_pricing:
            self.pricing.update(custom_pricing)
    
    def calculate_costs(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate costs for all models and sessions."""
        costs = {
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
        
        # Calculate costs by model
        for model, usage in stats.get('by_model', {}).items():
            model_costs = self._calculate_model_costs(model, usage)
            costs['by_model'][model] = model_costs
            
            # Update totals
            for key in ['input_cost', 'output_cost', 'cache_write_cost', 'cache_read_cost', 'total_cost']:
                costs['total'][key] += model_costs[key]
        
        # Calculate costs by session
        for session_id, session_data in stats.get('by_session', {}).items():
            # Use model-specific pricing if only one model was used
            models_used = session_data.get('models_used', [])
            if len(models_used) == 1:
                session_cost = self._calculate_model_costs(list(models_used)[0], session_data)
            else:
                # For mixed models, calculate weighted average based on the most expensive model used
                session_cost = self._calculate_weighted_costs(session_data, models_used)
            costs['by_session'][session_id] = session_cost
        
        # Calculate costs by date
        for date, date_data in stats.get('by_date', {}).items():
            # For daily costs, sum up actual costs from all models used that day
            date_cost = self._calculate_weighted_costs(date_data, None)
            costs['by_date'][date] = date_cost
            
        return costs
    
    def _calculate_model_costs(self, model: str, usage: Dict[str, Any]) -> Dict[str, float]:
        """Calculate costs for a specific model."""
        model_pricing = self.pricing.get(model, self.pricing['default'])
        
        input_cost = (usage.get('input_tokens', 0) / 1_000_000) * model_pricing['input']
        output_cost = (usage.get('output_tokens', 0) / 1_000_000) * model_pricing['output']
        cache_write_cost = (usage.get('cache_creation_input_tokens', 0) / 1_000_000) * model_pricing['cache_write']
        cache_read_cost = (usage.get('cache_read_input_tokens', 0) / 1_000_000) * model_pricing['cache_read']
        
        total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
        
        return {
            'input_cost': input_cost,
            'output_cost': output_cost,
            'cache_write_cost': cache_write_cost,
            'cache_read_cost': cache_read_cost,
            'total_cost': total_cost,
            'input_tokens': usage.get('input_tokens', 0),
            'output_tokens': usage.get('output_tokens', 0),
            'cache_creation_tokens': usage.get('cache_creation_input_tokens', 0),
            'cache_read_tokens': usage.get('cache_read_input_tokens', 0)
        }
    
    def _calculate_weighted_costs(self, usage: Dict[str, Any], models_used: List[str] = None) -> Dict[str, float]:
        """Calculate costs using the most expensive model pricing or weighted average."""
        # If models are specified, use the most expensive one
        if models_used:
            # Find the most expensive model based on output pricing
            most_expensive_model = max(
                models_used,
                key=lambda m: self.pricing.get(m, self.pricing['default'])['output']
            )
            model_pricing = self.pricing.get(most_expensive_model, self.pricing['default'])
        else:
            # Use Opus pricing as it's the most expensive (conservative estimate)
            model_pricing = self.pricing.get('claude-opus-4-20250514', self.pricing['default'])
        
        input_cost = (usage.get('input_tokens', 0) / 1_000_000) * model_pricing['input']
        output_cost = (usage.get('output_tokens', 0) / 1_000_000) * model_pricing['output']
        cache_write_cost = (usage.get('cache_creation_input_tokens', 0) / 1_000_000) * model_pricing['cache_write']
        cache_read_cost = (usage.get('cache_read_input_tokens', 0) / 1_000_000) * model_pricing['cache_read']
        
        total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
        
        return {
            'input_cost': input_cost,
            'output_cost': output_cost,
            'cache_write_cost': cache_write_cost,
            'cache_read_cost': cache_read_cost,
            'total_cost': total_cost
        }