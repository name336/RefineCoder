from typing import List, Dict, Optional, Any
import tiktoken
import openai
from .base import BaseLLM
from .rate_limiter import RateLimiter

class GeminiLLM(BaseLLM):
    """Google Gemini API wrapper using OpenAI-compatible format."""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str = "https://aihubmix.com/v1",
        rate_limits: Optional[Dict[str, Any]] = None
    ):
        """Initialize Gemini LLM using OpenAI-compatible API.
        
        Args:
            api_key: API key
            model: Model identifier (e.g., "gemini-1.5-flash", "gemini-1.5-pro")
            api_base: Base URL for the API
            rate_limits: Optional dictionary with rate limit settings
        """
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base.rstrip("/"),
        )
        self.model = model
        
        try:
            # Initialize tokenizer for token counting
            # Using tiktoken cl100k_base as a reasonable approximation
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except:
            # Fallback to basic word counting if tokenizer fails
            self.tokenizer = None
        
        # Default rate limits for Gemini (adjust based on actual API limits)
        default_limits = {
            "requests_per_minute": 60,
            "input_tokens_per_minute": 100000,
            "output_tokens_per_minute": 50000,
            "input_token_price_per_million": 0.125,  # Approximate for gemini-1.5-flash
            "output_token_price_per_million": 0.375  # Approximate for gemini-1.5-flash
        }
        
        # Use provided rate limits or defaults
        limits = rate_limits or default_limits
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            provider="Gemini",
            requests_per_minute=limits.get("requests_per_minute", default_limits["requests_per_minute"]),
            input_tokens_per_minute=limits.get("input_tokens_per_minute", default_limits["input_tokens_per_minute"]),
            output_tokens_per_minute=limits.get("output_tokens_per_minute", default_limits["output_tokens_per_minute"]),
            input_token_price_per_million=limits.get("input_token_price_per_million", default_limits["input_token_price_per_million"]),
            output_token_price_per_million=limits.get("output_token_price_per_million", default_limits["output_token_price_per_million"])
        )
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in a string using the model's tokenizer.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Token count
        """
        if not text:
            return 0
            
        try:
            if self.tokenizer:
                return len(self.tokenizer.encode(text))
            else:
                # Fallback: rough estimate if tokenizer not available
                return len(text.split()) * 1.3
        except Exception as e:
            # Log the error but don't fail
            import logging
            logging.warning(f"Failed to count tokens for Gemini: {e}")
            # Fallback: rough estimate if tokenizer fails
            return len(text.split()) * 1.3
    
    def _count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in all messages.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Total token count
        """
        if not messages:
            return 0
            
        total_tokens = 0
        
        # Count tokens in each message
        for message in messages:
            if "content" in message and message["content"]:
                total_tokens += self._count_tokens(message["content"])
            
        # Add overhead for message formatting (estimated)
        total_tokens += 4 * len(messages)
        
        # Add tokens for model overhead
        total_tokens += 3
        
        return total_tokens
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response using OpenAI-compatible Gemini API with rate limiting.
        
        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text
        """
        # Count input tokens
        input_tokens = self._count_messages_tokens(messages)
        
        # Wait if we're approaching rate limits
        self.rate_limiter.wait_if_needed(input_tokens, max_tokens if max_tokens else 1000)
        
        # Make the API call using OpenAI-compatible format
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens if max_tokens else None
        )
        
        result_text = response.choices[0].message.content
        
        # Count output tokens and record request
        output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else self._count_tokens(result_text)
        input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else input_tokens
        
        self.rate_limiter.record_request(input_tokens, output_tokens)
        
        return result_text
    
    def format_message(self, role: str, content: str) -> Dict[str, str]:
        """Format message for OpenAI-compatible API.
        
        Args:
            role: Message role (system, user, assistant)
            content: Message content
            
        Returns:
            Formatted message dictionary
        """
        # OpenAI-compatible format
        return {"role": role, "content": content}