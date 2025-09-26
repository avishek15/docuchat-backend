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
    DeleteAllDataResponse,
)
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.services.external_apis.pinecone_service import PineconeService
from app.services.database.files import FileDatabaseService
from app.utils.text_processing import create_text_chunker

logger = structlog.get_logger()
router = APIRouter()

# Initialize services
pinecone_service = PineconeService()
file_db_service = FileDatabaseService()

# Get settings and create chunker with configured values
settings = get_settings()
text_chunker = create_text_chunker(
    chunk_size=settings.chunk_size,
    overlap_size=settings.chunk_overlap_size,
    min_chunk_size=settings.chunk_min_size,
)


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

    # Initial debug logging
    logger.info(
        "File upload started",
        user_id=user_id,
        user_email=user_email,
        file_name=file_data.file_name,
        file_size=file_data.file_size,
        file_type=file_data.file_type,
        content_length=len(file_data.contents) if file_data.contents else 0,
    )

    try:
        # Validate user session
        if not user_id or not user_email:
            logger.error("Invalid user session", user_id=user_id, user_email=user_email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session",
            )

        # Check file upload limit (5 files per user)
        user_file_count = await file_db_service.get_user_file_count(user_id)
        logger.debug(
            "User file count check",
            user_id=user_id,
            current_count=user_file_count,
            limit=5,
        )

        if user_file_count >= 5:
            logger.warning(
                "File upload limit reached",
                user_id=user_id,
                current_count=user_file_count,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum file upload limit reached (5 files per user)",
            )

        # Validate file size (max 2MB)
        max_size = 2 * 1024 * 1024  # 2MB in bytes
        if file_data.file_size > max_size:
            logger.warning(
                "File size exceeds limit",
                file_name=file_data.file_name,
                file_size=file_data.file_size,
                max_size=max_size,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed size of {max_size} bytes",
            )

        # Validate file name
        if not file_data.file_name.strip():
            logger.error("Empty file name provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name cannot be empty",
            )

        # Enhanced content validation with debugging
        if not file_data.contents:
            logger.error("No file contents provided", file_name=file_data.file_name)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contents cannot be empty",
            )

        if not file_data.contents.strip():
            logger.error(
                "File contents are only whitespace",
                file_name=file_data.file_name,
                content_length=len(file_data.contents),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contents cannot be empty",
            )

        # Debug content characteristics
        content_stats = {
            "total_length": len(file_data.contents),
            "stripped_length": len(file_data.contents.strip()),
            "line_count": len(file_data.contents.splitlines()),
            "word_count": len(file_data.contents.split()),
            "has_unicode": any(ord(c) > 127 for c in file_data.contents),
            "encoding_issues": False,
        }

        # Check for potential encoding issues
        try:
            file_data.contents.encode("utf-8")
        except UnicodeEncodeError as e:
            content_stats["encoding_issues"] = True
            logger.error(
                "Content encoding issues detected",
                file_name=file_data.file_name,
                encoding_error=str(e),
                **content_stats,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contains invalid characters that cannot be processed",
            )

        # Log content preview for debugging
        content_preview = (
            file_data.contents[:500] + "..."
            if len(file_data.contents) > 500
            else file_data.contents
        )
        logger.info(
            "File content validation passed",
            file_name=file_data.file_name,
            content_preview=content_preview,
            **content_stats,
        )

        # Generate unique file ID and content hash
        file_id = str(uuid.uuid4())
        logger.debug(
            "Generated file ID", file_id=file_id, file_name=file_data.file_name
        )

        try:
            content_hash = hashlib.sha256(file_data.contents.encode()).hexdigest()
            logger.debug(
                "Generated content hash",
                file_id=file_id,
                content_hash=content_hash[:16] + "...",
            )
        except Exception as e:
            logger.error(
                "Failed to generate content hash", file_id=file_id, error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process file content - invalid encoding",
            )

        # Create file record in database (status: processing)
        try:
            file_create_data = FileCreate(
                file_id=file_id,
                user_id=user_id,
                file_name=file_data.file_name,
                file_size=file_data.file_size,
                file_type=file_data.file_type or "text/plain",
                content_hash=content_hash,
                storage_path=None,  # Content stored in Pinecone
            )

            logger.debug("Creating file record in database", file_id=file_id)
            db_file = await file_db_service.create_file(file_create_data)
            logger.info("File record created", file_id=file_id, db_file_id=db_file.id)

        except Exception as e:
            logger.error(
                "Failed to create file record",
                file_id=file_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create file record in database",
            )

        # Update status to processing
        try:
            logger.debug(
                "Updating file status to processing",
                file_id=file_id,
                db_file_id=db_file.id,
            )
            await file_db_service.update_file(
                db_file.id, FileUpdate(status="processing")
            )
            logger.info("File status updated to processing", file_id=file_id)
        except Exception as e:
            logger.error(
                "Failed to update file status",
                file_id=file_id,
                db_file_id=db_file.id,
                error=str(e),
            )
            # Continue processing - this is not critical

        # Chunk the text content with enhanced debugging
        logger.info(
            "Starting text chunking",
            file_id=file_id,
            content_length=len(file_data.contents),
        )

        try:
            chunks = text_chunker.chunk_text(
                text=file_data.contents,
                filename=file_data.file_name,
                document_type=file_data.file_type or "text",
            )

            logger.info(
                "Text chunking completed",
                file_id=file_id,
                chunks_generated=len(chunks) if chunks else 0,
                avg_chunk_size=sum(len(c.get("text", "")) for c in chunks)
                // max(1, len(chunks))
                if chunks
                else 0,
            )

        except Exception as e:
            logger.error(
                "Text chunking failed",
                file_id=file_id,
                error=str(e),
                error_type=type(e).__name__,
                content_preview=file_data.contents[:200] + "..."
                if len(file_data.contents) > 200
                else file_data.contents,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process file content during chunking: {str(e)}",
            )

        if not chunks:
            logger.error(
                "No chunks generated from content",
                file_id=file_id,
                content_length=len(file_data.contents),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process file content - no chunks generated",
            )

        # Store chunks in Pinecone with database file ID
        logger.info(
            "Starting Pinecone storage",
            file_id=file_id,
            chunks_count=len(chunks),
            user_email=user_email[:10] + "..." if len(user_email) > 10 else user_email,
        )

        try:
            pinecone_result = await pinecone_service.store_chunks(
                user_email=user_email,
                filename=file_data.file_name,
                chunks_batch=chunks,
                db_file_id=db_file.id,
            )

            stored_chunks = pinecone_result.get("stored_chunks", 0)
            logger.info(
                "Pinecone storage completed",
                file_id=file_id,
                chunks_sent=len(chunks),
                chunks_stored=stored_chunks,
                pinecone_result_keys=list(pinecone_result.keys())
                if isinstance(pinecone_result, dict)
                else "not_dict",
            )

            if stored_chunks == 0:
                logger.warning("No chunks were stored in Pinecone", file_id=file_id)

        except Exception as e:
            logger.error(
                "Pinecone storage failed",
                file_id=file_id,
                error=str(e),
                error_type=type(e).__name__,
                chunks_count=len(chunks),
                user_email_hash=hashlib.sha256(user_email.encode()).hexdigest()[:16],
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store file content in vector database: {str(e)}",
            )

        # Update file status to ready and set processed timestamp
        try:
            processed_at = datetime.now(timezone.utc)
            logger.debug(
                "Updating file status to ready", file_id=file_id, db_file_id=db_file.id
            )

            await file_db_service.update_file(
                db_file.id, FileUpdate(status="ready", processed_at=processed_at)
            )

            logger.info(
                "File status updated to ready",
                file_id=file_id,
                processed_at=processed_at.isoformat(),
            )

        except Exception as e:
            logger.error(
                "Failed to update file status to ready",
                file_id=file_id,
                db_file_id=db_file.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            # This is critical - if we can't mark as ready, the file is stuck in processing
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to finalize file processing status",
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

    except HTTPException as he:
        # Handle partial failures - cleanup if file was created
        logger.warning(
            "HTTPException during file upload",
            file_id=file_id,
            status_code=he.status_code,
            detail=he.detail,
            user_id=user_id,
            file_name=file_data.file_name,
        )

        if file_id:
            try:
                logger.info("Starting cleanup for failed upload", file_id=file_id)
                # Update file status to error
                db_file = await file_db_service.get_file_by_file_id(file_id)
                if db_file:
                    await file_db_service.update_file(
                        db_file.id, FileUpdate(status="error")
                    )
                    logger.info(
                        "File status updated to error during cleanup", file_id=file_id
                    )
                else:
                    logger.warning(
                        "Could not find db_file for cleanup", file_id=file_id
                    )
            except Exception as cleanup_error:
                logger.error(
                    "Failed to update file status during error cleanup",
                    file_id=file_id,
                    cleanup_error=str(cleanup_error),
                    cleanup_error_type=type(cleanup_error).__name__,
                )
        raise

    except Exception as e:
        # Handle unexpected errors with comprehensive logging
        logger.error(
            "Unexpected exception during file upload",
            error=str(e),
            error_type=type(e).__name__,
            file_name=file_data.file_name,
            user_id=user_id,
            file_id=file_id,
            user_email_hash=hashlib.sha256(user_email.encode()).hexdigest()[:16]
            if user_email
            else None,
            content_length=len(file_data.contents)
            if hasattr(file_data, "contents") and file_data.contents
            else 0,
        )

        if file_id:
            try:
                logger.info(
                    "Starting comprehensive cleanup for unexpected error",
                    file_id=file_id,
                )

                # Update file status to error and cleanup Pinecone if needed
                db_file = await file_db_service.get_file_by_file_id(file_id)
                if db_file:
                    logger.debug(
                        "Updating file status to error",
                        file_id=file_id,
                        db_file_id=db_file.id,
                    )
                    await file_db_service.update_file(
                        db_file.id, FileUpdate(status="error")
                    )

                    # Cleanup Pinecone data if it was stored
                    if user_email:
                        logger.debug("Attempting Pinecone cleanup", file_id=file_id)
                        try:
                            await pinecone_service.delete_file_by_db_id(
                                user_email=user_email,
                                db_file_id=db_file.id,
                                filename=file_data.file_name,  # Fallback for cleanup
                            )
                            logger.info("Pinecone cleanup completed", file_id=file_id)
                        except Exception as pinecone_cleanup_error:
                            logger.error(
                                "Pinecone cleanup failed",
                                file_id=file_id,
                                pinecone_error=str(pinecone_cleanup_error),
                            )
                else:
                    logger.warning(
                        "Could not find db_file for comprehensive cleanup",
                        file_id=file_id,
                    )

            except Exception as cleanup_error:
                logger.error(
                    "Failed to cleanup during error handling",
                    file_id=file_id,
                    cleanup_error=str(cleanup_error),
                    cleanup_error_type=type(cleanup_error).__name__,
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file upload: {str(e)}",
        )


@router.delete(
    "/files/all",
    response_model=DeleteAllDataResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def delete_all_user_data(
    current_user: dict = Depends(get_current_user),
):
    """Delete all user data from both Pinecone and database."""
    user_id = current_user.get("user_id")
    user_email = current_user.get("email")

    try:
        # Validate user session
        if not user_id or not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user session",
            )

        logger.info(
            "Starting complete user data deletion",
            user_id=user_id,
            user_email=user_email,
        )

        # Step 1: Delete all vectors from Pinecone namespace
        pinecone_result = await pinecone_service.delete_user_namespace(user_email)
        pinecone_vectors_deleted = pinecone_result.get("deleted_vectors", 0)

        # Step 2: Delete all files from database
        database_files_deleted = await file_db_service.delete_all_user_files(user_id)

        logger.info(
            "Complete user data deletion successful",
            user_id=user_id,
            user_email=user_email,
            pinecone_vectors_deleted=pinecone_vectors_deleted,
            database_files_deleted=database_files_deleted,
        )

        return DeleteAllDataResponse(
            status="success",
            message="All user data deleted successfully",
            user_id=user_id,
            pinecone_vectors_deleted=pinecone_vectors_deleted,
            database_files_deleted=database_files_deleted,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete all user data",
            error=str(e),
            user_id=user_id,
            user_email=user_email,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete all user data",
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
