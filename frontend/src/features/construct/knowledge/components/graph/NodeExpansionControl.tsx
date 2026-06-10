import { useCallback } from "react"
import { useTranslation } from "react-i18next"
import { GitBranchPlus, GitBranch, Network } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useGraphStore } from "@/features/construct/knowledge/stores/graph"
import { controlButtonVariant } from "@/features/construct/knowledge/lib/constants"

/**
 * Node expansion control — allows expanding selected node by N hops.
 * Renders as a button group in the graph control panel.
 */
const NodeExpansionControl = () => {
  const { t } = useTranslation()
  const selectedNode = useGraphStore.use.selectedNode()
  const sigmaGraph = useGraphStore.use.sigmaGraph()
  const triggerNodeExpand = useGraphStore.use.triggerNodeExpand()

  const getNeighborCount = useCallback(
    (nodeId: string, hops: number): number => {
      if (!sigmaGraph || !sigmaGraph.hasNode(nodeId)) return 0
      const visited = new Set<string>([nodeId])
      let frontier = [nodeId]
      for (let i = 0; i < hops; i++) {
        const next: string[] = []
        for (const nid of frontier) {
          sigmaGraph.forEachNeighbor(nid, (neighbor: string) => {
            if (!visited.has(neighbor)) {
              visited.add(neighbor)
              next.push(neighbor)
            }
          })
        }
        frontier = next
      }
      return visited.size - 1 // Exclude the source node
    },
    [sigmaGraph],
  )

  const handleExpand = useCallback(
    (_hops: number) => {
      if (!selectedNode) return
      triggerNodeExpand(selectedNode)
    },
    [selectedNode, triggerNodeExpand],
  )

  if (!selectedNode) return null

  const oneHopCount = getNeighborCount(selectedNode, 1)
  const twoHopCount = getNeighborCount(selectedNode, 2)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="icon"
          variant={controlButtonVariant}
          title={t("graphPanel.expandNode", "Expand node neighbors")}
          className="h-8 w-8"
        >
          <GitBranchPlus className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="right"
        align="start"
        avoidCollisions
        collisionPadding={8}
        className="w-56 p-2"
      >
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground px-2 py-1">
            {t("graphPanel.expandTitle", "Expand neighbors")}
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => handleExpand(1)}
          >
            <GitBranch className="h-3.5 w-3.5" />
            <span>1-hop</span>
            <span className="ml-auto text-xs text-muted-foreground tabular-nums">
              {oneHopCount} nodes
            </span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => handleExpand(2)}
          >
            <Network className="h-3.5 w-3.5" />
            <span>2-hop</span>
            <span className="ml-auto text-xs text-muted-foreground tabular-nums">
              {twoHopCount} nodes
            </span>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}

export default NodeExpansionControl
