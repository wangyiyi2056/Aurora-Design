import { Routes, Route } from "react-router-dom"
import { Shell } from "@/components/layout/shell"
import ExplorePage from "@/features/chat/pages/explore-page"
import ChatPage from "@/features/chat/pages/chat-page"
import SharePage from "@/features/chat/pages/share-page"
import AppListPage from "@/features/construct/app/pages/app-list-page"
import DatabaseListPage from "@/features/construct/database/pages/database-list-page"
import KnowledgePage from "@/features/construct/knowledge/pages/knowledge-page"
import SkillsPage from "@/features/construct/skills/pages/skills-page"
import ModelsPage from "@/features/construct/models/pages/models-page"
import EvaluationListPage from "@/features/evaluation/pages/evaluation-list-page"
import MobileChatPage from "@/features/mobile/pages/mobile-chat-page"

export default function App() {
  return (
    <Routes>
      <Route path="/mobile/chat" element={<MobileChatPage />} />
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
              <Route path="/construct/knowledge" element={<KnowledgePage />} />
              <Route path="/construct/skills" element={<SkillsPage />} />
              <Route path="/construct/models" element={<ModelsPage />} />
              <Route path="/models_evaluation" element={<EvaluationListPage />} />
            </Routes>
          </Shell>
        }
      />
    </Routes>
  )
}
