"""File management database service for file and chunk operations."""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import update, delete
import structlog
from app.models.files import File, FileChunk, FileCreate, FileUpdate, ChunkCreate
from .base import BaseDatabaseService

logger = structlog.get_logger()


class FileDatabaseService(BaseDatabaseService):
    """Database service for file management operations."""

    def __init__(self):
        super().__init__()
        self.logger = logger.bind(service="FileDatabaseService")

    # File operations
    async def create_file(self, file_data: FileCreate) -> File:
        """Create a new file record."""
        try:
            with self._get_session() as session:
                file = File(
                    file_id=file_data.file_id,
                    user_id=file_data.user_id,
                    file_name=file_data.file_name,
                    file_size=file_data.file_size,
                    file_type=file_data.file_type,
                    content_hash=file_data.content_hash,
                    storage_path=file_data.storage_path,
                    status=file_data.status,
                    processed_at=file_data.processed_at,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(file)
                session.commit()
                session.refresh(file)

                self.logger.info(
                    "File created successfully",
                    file_id=file.id,
                    user_id=file_data.user_id,
                )
                return file
        except Exception as e:
            self.logger.error("Failed to create file", error=str(e))
            raise

    async def get_file_by_id(self, file_id: int) -> Optional[File]:
        """Get file by ID."""
        try:
            with self._get_session() as session:
                result = session.query(File).filter(File.id == file_id).first()
                return result
        except Exception as e:
            self.logger.error("Failed to get file by ID", file_id=file_id, error=str(e))
            raise

    async def get_file_by_file_id(self, file_id: str) -> Optional[File]:
        """Get file by file_id (UUID)."""
        try:
            with self._get_session() as session:
                result = session.query(File).filter(File.file_id == file_id).first()
                return result
        except Exception as e:
            self.logger.error(
                "Failed to get file by file_id", file_id=file_id, error=str(e)
            )
            raise

    async def update_file(self, file_id: int, file_data: FileUpdate) -> Optional[File]:
        """Update file information."""
        try:
            with self._get_session() as session:
                file = session.query(File).filter(File.id == file_id).first()
                if not file:
                    return None

                # Update fields
                if file_data.file_name is not None:
                    file.file_name = file_data.file_name
                if file_data.file_size is not None:
                    file.file_size = file_data.file_size
                if file_data.file_type is not None:
                    file.file_type = file_data.file_type
                if file_data.content_hash is not None:
                    file.content_hash = file_data.content_hash
                if file_data.storage_path is not None:
                    file.storage_path = file_data.storage_path
                if file_data.status is not None:
                    file.status = file_data.status
                if file_data.processed_at is not None:
                    file.processed_at = file_data.processed_at

                file.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(file)

                self.logger.info("File updated successfully", file_id=file_id)
                return file
        except Exception as e:
            self.logger.error("Failed to update file", file_id=file_id, error=str(e))
            raise

    async def delete_file(self, file_id: int) -> bool:
        """Delete a file and all its chunks."""
        try:
            with self._get_session() as session:
                # Delete all chunks first
                session.execute(delete(FileChunk).where(FileChunk.file_id == file_id))

                # Delete the file
                session.execute(delete(File).where(File.id == file_id))

                session.commit()

                self.logger.info("File deleted successfully", file_id=file_id)
                return True
        except Exception as e:
            self.logger.error("Failed to delete file", file_id=file_id, error=str(e))
            raise

    async def get_user_files(self, user_id: int) -> List[File]:
        """Get all files for a user."""
        try:
            with self._get_session() as session:
                result = session.query(File).filter(File.user_id == user_id).all()
                return result
        except Exception as e:
            self.logger.error("Failed to get user files", user_id=user_id, error=str(e))
            raise

    # File chunk operations
    async def create_file_chunk(self, chunk_data: ChunkCreate) -> FileChunk:
        """Create a new file chunk."""
        try:
            with self._get_session() as session:
                chunk = FileChunk(
                    file_id=chunk_data.file_id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    embedding_id=chunk_data.embedding_id,
                    token_count=chunk_data.token_count,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(chunk)
                session.commit()
                session.refresh(chunk)

                self.logger.info(
                    "File chunk created successfully",
                    chunk_id=chunk.id,
                    file_id=chunk_data.file_id,
                )
                return chunk
        except Exception as e:
            self.logger.error("Failed to create file chunk", error=str(e))
            raise

    async def get_file_chunks(self, file_id: int) -> List[FileChunk]:
        """Get all chunks for a file."""
        try:
            with self._get_session() as session:
                result = (
                    session.query(FileChunk)
                    .filter(FileChunk.file_id == file_id)
                    .order_by(FileChunk.chunk_index)
                    .all()
                )
                return result
        except Exception as e:
            self.logger.error(
                "Failed to get file chunks", file_id=file_id, error=str(e)
            )
            raise

    async def get_chunk_by_id(self, chunk_id: int) -> Optional[FileChunk]:
        """Get chunk by ID."""
        try:
            with self._get_session() as session:
                result = (
                    session.query(FileChunk).filter(FileChunk.id == chunk_id).first()
                )
                return result
        except Exception as e:
            self.logger.error(
                "Failed to get chunk by ID", chunk_id=chunk_id, error=str(e)
            )
            raise

    async def update_file_chunk(
        self, chunk_id: int, chunk_data: dict
    ) -> Optional[FileChunk]:
        """Update file chunk information."""
        try:
            with self._get_session() as session:
                chunk = (
                    session.query(FileChunk).filter(FileChunk.id == chunk_id).first()
                )
                if not chunk:
                    return None

                # Update fields
                if "content" in chunk_data:
                    chunk.content = chunk_data["content"]
                if "embedding_id" in chunk_data:
                    chunk.embedding_id = chunk_data["embedding_id"]
                if "token_count" in chunk_data:
                    chunk.token_count = chunk_data["token_count"]

                chunk.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(chunk)

                self.logger.info("File chunk updated successfully", chunk_id=chunk_id)
                return chunk
        except Exception as e:
            self.logger.error(
                "Failed to update file chunk", chunk_id=chunk_id, error=str(e)
            )
            raise

    async def delete_file_chunk(self, chunk_id: int) -> bool:
        """Delete a file chunk."""
        try:
            with self._get_session() as session:
                session.execute(delete(FileChunk).where(FileChunk.id == chunk_id))
                session.commit()

                self.logger.info("File chunk deleted successfully", chunk_id=chunk_id)
                return True
        except Exception as e:
            self.logger.error(
                "Failed to delete file chunk", chunk_id=chunk_id, error=str(e)
            )
            raise

    async def delete_file_chunks(self, file_id: int) -> bool:
        """Delete all chunks for a file."""
        try:
            with self._get_session() as session:
                session.execute(delete(FileChunk).where(FileChunk.file_id == file_id))
                session.commit()

                self.logger.info("File chunks deleted successfully", file_id=file_id)
                return True
        except Exception as e:
            self.logger.error(
                "Failed to delete file chunks", file_id=file_id, error=str(e)
            )
            raise
