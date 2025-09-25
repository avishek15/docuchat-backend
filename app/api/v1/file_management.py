"""File management API endpoints."""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from datetime import datetime, timezone
import structlog
import uuid
import hashlib

from app.models import (
    FileUploadRequest,
    FileUploadResponse,
    FileListResponse,
    ErrorResponse,
)
from app.models.files import (
    FileCreate,
    FileUpdate,
    FileInfo,
    FileCountResponse,
    FileDeleteResponse,
)
from app.core.auth import get_current_user
from app.services.external_apis.pinecone_service import PineconeService
from app.services.database.files import FileDatabaseService
from app.utils.text_processing import create_text_chunker

logger = structlog.get_logger()
router = APIRouter()

# Initialize services
pinecone_service = PineconeService()
file_db_service = FileDatabaseService()
text_chunker = create_text_chunker()


@router.get(
    "/files",
    response_model=FileListResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_files(current_user: dict = Depends(get_current_user)):
    """Get list of uploaded files for the current user."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session",
            )

        # Get files from database
        db_files = await file_db_service.get_user_files(user_id)

        # Convert to response format
        files = []
        for db_file in db_files:
            files.append(
                FileInfo(
                    file_id=db_file.file_id,
                    file_name=db_file.file_name,
                    file_size=db_file.file_size,
                    file_type=db_file.file_type,
                    uploaded_at=db_file.created_at.isoformat() + "Z",
                    status=db_file.status,
                )
            )

        return FileListResponse(status="success", files=files, total_count=len(files))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve files",
            error=str(e),
            user_id=current_user.get("user_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve files",
        )


@router.get(
    "/files/count",
    response_model=FileCountResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_file_count(current_user: dict = Depends(get_current_user)):
    """Get the current file count for the user (for upload limit checking)."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session",
            )

        # Get current file count
        file_count = await file_db_service.get_user_file_count(user_id)

        return FileCountResponse(
            status="success",
            count=file_count,
            limit=5,  # Current upload limit
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get file count",
            error=str(e),
            user_id=current_user.get("user_id"),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file count",
        )


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def upload_file(
    request: Request,
    file_data: FileUploadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Upload a file with text contents."""
    user_id = current_user.get("user_id")
    user_email = current_user.get("email")
    file_id = None

    try:
        # Validate user session
        if not user_id or not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session",
            )

        # Check file upload limit (5 files per user)
        user_file_count = await file_db_service.get_user_file_count(user_id)
        if user_file_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum file upload limit reached (5 files per user)",
            )

        # Validate file size (max 2MB)
        max_size = 2 * 1024 * 1024  # 2MB in bytes
        if file_data.file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size of {max_size} bytes",
            )

        # Validate file name
        if not file_data.file_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name cannot be empty",
            )

        # Validate contents
        if not file_data.contents.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contents cannot be empty",
            )

        # Generate unique file ID and content hash
        file_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(file_data.contents.encode()).hexdigest()

        # Create file record in database (status: processing)
        file_create_data = FileCreate(
            file_id=file_id,
            user_id=user_id,
            file_name=file_data.file_name,
            file_size=file_data.file_size,
            file_type=file_data.file_type or "text/plain",
            content_hash=content_hash,
            storage_path=None,  # Content stored in Pinecone
        )

        db_file = await file_db_service.create_file(file_create_data)

        # Update status to processing
        await file_db_service.update_file(db_file.id, FileUpdate(status="processing"))

        # Chunk the text content
        chunks = text_chunker.chunk_text(
            text=file_data.contents,
            filename=file_data.file_name,
            document_type=file_data.file_type or "text",
        )

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process file content - no chunks generated",
            )

        # Store chunks in Pinecone with database file ID
        pinecone_result = await pinecone_service.store_chunks(
            user_email=user_email,
            filename=file_data.file_name,
            chunks_batch=chunks,
            db_file_id=db_file.id,
        )

        # Update file status to ready and set processed timestamp
        processed_at = datetime.now(timezone.utc)
        await file_db_service.update_file(
            db_file.id, FileUpdate(status="ready", processed_at=processed_at)
        )

        logger.info(
            "File uploaded and processed successfully",
            file_id=file_id,
            file_name=file_data.file_name,
            file_size=file_data.file_size,
            user_id=user_id,
            user_email=user_email,
            chunks_stored=pinecone_result.get("stored_chunks", 0),
        )

        return FileUploadResponse(
            status="success",
            message="File uploaded and processed successfully",
            file_id=file_id,
            file_name=file_data.file_name,
            file_size=file_data.file_size,
            processed_at=processed_at.isoformat() + "Z",
        )

    except HTTPException:
        # Handle partial failures - cleanup if file was created
        if file_id:
            try:
                # Update file status to error
                db_file = await file_db_service.get_file_by_file_id(file_id)
                if db_file:
                    await file_db_service.update_file(
                        db_file.id, FileUpdate(status="error")
                    )
            except Exception as cleanup_error:
                logger.error(
                    "Failed to update file status during error cleanup",
                    file_id=file_id,
                    cleanup_error=str(cleanup_error),
                )
        raise
    except Exception as e:
        # Handle unexpected errors
        if file_id:
            try:
                # Update file status to error and cleanup Pinecone if needed
                db_file = await file_db_service.get_file_by_file_id(file_id)
                if db_file:
                    await file_db_service.update_file(
                        db_file.id, FileUpdate(status="error")
                    )

                # Cleanup Pinecone data if it was stored
                if user_email and db_file:
                    await pinecone_service.delete_file_by_db_id(
                        user_email=user_email,
                        db_file_id=db_file.id,
                        filename=file_data.file_name,  # Fallback for cleanup
                    )

            except Exception as cleanup_error:
                logger.error(
                    "Failed to cleanup during error handling",
                    file_id=file_id,
                    cleanup_error=str(cleanup_error),
                )

        logger.error(
            "Failed to upload file",
            error=str(e),
            file_name=file_data.file_name,
            user_id=user_id,
            file_id=file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process file upload",
        )


@router.delete(
    "/files/{file_id}",
    response_model=FileDeleteResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a file and all its chunks from both Pinecone and database."""
    user_id = current_user.get("user_id")
    user_email = current_user.get("email")

    try:
        # Validate user session
        if not user_id or not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session",
            )

        # Get file from database to verify ownership and get filename
        db_file = await file_db_service.get_file_by_file_id(file_id)
        if not db_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        # Verify file belongs to current user
        if db_file.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,  # Don't reveal file exists
                detail="File not found",
            )

        # Delete from Pinecone first (using database file ID, with filename fallback)
        pinecone_result = await pinecone_service.delete_file_by_db_id(
            user_email=user_email,
            db_file_id=db_file.id,
            filename=db_file.file_name,  # Fallback for legacy data
        )

        # Delete from database
        await file_db_service.delete_file(db_file.id)

        logger.info(
            "File deleted successfully",
            file_id=file_id,
            file_name=db_file.file_name,
            user_id=user_id,
            user_email=user_email,
            pinecone_chunks_deleted=pinecone_result.get("deleted_chunks", 0),
        )

        return FileDeleteResponse(
            status="success",
            message="File and all associated data deleted successfully",
            file_id=file_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete file",
            error=str(e),
            file_id=file_id,
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        )
