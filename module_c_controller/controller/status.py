from __future__ import annotations


SERVICE_GRADED = "graded"
SERVICE_REJECTED = "rejected"
LOCAL_APPROVED = "approved"
LOCAL_REJECTED = "rejected"
PENDING = "pending"


def service_to_local_status(status: str) -> str:
    if status == SERVICE_GRADED:
        return LOCAL_APPROVED
    return status


def local_to_service_status(status: str) -> str:
    if status == LOCAL_APPROVED:
        return SERVICE_GRADED
    return status


def is_reviewed_status(status: str) -> bool:
    return status in {LOCAL_APPROVED, LOCAL_REJECTED, SERVICE_GRADED, SERVICE_REJECTED}
