"""File management database service for file and chunk operations."""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import delete
import structlog
from app.models.files import File, FileCreate, FileUpdate
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

                # Update fields (only fields that exist in FileUpdate model)
                if file_data.file_name is not None:
                    file.file_name = file_data.file_name
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
        """Delete a file record."""
        try:
            with self._get_session() as session:
                # Delete the file (chunks are stored in Pinecone)
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

    async def get_user_file_count(self, user_id: int) -> int:
        """Get the number of files for a user (for upload limits)."""
        try:
            with self._get_session() as session:
                count = session.query(File).filter(File.user_id == user_id).count()
                return count
        except Exception as e:
            self.logger.error(
                "Failed to get user file count", user_id=user_id, error=str(e)
            )
            raise

    # Note: File chunks are stored in Pinecone, not in database
