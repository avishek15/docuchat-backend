"""Text processing utilities for document chunking and content management."""

import re
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()


class TextChunker:
    """Text chunking utility for document processing."""

    def __init__(
        self,
        chunk_size: int = 2048,  # 512 tokens * 4 chars/token = ~2048 characters
        overlap_size: int = 256,  # ~64 tokens overlap (12.5% of chunk size)
        min_chunk_size: int = 128,  # ~32 tokens minimum
    ):
        """
        Initialize text chunker with configurable parameters.

        Args:
            chunk_size: Target size for each chunk in characters
            overlap_size: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size to avoid tiny fragments
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size
        self.logger = logger.bind(service="TextChunker")

    def chunk_text(
        self, text: str, filename: str, document_type: str = "text"
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into overlapping segments optimized for vector search.

        Args:
            text: The text content to chunk
            filename: Name of the source file
            document_type: Type of document (text, markdown, etc.)

        Returns:
            List of chunk dictionaries with text and metadata
        """
        try:
            # Enhanced input validation with debugging
            self.logger.debug(
                "Starting text chunking",
                filename=filename,
                text_length=len(text) if text else 0,
                text_type=type(text).__name__,
                document_type=document_type,
                chunk_size=self.chunk_size,
                overlap_size=self.overlap_size,
                min_chunk_size=self.min_chunk_size,
            )

            if not text:
                self.logger.warning("No text provided for chunking", filename=filename)
                return []

            if not text.strip():
                self.logger.warning(
                    "Only whitespace provided for chunking",
                    filename=filename,
                    text_length=len(text),
                )
                return []

            # Detect potential problematic content
            problematic_chars = []
            if "\x00" in text:  # Null bytes
                problematic_chars.append("null_bytes")
            if len([c for c in text if ord(c) > 65535]) > 0:  # Rare Unicode
                problematic_chars.append("rare_unicode")
            if len(text.splitlines()) > 10000:  # Too many lines
                problematic_chars.append("excessive_lines")

            if problematic_chars:
                self.logger.warning(
                    "Detected potentially problematic content",
                    filename=filename,
                    issues=problematic_chars,
                    text_preview=text[:100] + "..." if len(text) > 100 else text,
                )

            # Clean and normalize text
            self.logger.debug("Starting text cleaning", filename=filename)
            try:
                cleaned_text = self._clean_text(text)
                self.logger.debug(
                    "Text cleaning completed",
                    filename=filename,
                    original_length=len(text),
                    cleaned_length=len(cleaned_text),
                )
            except Exception as clean_error:
                self.logger.error(
                    "Text cleaning failed",
                    filename=filename,
                    error=str(clean_error),
                    error_type=type(clean_error).__name__,
                )
                raise

            # Split into sentences for better chunk boundaries
            self.logger.debug("Starting sentence splitting", filename=filename)
            try:
                sentences = self._split_into_sentences(cleaned_text)
                self.logger.debug(
                    "Sentence splitting completed",
                    filename=filename,
                    sentences_count=len(sentences),
                    avg_sentence_length=sum(len(s) for s in sentences)
                    // max(1, len(sentences)),
                )
            except Exception as sentence_error:
                self.logger.error(
                    "Sentence splitting failed",
                    filename=filename,
                    error=str(sentence_error),
                    error_type=type(sentence_error).__name__,
                )
                raise

            # Create chunks respecting sentence boundaries
            self.logger.debug("Starting chunk creation", filename=filename)
            try:
                # Log sample sentences to debug potential infinite loops
                sample_sentences = sentences[:5] if len(sentences) > 5 else sentences
                self.logger.debug(
                    "Sample sentences for debugging",
                    filename=filename,
                    sample_count=len(sample_sentences),
                    sample_sentences=[
                        s[:100] + "..." if len(s) > 100 else s for s in sample_sentences
                    ],
                )

                chunks = self._create_chunks_from_sentences(sentences)
                self.logger.debug(
                    "Chunk creation completed",
                    filename=filename,
                    raw_chunks_count=len(chunks),
                    avg_raw_chunk_size=sum(len(c) for c in chunks)
                    // max(1, len(chunks)),
                )
            except Exception as chunk_error:
                self.logger.error(
                    "Chunk creation failed",
                    filename=filename,
                    error=str(chunk_error),
                    error_type=type(chunk_error).__name__,
                    sentences_count=len(sentences) if "sentences" in locals() else 0,
                )
                raise

            # Format chunks with metadata
            self.logger.debug("Starting chunk formatting", filename=filename)
            formatted_chunks = []

            try:
                for i, chunk_text in enumerate(chunks):
                    if len(chunk_text.strip()) >= self.min_chunk_size:
                        formatted_chunks.append(
                            {
                                "text": chunk_text.strip(),
                                "document_type": document_type,
                                "metadata": {
                                    "original_filename": filename,
                                    "chunk_size": len(chunk_text),
                                    "word_count": len(chunk_text.split()),
                                    "chunk_index": i,
                                },
                            }
                        )
                    else:
                        self.logger.debug(
                            "Chunk too small, skipping",
                            filename=filename,
                            chunk_index=i,
                            chunk_size=len(chunk_text.strip()),
                            min_size=self.min_chunk_size,
                        )

            except Exception as format_error:
                self.logger.error(
                    "Chunk formatting failed",
                    filename=filename,
                    error=str(format_error),
                    error_type=type(format_error).__name__,
                    chunks_count=len(chunks),
                )
                raise

            # Final validation
            if not formatted_chunks:
                self.logger.warning(
                    "No valid chunks created after formatting",
                    filename=filename,
                    raw_chunks_count=len(chunks),
                    text_length=len(text),
                    min_chunk_size=self.min_chunk_size,
                )

            self.logger.info(
                "Text chunking completed successfully",
                filename=filename,
                original_length=len(text),
                cleaned_length=len(cleaned_text),
                sentences_count=len(sentences),
                raw_chunks_count=len(chunks),
                formatted_chunks_count=len(formatted_chunks),
                avg_chunk_size=sum(len(c["text"]) for c in formatted_chunks)
                // max(1, len(formatted_chunks))
                if formatted_chunks
                else 0,
                total_formatted_length=sum(len(c["text"]) for c in formatted_chunks),
            )

            return formatted_chunks

        except Exception as e:
            self.logger.error(
                "Text chunking failed with unexpected error",
                filename=filename,
                error=str(e),
                error_type=type(e).__name__,
                text_length=len(text) if text else 0,
                text_preview=text[:200] + "..." if text and len(text) > 200 else text,
            )
            raise

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Remove excessive whitespace while preserving paragraph breaks
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Multiple newlines to double
        text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces/tabs to single space
        text = re.sub(r"\n[ \t]+", "\n", text)  # Leading whitespace on lines
        text = re.sub(r"[ \t]+\n", "\n", text)  # Trailing whitespace on lines

        return text.strip()

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using simple heuristics."""
        # Simple sentence splitting on common sentence endings
        # This is basic - could be enhanced with proper NLP libraries
        sentence_endings = r"[.!?]+\s+"
        sentences = re.split(sentence_endings, text)

        # Clean up sentences and remove empty ones
        sentences = [s.strip() for s in sentences if s.strip()]

        # Handle the case where the last sentence doesn't end with punctuation
        if sentences and not re.search(r"[.!?]$", sentences[-1]):
            sentences[-1] += "."

        return sentences

    def _create_chunks_from_sentences(self, sentences: List[str]) -> List[str]:
        """Create chunks from sentences, respecting boundaries and overlap."""
        if not sentences:
            return []

        chunks = []
        current_chunk = ""
        sentence_index = 0
        max_iterations = len(sentences) * 3  # Safety limit to prevent infinite loops
        iteration_count = 0

        self.logger.debug(
            "Starting chunk creation loop",
            sentences_count=len(sentences),
            max_iterations=max_iterations,
        )

        while sentence_index < len(sentences) and iteration_count < max_iterations:
            iteration_count += 1

            # Log progress every 50 iterations to detect infinite loops
            if iteration_count % 50 == 0:
                self.logger.warning(
                    "Chunk creation taking many iterations - possible infinite loop",
                    iteration_count=iteration_count,
                    sentence_index=sentence_index,
                    sentences_total=len(sentences),
                    current_chunk_length=len(current_chunk),
                )
            # Start new chunk
            current_chunk = ""
            chunk_start_index = sentence_index

            # Add sentences until we reach target chunk size
            while (
                sentence_index < len(sentences)
                and len(current_chunk) + len(sentences[sentence_index]) + 1
                <= self.chunk_size
            ):
                if current_chunk:
                    current_chunk += " "
                current_chunk += sentences[sentence_index]
                sentence_index += 1

            # If we couldn't fit even one sentence, split it at word boundaries
            if not current_chunk and sentence_index < len(sentences):
                long_sentence = sentences[sentence_index]
                current_chunk = self._split_long_sentence_at_word_boundary(
                    long_sentence, self.chunk_size
                )
                sentence_index += 1

            if current_chunk:
                chunks.append(current_chunk)

            # Calculate overlap for next chunk
            if sentence_index < len(sentences):
                # Go back to create overlap
                overlap_text = ""
                overlap_sentence_index = sentence_index - 1

                # Build overlap by going backwards through sentences
                while (
                    overlap_sentence_index >= chunk_start_index
                    and len(overlap_text) < self.overlap_size
                ):
                    sentence_to_add = sentences[overlap_sentence_index]
                    if (
                        len(overlap_text) + len(sentence_to_add) + 1
                        <= self.overlap_size
                    ):
                        if overlap_text:
                            overlap_text = sentence_to_add + " " + overlap_text
                        else:
                            overlap_text = sentence_to_add
                    overlap_sentence_index -= 1

                # Adjust sentence_index to include overlap
                if overlap_text:
                    # Find where to restart based on overlap
                    words_in_overlap = len(overlap_text.split())
                    sentences_to_back_track = min(
                        2, words_in_overlap // 10
                    )  # Heuristic

                    # CRITICAL FIX: Ensure forward progress to prevent infinite loops
                    new_sentence_index = max(
                        chunk_start_index, sentence_index - sentences_to_back_track
                    )

                    # If we would go back to the same position or earlier, force forward progress
                    if new_sentence_index <= chunk_start_index:
                        sentence_index = chunk_start_index + 1
                    else:
                        sentence_index = new_sentence_index

        # Check if we hit the iteration limit (infinite loop protection)
        if iteration_count >= max_iterations:
            self.logger.error(
                "Chunk creation hit iteration limit - possible infinite loop detected",
                iteration_count=iteration_count,
                sentence_index=sentence_index,
                sentences_total=len(sentences),
                chunks_created=len(chunks),
            )
            raise RuntimeError(
                f"Chunk creation exceeded maximum iterations ({max_iterations})"
            )

        self.logger.debug(
            "Chunk creation loop completed",
            total_iterations=iteration_count,
            chunks_created=len(chunks),
        )

        return chunks

    def _split_long_sentence_at_word_boundary(
        self, sentence: str, max_size: int
    ) -> str:
        """Split a long sentence at word boundaries to avoid cutting words."""
        if len(sentence) <= max_size:
            return sentence

        # Find the last space before max_size to avoid cutting words
        words = sentence.split()
        current_chunk = ""

        for word in words:
            # Check if adding this word would exceed the limit
            test_chunk = current_chunk + (" " if current_chunk else "") + word
            if len(test_chunk) <= max_size:
                current_chunk = test_chunk
            else:
                # If we haven't added any words yet, we need to handle a very long word
                if not current_chunk:
                    # For extremely long words, we have no choice but to cut them
                    # But we'll try to cut at a reasonable point (like a hyphen)
                    current_chunk = self._split_long_word(word, max_size)
                break

        # If we still have an empty chunk, take at least something
        if not current_chunk and sentence:
            current_chunk = self._split_long_word(sentence, max_size)

        return current_chunk

    def _split_long_word(self, word: str, max_size: int) -> str:
        """Split an extremely long word, preferring hyphens or other natural break points."""
        if len(word) <= max_size:
            return word

        # Try to find natural break points (hyphens, underscores, etc.)
        break_chars = ["-", "_", ".", "/"]

        for break_char in break_chars:
            if break_char in word:
                parts = word.split(break_char)
                result = ""
                for i, part in enumerate(parts):
                    test_result = result + (break_char if result else "") + part
                    if len(test_result) <= max_size:
                        result = test_result
                    else:
                        break
                if result:
                    return result

        # As a last resort, cut at character boundary but leave a warning
        self.logger.warning(
            "Had to split word at character boundary",
            word=word[:50] + "..." if len(word) > 50 else word,
            max_size=max_size,
        )
        return word[:max_size]

    def estimate_token_count(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough estimate: ~4 characters per token for English text
        return len(text) // 4

    def validate_chunk_quality(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate the quality of generated chunks."""
        if not chunks:
            return {"valid": False, "reason": "No chunks generated"}

        chunk_sizes = [len(chunk["text"]) for chunk in chunks]

        stats = {
            "valid": True,
            "total_chunks": len(chunks),
            "avg_chunk_size": sum(chunk_sizes) // len(chunk_sizes),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes),
            "chunks_too_small": sum(
                1 for size in chunk_sizes if size < self.min_chunk_size
            ),
            "chunks_too_large": sum(
                1 for size in chunk_sizes if size > self.chunk_size * 1.2
            ),
        }

        # Validation rules
        if stats["chunks_too_small"] > len(chunks) * 0.2:  # More than 20% too small
            stats["valid"] = False
            stats["reason"] = "Too many small chunks"
        elif stats["avg_chunk_size"] < self.min_chunk_size:
            stats["valid"] = False
            stats["reason"] = "Average chunk size too small"

        return stats


def create_text_chunker(
    chunk_size: int = 2048, overlap_size: int = 256, min_chunk_size: int = 128
) -> TextChunker:
    """Factory function to create a text chunker with custom settings."""
    return TextChunker(
        chunk_size=chunk_size, overlap_size=overlap_size, min_chunk_size=min_chunk_size
    )
