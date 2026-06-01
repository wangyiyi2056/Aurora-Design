import { useParams, useNavigate } from "react-router-dom"
import { ArrowLeft, FileText, Network, Settings } from "lucide-react"
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
import { ErrorBoundary } from "@/components/ErrorBoundary"

export default function KnowledgeDetailPage() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()

  const knowledgeName = name ? decodeURIComponent(name) : ""

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
            Back
          </Button>
          <h3 className="text-lg font-semibold truncate">{knowledgeName}</h3>
        </div>

        {/* Tabs — flex-1 to fill available height */}
        <Tabs defaultValue="documents" className="flex flex-col flex-1 min-h-0">
          <TabsList className="shrink-0">
            <TabsTrigger value="documents" className="gap-1.5">
              <FileText className="h-3.5 w-3.5" />
              Documents
            </TabsTrigger>
            <TabsTrigger value="graph" className="gap-1.5">
              <Network className="h-3.5 w-3.5" />
              Graph
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-1.5">
              <Settings className="h-3.5 w-3.5" />
              Settings
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
            className="mt-3 flex-1 min-h-0"
          >
            <ErrorBoundary>
              <GraphViewer knowledgeName={knowledgeName} />
            </ErrorBoundary>
          </TabsContent>

          <TabsContent
            value="settings"
            className="mt-3 flex-1 min-h-0 overflow-auto"
          >
            <KnowledgeSettings knowledgeName={knowledgeName} />
          </TabsContent>
        </Tabs>
      </div>
    </ConstructShell>
  )
}
