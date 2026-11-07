"""Pure scheduling engine used by the n8n-facing API."""

from .service import optimize_schedule

__all__ = ["optimize_schedule"]
