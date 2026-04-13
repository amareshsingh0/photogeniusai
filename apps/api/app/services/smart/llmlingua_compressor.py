"""
LLMLingua-2 Prompt Compression (Microsoft Research)

Compresses prompts by up to 20x while maintaining quality.
Uses bidirectional transformer (XLM-RoBERTa) for token classification.

Performance:
- 5.7x faster inference
- 50-80% token reduction
- <1.5 point EM score degradation
- Works with any LLM (model-agnostic)

Usage:
    from app.services.smart.llmlingua_compressor import LLMLinguaCompressor

    compressor = LLMLinguaCompressor()
    compressed = compressor.compress_prompt(
        prompt="Long verbose prompt...",
        rate=0.5  # 50% compression
    )
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_compressor_instance: Optional['PromptCompressor'] = None
_COMPRESSION_ENABLED = os.getenv("USE_LLMLINGUA_COMPRESSION", "true").lower() != "false"


class LLMLinguaCompressor:
    """
    Intelligent prompt compression using LLMLingua-2.

    Falls back gracefully to no compression if library not available.
    """

    def __init__(self):
        self.compressor = None
        self.available = False

        if not _COMPRESSION_ENABLED:
            logger.info("[llmlingua] Compression disabled (USE_LLMLINGUA_COMPRESSION=false)")
            return

        try:
            from llmlingua import PromptCompressor

            # Initialize with XLM-RoBERTa-large (best quality)
            self.compressor = PromptCompressor(
                model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                use_llmlingua2=True,  # Use LLMLingua-2 (bidirectional)
                device_map="cpu",  # CPU is fine for compression
            )
            self.available = True
            logger.info("[llmlingua] Initialized successfully (microsoft/llmlingua-2)")

        except ImportError:
            logger.warning("[llmlingua] llmlingua package not installed - compression disabled")
            logger.warning("[llmlingua] Install with: pip install llmlingua")

        except Exception as e:
            logger.warning("[llmlingua] Failed to initialize: %s - compression disabled", e)

    def compress_prompt(
        self,
        prompt: str,
        rate: float = 0.5,
        instruction: str = "",
        question: str = "",
        target_token: Optional[int] = None,
    ) -> str:
        """
        Compress a prompt using LLMLingua-2.

        Args:
            prompt: The full prompt to compress
            rate: Compression ratio (0.5 = 50% compression)
            instruction: System instruction (preserved at lower compression)
            question: User question (preserved at lower compression)
            target_token: Target token count (overrides rate if provided)

        Returns:
            Compressed prompt (or original if compression unavailable/fails)

        Example:
            >>> compressor = LLMLinguaCompressor()
            >>> long_prompt = "You are a world-class copywriter with 15 years of experience..."
            >>> compressed = compressor.compress_prompt(long_prompt, rate=0.5)
            >>> # "Copywriter 15yr exp at top agencies. Write impactful ad copy..."
        """
        if not self.available or not self.compressor:
            return prompt  # Fallback: no compression

        if not prompt or len(prompt) < 50:
            return prompt  # Too short to compress meaningfully

        try:
            # Build structured compression request
            contexts = [prompt]
            if instruction:
                contexts.insert(0, instruction)
            if question:
                contexts.append(question)

            # Compress with dynamic budget allocation
            result = self.compressor.compress_prompt(
                contexts,
                rate=rate if target_token is None else None,
                target_token=target_token,
                # Force dynamic compression (better quality)
                force_tokens=[],
                drop_consecutive=True,  # Drop repeated tokens
                use_sentence_level_filter=True,  # Keep high-quality sentences
            )

            compressed_prompt = result.get("compressed_prompt", prompt)

            # Log compression stats
            original_tokens = len(prompt.split())
            compressed_tokens = len(compressed_prompt.split())
            compression_ratio = 1 - (compressed_tokens / original_tokens) if original_tokens > 0 else 0

            logger.info(
                "[llmlingua] Compressed: %d → %d tokens (%.1f%% reduction)",
                original_tokens, compressed_tokens, compression_ratio * 100
            )

            return compressed_prompt

        except Exception as e:
            logger.warning("[llmlingua] Compression failed: %s - using original prompt", e)
            return prompt  # Fallback on error

    def compress_system_prompt(self, system_prompt: str, target_token: int = 1000) -> str:
        """
        Compress a system prompt to a target token count.

        System prompts can be aggressively compressed since they're static knowledge.

        Args:
            system_prompt: The full system prompt
            target_token: Target token count (default 1000)

        Returns:
            Compressed system prompt
        """
        return self.compress_prompt(
            prompt=system_prompt,
            target_token=target_token,
            rate=None,  # Use target_token instead
        )

    def compress_context(
        self,
        instruction: str,
        context: str,
        question: str,
        instruction_rate: float = 0.2,  # Keep 80% of instruction
        context_rate: float = 0.7,  # Compress context to 30%
        question_rate: float = 0.1,  # Keep 90% of question
    ) -> str:
        """
        Compress a structured prompt with different rates for each component.

        Dynamic budget allocation (from LLMLingua-2 paper):
        - Instruction: Low compression (critical for task accuracy)
        - Context (RAG, history): High compression (recoverable info)
        - Question: Low compression (user intent must be preserved)

        Args:
            instruction: System instruction
            context: Retrieved context or conversation history
            question: User question
            instruction_rate: Compression rate for instruction (default 0.2 = keep 80%)
            context_rate: Compression rate for context (default 0.7 = keep 30%)
            question_rate: Compression rate for question (default 0.1 = keep 90%)

        Returns:
            Compressed prompt with all components
        """
        if not self.available or not self.compressor:
            return f"{instruction}\n\n{context}\n\n{question}"

        try:
            result = self.compressor.compress_prompt(
                [instruction, context, question],
                rate=[instruction_rate, context_rate, question_rate],  # Per-component rates
                drop_consecutive=True,
                use_sentence_level_filter=True,
            )

            return result.get("compressed_prompt", f"{instruction}\n\n{context}\n\n{question}")

        except Exception as e:
            logger.warning("[llmlingua] Context compression failed: %s", e)
            return f"{instruction}\n\n{context}\n\n{question}"


# ── Module-level singleton ──────────────────────────────────────────────────

def get_compressor() -> LLMLinguaCompressor:
    """Get or create the global compressor instance."""
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = LLMLinguaCompressor()
    return _compressor_instance


# ── Convenience functions ──────────────────────────────────────────────────

def compress_prompt(prompt: str, rate: float = 0.5) -> str:
    """Convenience function: Compress a prompt using the global compressor."""
    return get_compressor().compress_prompt(prompt, rate=rate)


def compress_system_prompt(system_prompt: str, target_token: int = 1000) -> str:
    """Convenience function: Compress a system prompt to target token count."""
    return get_compressor().compress_system_prompt(system_prompt, target_token=target_token)
