from fastapi import APIRouter

from chatbi_serve.apps.api import router as apps_router
from chatbi_serve.agent.api import router as agent_router
from chatbi_serve.awel.api import router as awel_router
from chatbi_serve.chat.api import router as chat_router
from chatbi_serve.datasource.api import router as datasource_router
from chatbi_serve.files.api import router as files_router
from chatbi_serve.health.api import router as health_router
from chatbi_serve.knowledge.api import router as knowledge_router
from chatbi_serve.models.api import router as models_router
from chatbi_serve.skills.api import router as skills_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(apps_router)
api_router.include_router(chat_router)
api_router.include_router(datasource_router)
api_router.include_router(agent_router)
api_router.include_router(knowledge_router)
api_router.include_router(awel_router)
api_router.include_router(files_router)
api_router.include_router(skills_router)
api_router.include_router(models_router)
