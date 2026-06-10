import { useCallback, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Route, X, Loader2, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useGraphStore } from "@/features/construct/knowledge/stores/graph"
import { usePathFinder } from "@/features/construct/knowledge/hooks/usePathFinder"
import { controlButtonVariant } from "@/features/construct/knowledge/lib/constants"
import { cn } from "@/lib/utils"

/**
 * Path finder control — find shortest path between two nodes.
 * Allows setting source/target from selected node, then highlights the path.
 */
const PathFinder = () => {
  const { t } = useTranslation()
  const selectedNode = useGraphStore.use.selectedNode()
  const sigmaGraph = useGraphStore.use.sigmaGraph()
  const setSelectedNode = useGraphStore.use.setSelectedNode()

  const {
    sourceNode,
    setSourceNode,
    targetNode,
    setTargetNode,
    result,
    isSearching,
    error,
    findPath,
    clearPath,
  } = usePathFinder()

  // Get node label for display
  const getNodeLabel = useCallback(
    (nodeId: string | null): string => {
      if (!nodeId || !sigmaGraph || !sigmaGraph.hasNode(nodeId)) return nodeId || ""
      return sigmaGraph.getNodeAttribute(nodeId, "label") || nodeId
    },
    [sigmaGraph],
  )

  // Highlight path on graph when result changes
  useEffect(() => {
    if (!sigmaGraph || !result) return

    // Clear previous highlights
    sigmaGraph.forEachNode((node: string) => {
      sigmaGraph.removeNodeAttribute(node, "pathHighlighted")
    })
    sigmaGraph.forEachEdge((edge: string) => {
      sigmaGraph.removeEdgeAttribute(edge, "pathHighlighted")
    })

    // Apply new highlights
    for (const nodeId of result.nodes) {
      if (sigmaGraph.hasNode(nodeId)) {
        sigmaGraph.setNodeAttribute(nodeId, "pathHighlighted", true)
      }
    }
    for (const edgeId of result.edges) {
      if (sigmaGraph.hasEdge(edgeId)) {
        sigmaGraph.setEdgeAttribute(edgeId, "pathHighlighted", true)
      }
    }

    return () => {
      if (!sigmaGraph) return
      sigmaGraph.forEachNode((node: string) => {
        sigmaGraph.removeNodeAttribute(node, "pathHighlighted")
      })
      sigmaGraph.forEachEdge((edge: string) => {
        sigmaGraph.removeEdgeAttribute(edge, "pathHighlighted")
      })
    }
  }, [sigmaGraph, result])

  const handleSetSource = useCallback(() => {
    if (selectedNode) setSourceNode(selectedNode)
  }, [selectedNode, setSourceNode])

  const handleSetTarget = useCallback(() => {
    if (selectedNode) setTargetNode(selectedNode)
  }, [selectedNode, setTargetNode])

  const handleFindPath = useCallback(() => {
    if (sourceNode && targetNode) {
      findPath(sigmaGraph, sourceNode, targetNode)
    }
  }, [sourceNode, targetNode, sigmaGraph, findPath])

  const handleClear = useCallback(() => {
    clearPath()
  }, [clearPath])

  const handleNavigateToNode = useCallback(
    (nodeId: string) => {
      setSelectedNode(nodeId, true)
    },
    [setSelectedNode],
  )

  const canFindPath = Boolean(sourceNode && targetNode && sourceNode !== targetNode)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="icon"
          variant={controlButtonVariant}
          title={t("graphPanel.pathFinder", "Find shortest path")}
          className={cn(
            "h-8 w-8",
            result && "text-primary",
          )}
        >
          <Route className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="right"
        align="start"
        avoidCollisions
        collisionPadding={8}
        className="w-72 max-h-[80vh] overflow-y-auto p-3"
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">
              {t("graphPanel.pathFinder", "Shortest Path")}
            </p>
            {(sourceNode || targetNode || result) && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={handleClear}
              >
                <X className="h-3 w-3" />
              </Button>
            )}
          </div>

          {/* Source node */}
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Source</label>
            <div className="flex items-center gap-2">
              <div className="flex-1 truncate rounded border bg-muted/50 px-2 py-1 text-xs">
                {sourceNode ? getNodeLabel(sourceNode) : "—"}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="shrink-0 text-xs h-7"
                disabled={!selectedNode}
                onClick={handleSetSource}
              >
                Use selected
              </Button>
            </div>
          </div>

          {/* Target node */}
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Target</label>
            <div className="flex items-center gap-2">
              <div className="flex-1 truncate rounded border bg-muted/50 px-2 py-1 text-xs">
                {targetNode ? getNodeLabel(targetNode) : "—"}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="shrink-0 text-xs h-7"
                disabled={!selectedNode}
                onClick={handleSetTarget}
              >
                Use selected
              </Button>
            </div>
          </div>

          {/* Find button */}
          <Button
            size="sm"
            className="w-full"
            disabled={!canFindPath || isSearching}
            onClick={handleFindPath}
          >
            {isSearching ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Route className="mr-1.5 h-3.5 w-3.5" />
            )}
            {t("graphPanel.findPath", "Find Path")}
          </Button>

          {/* Error */}
          {error && (
            <p className="text-xs text-destructive">{error}</p>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-2 rounded border bg-muted/30 p-2">
              <p className="text-xs font-medium">
                Path found: {result.distance} step{result.distance !== 1 ? "s" : ""}
              </p>
              <div className="space-y-0.5">
                {result.nodes.map((nodeId, i) => (
                  <div key={nodeId} className="flex items-center gap-1">
                    {i > 0 && (
                      <ArrowRight className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                    )}
                    <button
                      className="truncate text-left text-xs text-primary hover:underline"
                      onClick={() => handleNavigateToNode(nodeId)}
                    >
                      {getNodeLabel(nodeId)}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Hint */}
          {!sourceNode && !targetNode && (
            <p className="text-[10px] text-muted-foreground">
              Select a node in the graph, then click "Use selected" to set source and target.
            </p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export default PathFinder
