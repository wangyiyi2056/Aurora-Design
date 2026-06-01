import { Routes, Route } from "react-router-dom"
import { Shell } from "@/components/layout/shell"
import LoginPage from "@/features/auth/pages/login-page"
import ExplorePage from "@/features/chat/pages/explore-page"
import ChatPage from "@/features/chat/pages/chat-page"
import SharePage from "@/features/chat/pages/share-page"
import AppListPage from "@/features/construct/app/pages/app-list-page"
import DatabaseListPage from "@/features/construct/database/pages/database-list-page"
import KnowledgeListPage from "@/features/construct/knowledge/pages/knowledge-list-page"
import KnowledgeDetailPage from "@/features/construct/knowledge/pages/knowledge-detail-page"
import FlowPage from "@/features/construct/flow/pages/flow-page"
import PluginsPage from "@/features/construct/plugins/pages/plugins-page"
import PromptPage from "@/features/construct/prompt/pages/prompt-page"
import SkillsPage from "@/features/construct/skills/pages/skills-page"
import DesignSystemsPage from "@/features/construct/design-systems/pages/design-systems-page"
import ModelsPage from "@/features/construct/models/pages/models-page"
import EvaluationListPage from "@/features/evaluation/pages/evaluation-list-page"

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="*"
        element={
          <Shell>
            <Routes>
              <Route path="/" element={<ExplorePage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/share/:id" element={<SharePage />} />
              <Route path="/construct/app" element={<AppListPage />} />
              <Route path="/construct/database" element={<DatabaseListPage />} />
              <Route path="/construct/knowledge" element={<KnowledgeListPage />} />
              <Route path="/construct/knowledge/:name" element={<KnowledgeDetailPage />} />
              <Route path="/construct/flow" element={<FlowPage />} />
              <Route path="/construct/plugins" element={<PluginsPage />} />
              <Route path="/construct/prompt" element={<PromptPage />} />
              <Route path="/construct/skills" element={<SkillsPage />} />
              <Route path="/construct/design-systems" element={<DesignSystemsPage />} />
              <Route path="/construct/models" element={<ModelsPage />} />
              <Route path="/models_evaluation" element={<EvaluationListPage />} />
            </Routes>
          </Shell>
        }
      />
    </Routes>
  )
}
