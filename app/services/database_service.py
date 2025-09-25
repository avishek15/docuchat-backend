"""Legacy database service - compatibility layer for backward compatibility."""

import warnings
from typing import Optional, List
from app.models.auth import User, UserSession, UserCreate, UserUpdate, SessionCreate
from app.models.files import File, FileChunk, FileCreate, FileUpdate, ChunkCreate
from .database.auth import AuthDatabaseService
from .database.files import FileDatabaseService

# Global instances
_auth_db_service: Optional[AuthDatabaseService] = None
_file_db_service: Optional[FileDatabaseService] = None


class DatabaseService:
    """Legacy database service for backward compatibility."""

    def __init__(self):
        global _auth_db_service, _file_db_service

        if _auth_db_service is None:
            _auth_db_service = AuthDatabaseService()
        if _file_db_service is None:
            _file_db_service = FileDatabaseService()

        self.auth_service = _auth_db_service
        self.file_service = _file_db_service

        # Show deprecation warning
        warnings.warn(
            "DatabaseService is deprecated. Use AuthDatabaseService and FileDatabaseService directly.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Auth operations (delegated to AuthDatabaseService)
    async def get_user_by_email(self, email: str) -> Optional[User]:
        return await self.auth_service.get_user_by_email(email)

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        return await self.auth_service.get_user_by_id(user_id)

    async def create_user(self, user_data: UserCreate) -> User:
        return await self.auth_service.create_user(user_data)

    async def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        return await self.auth_service.update_user(user_id, user_data)

    async def update_user_last_accessed(self, user_id: int, ip_address: str) -> bool:
        return await self.auth_service.update_user_last_accessed(user_id, ip_address)

    async def create_session(self, session_data: SessionCreate) -> UserSession:
        return await self.auth_service.create_session(session_data)

    async def get_session_by_token(self, token: str) -> Optional[UserSession]:
        return await self.auth_service.get_session_by_token(token)

    async def invalidate_session(self, session_id: int) -> bool:
        return await self.auth_service.invalidate_session(session_id)

    async def invalidate_user_sessions(self, user_id: int) -> bool:
        return await self.auth_service.invalidate_user_sessions(user_id)

    async def cleanup_expired_sessions(self) -> int:
        return await self.auth_service.cleanup_expired_sessions()

    # File operations (delegated to FileDatabaseService)
    async def create_file(self, file_data: FileCreate) -> Optional[File]:
        return await self.file_service.create_file(file_data)

    async def get_file_by_id(self, file_id: int) -> Optional[File]:
        return await self.file_service.get_file_by_id(file_id)

    async def update_file(self, file_id: int, file_data: FileUpdate) -> Optional[File]:
        return await self.file_service.update_file(file_id, file_data)

    async def delete_file(self, file_id: int) -> bool:
        return await self.file_service.delete_file(file_id)

    async def get_user_files(self, user_id: int) -> List[File]:
        return await self.file_service.get_user_files(user_id)

    # File chunk operations (delegated to FileDatabaseService)
    async def create_file_chunk(self, chunk_data: ChunkCreate) -> Optional[FileChunk]:
        return await self.file_service.create_file_chunk(chunk_data)

    async def get_file_chunks(self, file_id: int) -> List[FileChunk]:
        return await self.file_service.get_file_chunks(file_id)

    async def update_file_chunk(
        self, chunk_id: int, chunk_data: dict
    ) -> Optional[FileChunk]:
        return await self.file_service.update_file_chunk(chunk_id, chunk_data)

    async def delete_file_chunk(self, chunk_id: int) -> bool:
        return await self.file_service.delete_file_chunk(chunk_id)


# Global database service instance (for backward compatibility)
_database_service: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """Get or create the global database service instance (deprecated)."""
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service
