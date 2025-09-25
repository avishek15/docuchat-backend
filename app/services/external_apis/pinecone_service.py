"""Robust Pinecone service for agent-optimized document storage and retrieval."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import structlog
from pinecone import Pinecone
from app.services.external_apis.base import BaseAPIClient
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError

logger = structlog.get_logger()


class PineconeService(BaseAPIClient):
    """Agent-optimized Pinecone service with parallel processing and user namespace management."""

    def __init__(self):
        """Initialize Pinecone service with connection management."""
        super().__init__()
        self.settings = get_settings()

        # Initialize Pinecone client
        self.pc = None
        self.index = None
        self.index_name = self.settings.pinecone_index_name

        # Concurrency control (configurable, default 15)
        self._semaphore = asyncio.Semaphore(self.settings.pinecone_max_concurrent)

        # Initialize connection
        self._initialize_connection()

        self.logger = logger.bind(service="PineconeService")

    def _initialize_connection(self) -> None:
        """Initialize Pinecone connection and index."""
        try:
            # Get API key from settings
            api_key = self.settings.pinecone_api_key
            if not api_key:
                raise ExternalAPIError("Pinecone API key not found in environment")

            # Initialize Pinecone client
            self.pc = Pinecone(api_key=api_key)

            # Get index host and initialize index
            host = self.pc.describe_index(self.index_name)["host"]
            self.index = self.pc.Index(host=host)

            self.logger.info(
                "Pinecone connection initialized successfully", index=self.index_name
            )

        except Exception as e:
            self.logger.error("Failed to initialize Pinecone connection", error=str(e))
            raise ExternalAPIError(f"Pinecone initialization failed: {str(e)}")

    def _get_user_namespace(self, user_email: str) -> str:
        """Get namespace for user based on email."""
        # Use email directly as namespace (user email acts as namespace)
        return user_email.lower().strip()

    async def health_check(self) -> bool:
        """Check if Pinecone service is healthy."""
        try:
            if not self.index:
                return False

            # Try to describe the index to verify connection
            stats = self.index.describe_index_stats()
            self.logger.debug("Pinecone health check passed", stats=stats)
            return True

        except Exception as e:
            self.logger.error("Pinecone health check failed", error=str(e))
            return False

    # Agent Interface Methods
    async def search_in_file(
        self, user_email: str, filename: str, query: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for content within a specific file for agent queries."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                # Search with filename filter
                results = self.index.search(
                    namespace=namespace,
                    query={
                        "inputs": {"text": query},
                        "top_k": top_k,
                        "filter": {"filename": filename},
                    },
                    fields=[
                        "text",
                        "filename",
                        "chunk_number",
                        "document_type",
                        "created_at",
                    ],
                )

                # Format results for agent consumption
                formatted_results = []
                for match in results.get("matches", []):
                    formatted_results.append(
                        {
                            "id": match["id"],
                            "score": match["score"],
                            "text": match["metadata"].get("text", ""),
                            "filename": match["metadata"].get("filename", ""),
                            "chunk_number": match["metadata"].get("chunk_number", 0),
                            "document_type": match["metadata"].get("document_type", ""),
                            "created_at": match["metadata"].get("created_at", ""),
                        }
                    )

                self.logger.info(
                    "File-specific search completed",
                    user_email=user_email,
                    filename=filename,
                    results_count=len(formatted_results),
                )

                return formatted_results

            except Exception as e:
                self.logger.error(
                    "File search failed",
                    user_email=user_email,
                    filename=filename,
                    error=str(e),
                )
                raise ExternalAPIError(f"File search failed: {str(e)}")

    async def search_across_documents(
        self,
        user_email: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search across all user documents for agent cross-document analysis."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                # Build search query
                search_query = {"inputs": {"text": query}, "top_k": top_k}

                # Add filters if provided
                if filters:
                    search_query["filter"] = filters

                results = self.index.search(
                    namespace=namespace,
                    query=search_query,
                    fields=[
                        "text",
                        "filename",
                        "chunk_number",
                        "document_type",
                        "created_at",
                    ],
                )

                # Format results for agent consumption
                formatted_results = []
                for match in results.get("matches", []):
                    formatted_results.append(
                        {
                            "id": match["id"],
                            "score": match["score"],
                            "text": match["metadata"].get("text", ""),
                            "filename": match["metadata"].get("filename", ""),
                            "chunk_number": match["metadata"].get("chunk_number", 0),
                            "document_type": match["metadata"].get("document_type", ""),
                            "created_at": match["metadata"].get("created_at", ""),
                        }
                    )

                self.logger.info(
                    "Cross-document search completed",
                    user_email=user_email,
                    results_count=len(formatted_results),
                )

                return formatted_results

            except Exception as e:
                self.logger.error(
                    "Cross-document search failed", user_email=user_email, error=str(e)
                )
                raise ExternalAPIError(f"Cross-document search failed: {str(e)}")

    async def get_file_context(
        self, user_email: str, filename: str, max_chunks: int = 50
    ) -> List[Dict[str, Any]]:
        """Get comprehensive context from a file for agent reasoning."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                # Get all chunks from the file, ordered by chunk_number
                results = self.index.search(
                    namespace=namespace,
                    query={
                        "inputs": {
                            "text": "document content"
                        },  # Generic query to get all chunks
                        "top_k": max_chunks,
                        "filter": {"filename": filename},
                    },
                    fields=[
                        "text",
                        "filename",
                        "chunk_number",
                        "document_type",
                        "created_at",
                    ],
                )

                # Sort by chunk number for proper context order
                chunks = []
                for match in results.get("matches", []):
                    chunks.append(
                        {
                            "id": match["id"],
                            "text": match["metadata"].get("text", ""),
                            "chunk_number": match["metadata"].get("chunk_number", 0),
                            "filename": match["metadata"].get("filename", ""),
                            "document_type": match["metadata"].get("document_type", ""),
                            "created_at": match["metadata"].get("created_at", ""),
                        }
                    )

                # Sort by chunk number
                chunks.sort(key=lambda x: x["chunk_number"])

                self.logger.info(
                    "File context retrieved",
                    user_email=user_email,
                    filename=filename,
                    chunks_count=len(chunks),
                )

                return chunks

            except Exception as e:
                self.logger.error(
                    "File context retrieval failed",
                    user_email=user_email,
                    filename=filename,
                    error=str(e),
                )
                raise ExternalAPIError(f"File context retrieval failed: {str(e)}")

    async def get_document_summary(
        self, user_email: str, filename: str
    ) -> Dict[str, Any]:
        """Get summary information about a document."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                # Get document stats
                results = self.index.search(
                    namespace=namespace,
                    query={
                        "inputs": {"text": "document content"},
                        "top_k": 1000,  # Get many results to count chunks
                        "filter": {"filename": filename},
                    },
                    fields=["filename", "chunk_number", "document_type", "created_at"],
                )

                matches = results.get("matches", [])
                if not matches:
                    return {"filename": filename, "exists": False, "chunk_count": 0}

                # Calculate summary statistics
                chunk_numbers = [
                    match["metadata"].get("chunk_number", 0) for match in matches
                ]

                summary = {
                    "filename": filename,
                    "exists": True,
                    "chunk_count": len(matches),
                    "max_chunk_number": max(chunk_numbers) if chunk_numbers else 0,
                    "document_type": matches[0]["metadata"].get("document_type", ""),
                    "created_at": matches[0]["metadata"].get("created_at", ""),
                }

                self.logger.info(
                    "Document summary retrieved",
                    user_email=user_email,
                    filename=filename,
                    summary=summary,
                )

                return summary

            except Exception as e:
                self.logger.error(
                    "Document summary failed",
                    user_email=user_email,
                    filename=filename,
                    error=str(e),
                )
                raise ExternalAPIError(f"Document summary failed: {str(e)}")

    # Document Operations
    async def store_chunks(
        self,
        user_email: str,
        filename: str,
        chunks_batch: List[Dict[str, Any]],
        db_file_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Store pre-chunked document data with parallel processing."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)
                current_time = datetime.now(timezone.utc).isoformat()

                # Prepare records for upsert
                records = []
                for i, chunk in enumerate(chunks_batch):
                    # Use database file ID if available, otherwise fall back to filename
                    if db_file_id:
                        record_id = f"file_{db_file_id}#chunk{i + 1}"
                    else:
                        record_id = f"{filename}#chunk{i + 1}"

                    # Ensure required metadata is present
                    metadata = {
                        "text": chunk.get("text", ""),
                        "filename": filename,
                        "chunk_number": i + 1,
                        "document_type": chunk.get("document_type", "text"),
                        "created_at": current_time,
                        **chunk.get("metadata", {}),  # Additional metadata
                    }

                    # Add database file ID to metadata if available
                    if db_file_id:
                        metadata["db_file_id"] = db_file_id

                    records.append({"_id": record_id, **metadata})

                # Upsert records to Pinecone
                self.index.upsert_records(namespace, records)

                self.logger.info(
                    "Document chunks stored successfully",
                    user_email=user_email,
                    filename=filename,
                    chunks_count=len(records),
                )

                return {
                    "stored_chunks": len(records),
                    "filename": filename,
                    "namespace": namespace,
                }

            except Exception as e:
                self.logger.error(
                    "Failed to store document chunks",
                    user_email=user_email,
                    filename=filename,
                    error=str(e),
                )
                raise ExternalAPIError(f"Document storage failed: {str(e)}")

    async def batch_search_queries(
        self, user_email: str, queries_batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute multiple search queries in parallel for agent batch processing."""
        namespace = self._get_user_namespace(user_email)

        async def execute_single_search(query_data: Dict[str, Any]) -> Dict[str, Any]:
            async with self._semaphore:
                try:
                    query_text = query_data.get("query", "")
                    top_k = query_data.get("top_k", 10)
                    filters = query_data.get("filters", {})
                    query_id = query_data.get("id", "")

                    results = self.index.search(
                        namespace=namespace,
                        query={
                            "inputs": {"text": query_text},
                            "top_k": top_k,
                            "filter": filters,
                        },
                        fields=[
                            "text",
                            "filename",
                            "chunk_number",
                            "document_type",
                            "created_at",
                        ],
                    )

                    # Format results
                    formatted_results = []
                    for match in results.get("matches", []):
                        formatted_results.append(
                            {
                                "id": match["id"],
                                "score": match["score"],
                                "text": match["metadata"].get("text", ""),
                                "filename": match["metadata"].get("filename", ""),
                                "chunk_number": match["metadata"].get(
                                    "chunk_number", 0
                                ),
                                "document_type": match["metadata"].get(
                                    "document_type", ""
                                ),
                                "created_at": match["metadata"].get("created_at", ""),
                            }
                        )

                    return {
                        "query_id": query_id,
                        "query": query_text,
                        "results": formatted_results,
                        "results_count": len(formatted_results),
                    }

                except Exception as e:
                    return {
                        "query_id": query_id,
                        "query": query_data.get("query", ""),
                        "error": str(e),
                        "results": [],
                        "results_count": 0,
                    }

        try:
            # Execute all queries in parallel
            search_tasks = [execute_single_search(query) for query in queries_batch]
            results = await asyncio.gather(*search_tasks)

            self.logger.info(
                "Batch search queries completed",
                user_email=user_email,
                queries_count=len(queries_batch),
                total_results=sum(r["results_count"] for r in results),
            )

            return results

        except Exception as e:
            self.logger.error(
                "Batch search queries failed", user_email=user_email, error=str(e)
            )
            raise ExternalAPIError(f"Batch search failed: {str(e)}")

    async def delete_document(self, user_email: str, filename: str) -> Dict[str, int]:
        """Delete all chunks of a document from user's namespace."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                # First, get all chunk IDs for this document
                self.logger.info(
                    "Searching for chunks by filename",
                    user_email=user_email,
                    filename=filename,
                    namespace=namespace,
                )

                results = self.index.search(
                    namespace=namespace,
                    query={
                        "inputs": {"text": "document content"},
                        "top_k": 1000,  # Get all chunks
                        "filter": {"filename": filename},
                    },
                    fields=["filename"],
                )

                chunk_ids = [match["id"] for match in results.get("matches", [])]

                self.logger.info(
                    "Search results for filename",
                    user_email=user_email,
                    filename=filename,
                    found_chunks=len(chunk_ids),
                    chunk_ids=chunk_ids[:5]
                    if chunk_ids
                    else [],  # Log first 5 IDs for debugging
                )

                if not chunk_ids:
                    self.logger.info(
                        "No chunks found for document deletion",
                        user_email=user_email,
                        filename=filename,
                    )
                    return {"deleted_chunks": 0, "filename": filename}

                # Delete all chunks
                self.index.delete(namespace=namespace, ids=chunk_ids)

                self.logger.info(
                    "Document deleted successfully",
                    user_email=user_email,
                    filename=filename,
                    deleted_chunks=len(chunk_ids),
                )

                return {
                    "deleted_chunks": len(chunk_ids),
                    "filename": filename,
                    "namespace": namespace,
                }

            except Exception as e:
                self.logger.error(
                    "Document deletion failed",
                    user_email=user_email,
                    filename=filename,
                    error=str(e),
                )

    async def delete_file_by_db_id(
        self, user_email: str, db_file_id: int, filename: str = None
    ) -> Dict[str, int]:
        """Delete all chunks of a file using database file ID from metadata."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                self.logger.info(
                    "Deleting chunks using db_file_id metadata filter",
                    user_email=user_email,
                    db_file_id=db_file_id,
                    namespace=namespace,
                )

                # Use Pinecone's delete with metadata filter - this is the most reliable approach
                delete_response = self.index.delete(
                    filter={"db_file_id": {"$eq": db_file_id}}, namespace=namespace
                )

                self.logger.info(
                    "Delete operation completed using metadata filter",
                    user_email=user_email,
                    db_file_id=db_file_id,
                    delete_response=delete_response,
                )

                # Verify deletion by searching for remaining chunks
                verification_results = self.index.search(
                    namespace=namespace,
                    query={
                        "inputs": {"text": "verification query"},
                        "top_k": 5,
                        "filter": {"db_file_id": db_file_id},
                    },
                    fields=["db_file_id", "filename"],
                )

                remaining_chunks = len(verification_results.get("matches", []))

                if remaining_chunks == 0:
                    # Successfully deleted using metadata filter
                    self.logger.info(
                        "File deleted successfully using db_file_id metadata",
                        user_email=user_email,
                        db_file_id=db_file_id,
                    )
                    return {
                        "deleted_chunks": "unknown",  # Pinecone doesn't return exact count
                        "db_file_id": db_file_id,
                        "namespace": namespace,
                        "method": "db_file_id_metadata",
                    }

                # If chunks still remain, try filename fallback for legacy data
                if filename:
                    self.logger.info(
                        "Some chunks remain after db_file_id deletion, trying filename fallback",
                        user_email=user_email,
                        db_file_id=db_file_id,
                        filename=filename,
                        remaining_chunks=remaining_chunks,
                    )
                    fallback_result = await self.delete_document(user_email, filename)
                    fallback_result["method"] = "filename_fallback"
                    self.logger.info(
                        "Fallback deletion result",
                        user_email=user_email,
                        db_file_id=db_file_id,
                        filename=filename,
                        result=fallback_result,
                    )
                    return fallback_result

                # No chunks found with either method
                self.logger.info(
                    "No chunks found for file deletion",
                    user_email=user_email,
                    db_file_id=db_file_id,
                )
                return {
                    "deleted_chunks": 0,
                    "db_file_id": db_file_id,
                    "method": "none_found",
                }

            except Exception as e:
                self.logger.error(
                    "File deletion by database ID failed",
                    user_email=user_email,
                    db_file_id=db_file_id,
                    error=str(e),
                )
                raise ExternalAPIError(f"Document deletion failed: {str(e)}")

    async def update_document_chunks(
        self, user_email: str, filename: str, chunks_batch: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Update existing document by replacing all chunks."""
        try:
            # First delete existing chunks
            delete_result = await self.delete_document(user_email, filename)

            # Then store new chunks
            store_result = await self.store_chunks(user_email, filename, chunks_batch)

            self.logger.info(
                "Document updated successfully",
                user_email=user_email,
                filename=filename,
                deleted_chunks=delete_result["deleted_chunks"],
                stored_chunks=store_result["stored_chunks"],
            )

            return {
                "updated_filename": filename,
                "deleted_chunks": delete_result["deleted_chunks"],
                "stored_chunks": store_result["stored_chunks"],
            }

        except Exception as e:
            self.logger.error(
                "Document update failed",
                user_email=user_email,
                filename=filename,
                error=str(e),
            )
            raise ExternalAPIError(f"Document update failed: {str(e)}")

    # User Management Methods
    async def create_user_namespace(self, user_email: str) -> bool:
        """Create/initialize user namespace (Pinecone creates namespaces automatically)."""
        try:
            namespace = self._get_user_namespace(user_email)

            # Pinecone creates namespaces automatically on first upsert
            # We can verify namespace exists by checking index stats
            await self.health_check()

            self.logger.info(
                "User namespace ready", user_email=user_email, namespace=namespace
            )

            return True

        except Exception as e:
            self.logger.error(
                "User namespace creation failed", user_email=user_email, error=str(e)
            )
            return False

    async def get_user_stats(self, user_email: str) -> Dict[str, Any]:
        """Get comprehensive statistics for user's documents and storage."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                # Get all vectors in user's namespace
                # Use a generic query to get all user data
                results = self.index.search(
                    namespace=namespace,
                    query={
                        "inputs": {
                            "text": "document content data"
                        },  # Generic query instead of empty
                        "top_k": 10000,  # Large number to get all vectors
                    },
                    fields=["filename", "document_type", "created_at"],
                )

                matches = results.get("matches", [])

                # Calculate statistics
                total_chunks = len(matches)
                unique_files = set()
                document_types = {}

                for match in matches:
                    filename = match["metadata"].get("filename", "unknown")
                    doc_type = match["metadata"].get("document_type", "unknown")

                    unique_files.add(filename)
                    document_types[doc_type] = document_types.get(doc_type, 0) + 1

                # Get index-level stats for namespace
                index_stats = self.index.describe_index_stats()
                namespace_stats = index_stats.get("namespaces", {}).get(namespace, {})

                stats = {
                    "user_email": user_email,
                    "namespace": namespace,
                    "total_documents": len(unique_files),
                    "total_chunks": total_chunks,
                    "document_types": document_types,
                    "unique_filenames": list(unique_files),
                    "vector_count": namespace_stats.get("vector_count", 0),
                    "last_activity": max(
                        [m["metadata"].get("created_at", "") for m in matches],
                        default="",
                    ),
                }

                self.logger.info(
                    "User statistics retrieved", user_email=user_email, stats=stats
                )

                return stats

            except Exception as e:
                self.logger.error(
                    "Failed to get user statistics", user_email=user_email, error=str(e)
                )
                raise ExternalAPIError(f"User statistics retrieval failed: {str(e)}")

    async def cleanup_user_data(self, user_email: str) -> Dict[str, int]:
        """Complete cleanup of all user data for GDPR compliance."""
        async with self._semaphore:
            try:
                namespace = self._get_user_namespace(user_email)

                # Get all vector IDs in the namespace
                results = self.index.search(
                    namespace=namespace,
                    query={
                        "inputs": {"text": "document content"},
                        "top_k": 10000,  # Large number to get all vectors
                    },
                    fields=["filename"],
                )

                vector_ids = [match["id"] for match in results.get("matches", [])]

                if not vector_ids:
                    self.logger.info(
                        "No data found for user cleanup",
                        user_email=user_email,
                        namespace=namespace,
                    )
                    return {
                        "deleted_vectors": 0,
                        "deleted_documents": 0,
                        "namespace": namespace,
                    }

                # Count unique documents
                unique_files = set()
                for match in results.get("matches", []):
                    filename = match["metadata"].get("filename", "")
                    if filename:
                        unique_files.add(filename)

                # Delete all vectors in the namespace using direct delete_all operation
                # This is more reliable than ID-based deletion
                self.index.delete_namespace(namespace=namespace)
                # self.index.delete(delete_all=True, namespace=namespace)

                # Note: Pinecone doesn't require explicit namespace deletion
                # Empty namespaces are automatically cleaned up

                cleanup_result = {
                    "deleted_vectors": len(vector_ids),
                    "deleted_documents": len(unique_files),
                    "namespace": namespace,
                    "user_email": user_email,
                }

                self.logger.info(
                    "User data cleanup completed",
                    user_email=user_email,
                    result=cleanup_result,
                )

                return cleanup_result

            except Exception as e:
                self.logger.error(
                    "User data cleanup failed", user_email=user_email, error=str(e)
                )
                raise ExternalAPIError(f"User data cleanup failed: {str(e)}")
