from typing import List, Dict, Optional, Any
import tiktoken
import openai
from .base import BaseLLM
from .rate_limiter import RateLimiter


class DeepSeekLLM(BaseLLM):
    """DeepSeek API wrapper using OpenAI-compatible format."""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str = "https://api.siliconflow.cn/v1/",
        rate_limits: Optional[Dict[str, Any]] = None
    ):
        """Initialize DeepSeek LLM.
        
        Args:
            api_key: API key
            model: Model identifier (e.g., "deepseek-chat", "deepseek-coder")
            api_base: Base URL for the API
            rate_limits: Optional dictionary with rate limit settings
        """
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base.rstrip("/"),
        )
        self.model = model
        
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except:
            self.tokenizer = None
        
        # Default rate limits for DeepSeek
        default_limits = {
            "requests_per_minute": 60,
            "input_tokens_per_minute": 100000,
            "output_tokens_per_minute": 50000,
            "input_token_price_per_million": 0.14,
            "output_token_price_per_million": 0.28
        }
        
        limits = rate_limits or default_limits
        
        self.rate_limiter = RateLimiter(
            provider="DeepSeek",
            requests_per_minute=limits.get("requests_per_minute", default_limits["requests_per_minute"]),
            input_tokens_per_minute=limits.get("input_tokens_per_minute", default_limits["input_tokens_per_minute"]),
            output_tokens_per_minute=limits.get("output_tokens_per_minute", default_limits["output_tokens_per_minute"]),
            input_token_price_per_million=limits.get("input_token_price_per_million", default_limits["input_token_price_per_million"]),
            output_token_price_per_million=limits.get("output_token_price_per_million", default_limits["output_token_price_per_million"])
        )
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in a string."""
        if not text:
            return 0
        try:
            if self.tokenizer:
                return len(self.tokenizer.encode(text))
            else:
                return int(len(text.split()) * 1.3)
        except Exception:
            return int(len(text.split()) * 1.3)
    
    def _count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in all messages."""
        if not messages:
            return 0
        total_tokens = 0
        for message in messages:
            if "content" in message and message["content"]:
                total_tokens += self._count_tokens(message["content"])
        total_tokens += 4 * len(messages)
        total_tokens += 3
        return total_tokens
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate a response using DeepSeek API.
        
        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text
        """
        input_tokens = self._count_messages_tokens(messages)
        self.rate_limiter.wait_if_needed(input_tokens, max_tokens if max_tokens else 1000)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens if max_tokens else None
        )
        
        result_text = response.choices[0].message.content
        
        output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else self._count_tokens(result_text)
        input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else input_tokens
        
        self.rate_limiter.record_request(input_tokens, output_tokens)
        
        return result_text
    
    def format_message(self, role: str, content: str) -> Dict[str, str]:
        """Format message for API."""
        return {"role": role, "content": content}

