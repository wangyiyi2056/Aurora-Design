import { useEffect, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, FileText, Network, Settings, MessageSquare } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import { DocumentManager } from "../components/DocumentManager"
import { GraphViewer } from "../components/GraphViewer"
import { KnowledgeSettings } from "../components/KnowledgeSettings"
import { QueryPanel } from "../components/QueryPanel"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { invalidateKnowledgeDetailV2Queries } from "../hooks/use-knowledge-v2"
import { useGraphStore } from "../stores/graph"
import { useSettingsStore } from "../stores/settings"

export default function KnowledgeDetailPage() {
  const { t } = useTranslation("construct")
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const knowledgeName = name ? decodeURIComponent(name) : ""

  useEffect(() => {
    if (!knowledgeName) return

    const graphState = useGraphStore.getState()
    useSettingsStore.getState().setQueryLabel("*")
    graphState.reset()
    graphState.setGraphDataFetchAttempted(false)
    graphState.setLabelsFetchAttempted(false)
    graphState.incrementGraphDataVersion()

    return () => {
      invalidateKnowledgeDetailV2Queries(qc, knowledgeName)

      const graphState = useGraphStore.getState()
      graphState.reset()
      graphState.setGraphDataFetchAttempted(false)
      graphState.setLabelsFetchAttempted(false)
      graphState.incrementGraphDataVersion()
    }
  }, [knowledgeName, qc])

  return (
    <ConstructShell>
      <div className="flex flex-col h-[calc(100vh-140px)]">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/construct/knowledge")}
            className="gap-1.5"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("knowledge.v2.detail.back")}
          </Button>
          <h3 className="text-lg font-semibold truncate">{knowledgeName}</h3>
        </div>

        {/* Tabs — flex-1 to fill available height */}
        <TabsWithMountedGraph knowledgeName={knowledgeName} />
      </div>
    </ConstructShell>
  )
}

function TabsWithMountedGraph({ knowledgeName }: { knowledgeName: string }) {
  const { t } = useTranslation("construct")
  const [activeTab, setActiveTab] = useState("documents")
  const [hasMountedGraph, setHasMountedGraph] = useState(false)

  const handleTabChange = (value: string) => {
    setActiveTab(value)
    if (value === "graph") {
      setHasMountedGraph(true)
    }
  }

  useEffect(() => {
    setActiveTab("documents")
    setHasMountedGraph(false)
  }, [knowledgeName])

  return (
    <Tabs value={activeTab} onValueChange={handleTabChange} className="flex flex-col flex-1 min-h-0">
          <TabsList className="shrink-0">
            <TabsTrigger value="documents" className="gap-1.5">
              <FileText className="h-3.5 w-3.5" />
              {t("knowledge.v2.detail.documents")}
            </TabsTrigger>
            <TabsTrigger value="graph" className="gap-1.5">
              <Network className="h-3.5 w-3.5" />
              {t("knowledge.v2.detail.graph")}
            </TabsTrigger>
            <TabsTrigger value="query" className="gap-1.5">
              <MessageSquare className="h-3.5 w-3.5" />
              {t("knowledge.v2.detail.query", "Query")}
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-1.5">
              <Settings className="h-3.5 w-3.5" />
              {t("knowledge.v2.detail.settings")}
            </TabsTrigger>
          </TabsList>

          <TabsContent
            value="documents"
            className="mt-3 flex-1 min-h-0 overflow-auto"
          >
            <DocumentManager knowledgeName={knowledgeName} />
          </TabsContent>

          <TabsContent
            value="graph"
            forceMount
            className="mt-3 flex-1 min-h-0 data-[state=inactive]:hidden"
          >
            {hasMountedGraph && knowledgeName && knowledgeName !== "undefined" && (
              <ErrorBoundary>
                <GraphViewer key={knowledgeName} knowledgeName={knowledgeName} />
              </ErrorBoundary>
            )}
          </TabsContent>

          <TabsContent
            value="query"
            className="mt-3 flex-1 min-h-0 overflow-hidden"
          >
            <ErrorBoundary>
              <QueryPanel knowledgeName={knowledgeName} />
            </ErrorBoundary>
          </TabsContent>

          <TabsContent
            value="settings"
            className="mt-3 flex-1 min-h-0 overflow-auto"
          >
            <KnowledgeSettings knowledgeName={knowledgeName} />
          </TabsContent>
    </Tabs>
  )
}
