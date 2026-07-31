import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.services.storage_service import StorageService
from app.services.ai_service import AIService
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/upload",
    tags=["Upload"]
)


@router.post("/")
async def upload_video(file: UploadFile = File(...)):
    """
    Complete end-to-end workflow:
    1. Upload video to Supabase Storage (videos bucket)
    2. Send video to AI detection service
    3. Upload evidence images to Supabase Storage (evidence bucket)
    4. Save report and evidence URLs to PostgreSQL
    5. Return complete response with all data
    """
    video_storage_result = None
    ai_report = None
    evidence_urls = []

    try:
        logger.info(f"Starting upload workflow for file: {file.filename}")

        # ========== Step 1: Upload Video to Storage ==========
        try:
            logger.info("Step 1: Uploading video to Supabase Storage...")
            video_storage_result = StorageService.upload_video(file)
            logger.info(f"✓ Video uploaded: {video_storage_result['filename']}")
        except Exception as e:
            logger.exception("Step 1 failed: Video upload")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": "Failed to upload video",
                    "details": str(e),
                    "step": 1
                }
            )

        # ========== Step 2: Send Video to AI Service ==========
        try:
            logger.info("Step 2: Sending video to AI detection service...")
            ai_report = AIService.analyze_video(file)
            logger.info(f"✓ AI analysis complete, run_id: {ai_report.run_id}")
        except Exception as e:
            logger.exception("Step 2 failed: AI analysis")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": "AI analysis failed",
                    "details": str(e),
                    "step": 2,
                    "video_uploaded": video_storage_result is not None
                }
            )

        # ========== Step 3: Upload Evidence Images ==========
        try:
            if ai_report.evidence_frame_paths and len(ai_report.evidence_frame_paths) > 0:
                logger.info(f"Step 3: Uploading {len(ai_report.evidence_frame_paths)} evidence images...")
                
                # Upload all evidence files
                uploaded_evidence = StorageService.upload_evidence_batch(
                    ai_report.evidence_frame_paths,
                    evidence_bucket="evidence"
                )
                
                # Convert to URLs (or store paths as-is depending on your needs)
                evidence_urls = [
                    f"evidence/{ev['filename']}" for ev in uploaded_evidence
                ]
                
                logger.info(f"✓ Uploaded {len(evidence_urls)} evidence images")
            else:
                logger.warning("No evidence frames found in AI report")
        except Exception as e:
            # Don't fail entirely if evidence upload fails
            logger.warning(f"Step 3 warning: Evidence upload partial/failed: {str(e)}")
            # Continue anyway - evidence is supplementary

        # ========== Step 4: Save Report to Database ==========
        try:
            logger.info("Step 4: Saving report to PostgreSQL...")
            db_result = ReportService.save_report(
                report=ai_report,
                video_filename=video_storage_result['filename'],
                evidence_urls=evidence_urls
            )
            logger.info(f"✓ Report saved, report_id: {db_result['report_id']}")
        except Exception as e:
            logger.exception("Step 4 failed: Database save")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": "Failed to save report to database",
                    "details": str(e),
                    "step": 4,
                    "video_uploaded": video_storage_result is not None,
                    "ai_analysis_complete": ai_report is not None,
                    "evidence_uploaded": len(evidence_urls) > 0
                }
            )

        # ========== Step 5: Return Complete Response ==========
        logger.info(f"✓ Upload workflow complete for {file.filename}")

        return {
            "success": True,
            "message": "Video analysis complete and stored successfully",
            "data": {
                "video": {
                    "filename": video_storage_result['filename'],
                    "path": video_storage_result['video_path']
                },
                "ai_report": {
                    "run_id": ai_report.run_id,
                    "status": ai_report.status,
                    "severity_score": ai_report.severity_score,
                    "violations_detected": ai_report.violations_detected,
                    "number_plate": ai_report.number_plate or "Not detected",
                    "plate_read_confidence": ai_report.plate_read_confidence,
                    "rider_count": ai_report.rider_count,
                    "helmet_status": ai_report.helmet_status,
                    "notes": ai_report.notes
                },
                "evidence": {
                    "count": len(evidence_urls),
                    "image_paths": evidence_urls
                },
                "database": {
                    "report_id": db_result['report_id'],
                    "vehicle_id": db_result['vehicle_id']
                }
            }
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in upload workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Unexpected error during upload",
                "details": str(e)
            }
        )