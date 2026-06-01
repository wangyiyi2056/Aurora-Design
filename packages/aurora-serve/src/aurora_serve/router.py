from fastapi import APIRouter

from aurora_serve.apps.api import router as apps_router
from aurora_serve.auth.routes import router as auth_router
from aurora_serve.awel.api import router as awel_router
from aurora_serve.agent.api import router as agent_router
from aurora_serve.chat.api import router as chat_router
from aurora_serve.datasource.api import router as datasource_router
from aurora_serve.design_skills.api import router as design_skills_router
from aurora_serve.design_systems.api import router as design_systems_router
from aurora_serve.evaluation.api import router as evaluation_router
from aurora_serve.feedback.api import router as feedback_router
from aurora_serve.files.api import router as files_router
from aurora_serve.files.workspace_api import router as workspaces_router
from aurora_serve.health.api import router as health_router
from aurora_serve.knowledge.api import router as knowledge_router
from aurora_serve.knowledge.v2.document_routes import router as v2_document_router
from aurora_serve.knowledge.v2.query_routes import router as v2_query_router
from aurora_serve.knowledge.v2.graph_routes import router as v2_graph_router
from aurora_serve.models.api import router as models_router
from aurora_serve.prompt.api import router as prompt_router
from aurora_serve.plugins.api import router as plugins_router
from aurora_serve.providers.api import router as providers_router
from aurora_serve.skills.api import router as skills_router
from aurora_serve.traces.api import router as traces_router
from aurora_serve.users.api import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(apps_router)
api_router.include_router(awel_router)
api_router.include_router(chat_router)
api_router.include_router(datasource_router)
api_router.include_router(agent_router)
api_router.include_router(knowledge_router)
# V2 knowledge base routes — scoped per knowledge base name
api_router.include_router(
    v2_document_router, prefix="/knowledge/{name}"
)
api_router.include_router(
    v2_query_router, prefix="/knowledge/{name}"
)
api_router.include_router(
    v2_graph_router, prefix="/knowledge/{name}"
)
api_router.include_router(files_router)
api_router.include_router(workspaces_router)
api_router.include_router(skills_router)
api_router.include_router(design_skills_router)
api_router.include_router(design_systems_router)
api_router.include_router(models_router)
api_router.include_router(prompt_router)
api_router.include_router(plugins_router)
api_router.include_router(providers_router)
api_router.include_router(evaluation_router)
api_router.include_router(feedback_router)
api_router.include_router(traces_router)
api_router.include_router(users_router)
