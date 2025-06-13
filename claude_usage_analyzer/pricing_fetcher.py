"""Dynamic pricing fetcher for LiteLLM model costs."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


@dataclass
class ModelPricing:
    """Pricing data for a model."""
    input_cost_per_token: Optional[float] = None
    output_cost_per_token: Optional[float] = None
    cache_creation_input_token_cost: Optional[float] = None
    cache_read_input_token_cost: Optional[float] = None

    def to_million_token_costs(self) -> Dict[str, float]:
        """Convert per-token costs to per-million-token costs."""
        return {
            'input': (self.input_cost_per_token or 0) * 1_000_000,
            'output': (self.output_cost_per_token or 0) * 1_000_000,
            'cache_write': (self.cache_creation_input_token_cost or 0) * 1_000_000,
            'cache_read': (self.cache_read_input_token_cost or 0) * 1_000_000
        }


class LiteLLMPricingFetcher:
    """Fetches and caches pricing data from LiteLLM."""
    
    LITELLM_URL = 'https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json'
    CACHE_TTL = timedelta(hours=24)
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the pricing fetcher.
        
        Args:
            cache_dir: Directory for caching pricing data. If None, uses default.
        """
        self.cache_dir = cache_dir or self._get_default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Optional[Dict[str, ModelPricing]] = None
        
    def _get_default_cache_dir(self) -> Path:
        """Get platform-specific cache directory."""
        import os
        
        # Follow XDG Base Directory specification
        if os.name == 'nt':  # Windows
            base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        else:  # macOS/Linux
            base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
        
        return base / 'claude-usage-analyzer'
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        metadata_file = self.cache_dir / 'metadata.json'
        if not metadata_file.exists():
            return False
            
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            cached_time = datetime.fromisoformat(metadata['timestamp'])
            return datetime.now() - cached_time < self.CACHE_TTL
        except Exception:
            return False
    
    def _load_from_cache(self) -> Optional[Dict[str, ModelPricing]]:
        """Load pricing from file cache."""
        if not self._is_cache_valid():
            return None
            
        pricing_file = self.cache_dir / 'litellm_pricing.json'
        try:
            with open(pricing_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = {}
            for model, pricing_data in data.items():
                if isinstance(pricing_data, dict):
                    result[model] = ModelPricing(**pricing_data)
            return result
        except Exception as e:
            logger.debug(f"Failed to load cache: {e}")
            return None
    
    def _save_to_cache(self, pricing_data: Dict[str, ModelPricing]) -> None:
        """Save pricing to file cache."""
        try:
            # Save pricing data
            pricing_file = self.cache_dir / 'litellm_pricing.json'
            serializable_data = {
                model: asdict(pricing) 
                for model, pricing in pricing_data.items()
            }
            
            with open(pricing_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2)
            
            # Save metadata
            metadata_file = self.cache_dir / 'metadata.json'
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'source': self.LITELLM_URL,
                    'count': len(pricing_data)
                }, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to save cache: {e}")
    
    def fetch_pricing(self, force_refresh: bool = False) -> Optional[Dict[str, ModelPricing]]:
        """Fetch pricing with caching strategy.
        
        Args:
            force_refresh: Force refresh from LiteLLM even if cache is valid
            
        Returns:
            Dictionary of model pricing data, or None if fetch failed
        """
        # Check if requests is available
        if not requests:
            logger.debug("requests library not available, skipping LiteLLM fetch")
            return None
        
        # 1. Memory cache
        if self._memory_cache and not force_refresh:
            return self._memory_cache
        
        # 2. File cache
        if not force_refresh:
            cached = self._load_from_cache()
            if cached:
                self._memory_cache = cached
                logger.debug(f"Loaded {len(cached)} models from cache")
                return cached
        
        # 3. Fetch from GitHub
        try:
            logger.debug(f"Fetching pricing from {self.LITELLM_URL}")
            response = requests.get(self.LITELLM_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            pricing = {}
            for model_name, model_data in data.items():
                if isinstance(model_data, dict):
                    # Only include models with pricing data
                    if any(key in model_data for key in [
                        'input_cost_per_token', 
                        'output_cost_per_token',
                        'cache_creation_input_token_cost',
                        'cache_read_input_token_cost'
                    ]):
                        pricing[model_name] = ModelPricing(
                            input_cost_per_token=model_data.get('input_cost_per_token'),
                            output_cost_per_token=model_data.get('output_cost_per_token'),
                            cache_creation_input_token_cost=model_data.get('cache_creation_input_token_cost'),
                            cache_read_input_token_cost=model_data.get('cache_read_input_token_cost')
                        )
            
            logger.info(f"Fetched pricing for {len(pricing)} models from LiteLLM")
            
            # Cache the results
            self._memory_cache = pricing
            self._save_to_cache(pricing)
            return pricing
            
        except Exception as e:
            logger.warning(f"Failed to fetch LiteLLM pricing: {e}")
            return None
    
    def get_model_pricing(self, model_name: str, exact_match: bool = False) -> Optional[ModelPricing]:
        """Get pricing for a specific model.
        
        Args:
            model_name: The model name to look up
            exact_match: If True, only return exact matches
            
        Returns:
            ModelPricing object or None if not found
        """
        pricing = self.fetch_pricing()
        if not pricing:
            return None
        
        # Direct match
        if model_name in pricing:
            return pricing[model_name]
        
        if exact_match:
            return None
        
        # Try common variations
        variations = [
            model_name,
            f"anthropic/{model_name}",
            f"bedrock/{model_name}",
            f"vertex_ai/{model_name}",
        ]
        
        for variant in variations:
            if variant in pricing:
                return pricing[variant]
        
        # Fuzzy matching - find models that contain the search term
        model_lower = model_name.lower()
        for key, value in pricing.items():
            key_lower = key.lower()
            # Check if the model name is contained in the key
            if model_lower in key_lower:
                return value
            # Check for partial matches (e.g., "opus-4" in "claude-opus-4-20250514")
            if any(part in key_lower for part in model_lower.split('-')):
                return value
        
        return None