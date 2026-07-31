import uuid
import logging
import os
from pathlib import Path

from app.database.supabase import supabase

logger = logging.getLogger(__name__)


class StorageService:

    @staticmethod
    def upload_video(file):
        """
        Upload a video to Supabase Storage 'videos' bucket.
        Args:
            file: FastAPI UploadFile object
        Returns:
            dict with filename and full storage path
        """
        try:
            extension = file.filename.split(".")[-1]
            filename = f"{uuid.uuid4()}.{extension}"

            # Ensure file pointer is at start
            try:
                file.file.seek(0)
            except Exception:
                pass

            file_bytes = file.file.read()

            # Upload to 'videos' bucket using positional args
            res = supabase.storage.from_("videos").upload(
                filename,
                file_bytes,
                {"content-type": file.content_type}
            )

            logger.info(f"Video uploaded successfully: {filename}")
            return {
                "filename": filename,
                "video_path": f"videos/{filename}",
                "full_path": f"videos/{filename}"
            }

        except Exception as e:
            logger.exception(f"Video upload failed: {str(e)}")
            raise RuntimeError(f"Failed to upload video: {str(e)}")

    @staticmethod
    def upload_evidence(evidence_file_path: str, evidence_bucket: str = "evidence"):
        """
        Upload evidence image file to Supabase Storage 'evidence' bucket.
        Args:
            evidence_file_path: Local file path to evidence image
            evidence_bucket: Target bucket name (default: 'evidence')
        Returns:
            dict with filename and storage path, or None if file doesn't exist
        """
        try:
            if not os.path.exists(evidence_file_path):
                logger.warning(f"Evidence file not found: {evidence_file_path}")
                return None

            # Generate unique filename preserving extension
            original_name = Path(evidence_file_path).name
            extension = original_name.split(".")[-1]
            filename = f"{uuid.uuid4()}.{extension}"

            # Read file bytes
            with open(evidence_file_path, 'rb') as f:
                file_bytes = f.read()

            # Determine content type
            content_type = "image/jpeg"
            if extension.lower() in ['png']:
                content_type = "image/png"
            elif extension.lower() in ['gif']:
                content_type = "image/gif"
            elif extension.lower() in ['webp']:
                content_type = "image/webp"

            # Upload to 'evidence' bucket
            res = supabase.storage.from_(evidence_bucket).upload(
                filename,
                file_bytes,
                {"content-type": content_type}
            )

            logger.info(f"Evidence uploaded successfully: {filename}")
            return {
                "filename": filename,
                "evidence_path": f"{evidence_bucket}/{filename}",
                "full_path": f"{evidence_bucket}/{filename}"
            }

        except Exception as e:
            logger.exception(f"Evidence upload failed for {evidence_file_path}: {str(e)}")
            # Return None instead of raising so one failed evidence doesn't break the whole flow
            return None

    @staticmethod
    def upload_evidence_batch(evidence_file_paths: list, evidence_bucket: str = "evidence"):
        """
        Upload multiple evidence files to Supabase Storage.
        Args:
            evidence_file_paths: List of local file paths
            evidence_bucket: Target bucket name
        Returns:
            list of dicts with filename and storage path (excludes failed uploads)
        """
        uploaded_evidence = []
        for path in evidence_file_paths:
            result = StorageService.upload_evidence(path, evidence_bucket)
            if result:
                uploaded_evidence.append(result)
        return uploaded_evidence

    @staticmethod
    def get_public_url(file_path: str, bucket: str = "videos"):
        """
        Generate a public URL for a file in Supabase Storage.
        Args:
            file_path: Path to file (e.g., 'filename.mp4' or 'videos/filename.mp4')
            bucket: Bucket name
        Returns:
            Public URL string
        """
        try:
            # Remove bucket prefix if included
            if file_path.startswith(f"{bucket}/"):
                file_path = file_path[len(bucket) + 1:]

            url = supabase.storage.from_(bucket).get_public_url(file_path)
            return url
        except Exception as e:
            logger.exception(f"Failed to generate public URL for {file_path}: {str(e)}")
            return None