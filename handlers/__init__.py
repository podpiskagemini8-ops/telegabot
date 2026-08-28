from .user import router as user_router
from .anonymous import router as anonymous_router
from .admin import router as admin_router

__all__ = ["user_router", "anonymous_router", "admin_router"]
