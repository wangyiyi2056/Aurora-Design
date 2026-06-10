import { useCallback, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { Filter, X, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Input } from "@/components/ui/input"
import { useGraphStore } from "@/features/construct/knowledge/stores/graph"
import { controlButtonVariant } from "@/features/construct/knowledge/lib/constants"
import { cn } from "@/lib/utils"

/**
 * Subgraph filter control — filter visible nodes by entity type and relation type.
 * Operates on the sigma graph directly by toggling node/edge visibility.
 */
const SubgraphFilter = () => {
  const { t } = useTranslation()
  const sigmaGraph = useGraphStore.use.sigmaGraph()
  const rawGraph = useGraphStore.use.rawGraph()
  const [activeTab, setActiveTab] = useState<"entity" | "relation">("entity")
  const [searchTerm, setSearchTerm] = useState("")

  // Extract unique entity types from raw graph
  const entityTypes = useMemo(() => {
    if (!rawGraph) return []
    const types = new Set<string>()
    for (const node of rawGraph.nodes) {
      const entityType = node.properties.entity_type as string | undefined
      if (entityType) types.add(entityType)
    }
    return Array.from(types).sort()
  }, [rawGraph])

  // Extract unique relation types from raw graph
  const relationTypes = useMemo(() => {
    if (!rawGraph) return []
    const types = new Set<string>()
    for (const edge of rawGraph.edges) {
      const keywords = edge.properties.keywords as string | undefined
      if (keywords) {
        // Keywords may be comma-separated
        keywords.split(",").map((k) => k.trim()).filter(Boolean).forEach((k) => types.add(k))
      }
    }
    return Array.from(types).sort()
  }, [rawGraph])

  // Track which types are visible (default: all visible)
  const [hiddenEntityTypes, setHiddenEntityTypes] = useState<Set<string>>(new Set())
  const [hiddenRelationTypes, setHiddenRelationTypes] = useState<Set<string>>(new Set())

  const toggleEntityType = useCallback(
    (type: string) => {
      setHiddenEntityTypes((prev) => {
        const next = new Set(prev)
        if (next.has(type)) {
          next.delete(type)
        } else {
          next.add(type)
        }
        return next
      })
    },
    [],
  )

  const toggleRelationType = useCallback(
    (type: string) => {
      setHiddenRelationTypes((prev) => {
        const next = new Set(prev)
        if (next.has(type)) {
          next.delete(type)
        } else {
          next.add(type)
        }
        return next
      })
    },
    [],
  )

  // Apply filters to sigma graph
  const applyFilters = useCallback(() => {
    if (!sigmaGraph || !rawGraph) return

    // Show/hide nodes based on entity type
    for (const node of rawGraph.nodes) {
      const entityType = (node.properties.entity_type as string) || ""
      const shouldHide = hiddenEntityTypes.has(entityType)
      if (sigmaGraph.hasNode(node.id)) {
        sigmaGraph.setNodeAttribute(node.id, "hidden", shouldHide)
      }
    }

    // Show/hide edges based on relation type
    for (const edge of rawGraph.edges) {
      const keywords = (edge.properties.keywords as string) || ""
      const keywordList = keywords.split(",").map((k) => k.trim()).filter(Boolean)
      const shouldHide = keywordList.some((k) => hiddenRelationTypes.has(k))
      if (sigmaGraph.hasEdge(edge.dynamicId)) {
        sigmaGraph.setEdgeAttribute(edge.dynamicId, "hidden", shouldHide)
      }
    }
  }, [sigmaGraph, rawGraph, hiddenEntityTypes, hiddenRelationTypes])

  // Apply when filters change
  useMemo(() => {
    applyFilters()
  }, [applyFilters])

  const resetFilters = useCallback(() => {
    setHiddenEntityTypes(new Set())
    setHiddenRelationTypes(new Set())
    if (!sigmaGraph) return
    sigmaGraph.forEachNode((node: string) => {
      sigmaGraph.removeNodeAttribute(node, "hidden")
    })
    sigmaGraph.forEachEdge((edge: string) => {
      sigmaGraph.removeEdgeAttribute(edge, "hidden")
    })
  }, [sigmaGraph])

  const hasActiveFilters = hiddenEntityTypes.size > 0 || hiddenRelationTypes.size > 0

  const filteredEntityTypes = entityTypes.filter((type) =>
    type.toLowerCase().includes(searchTerm.toLowerCase()),
  )
  const filteredRelationTypes = relationTypes.filter((type) =>
    type.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  if (!rawGraph || rawGraph.nodes.length === 0) return null

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="icon"
          variant={controlButtonVariant}
          title={t("graphPanel.subgraphFilter", "Filter subgraph")}
          className={cn(
            "h-8 w-8",
            hasActiveFilters && "text-primary",
          )}
        >
          <Filter className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="right"
        align="start"
        avoidCollisions
        collisionPadding={8}
        className="w-64 max-h-[80vh] overflow-y-auto p-3"
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">
              {t("graphPanel.subgraphFilter", "Filter by Type")}
            </p>
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs"
                onClick={resetFilters}
              >
                Reset
              </Button>
            )}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 rounded bg-muted p-0.5">
            <button
              className={cn(
                "flex-1 rounded px-2 py-1 text-xs font-medium transition-colors",
                activeTab === "entity"
                  ? "bg-background shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => {
                setActiveTab("entity")
                setSearchTerm("")
              }}
            >
              Entity ({entityTypes.length})
            </button>
            <button
              className={cn(
                "flex-1 rounded px-2 py-1 text-xs font-medium transition-colors",
                activeTab === "relation"
                  ? "bg-background shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => {
                setActiveTab("relation")
                setSearchTerm("")
              }}
            >
              Relation ({relationTypes.length})
            </button>
          </div>

          {/* Search */}
          <div className="relative">
            <Input
              placeholder="Search types..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="h-7 text-xs pr-7"
            />
            {searchTerm && (
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-7 w-7"
                onClick={() => setSearchTerm("")}
              >
                <X className="h-3 w-3" />
              </Button>
            )}
          </div>

          {/* Type list */}
          <div className="max-h-48 space-y-0.5 overflow-y-auto">
            {activeTab === "entity"
              ? filteredEntityTypes.map((type) => {
                  const isHidden = hiddenEntityTypes.has(type)
                  return (
                    <button
                      key={type}
                      className={cn(
                        "flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs transition-colors hover:bg-muted",
                        isHidden && "opacity-50",
                      )}
                      onClick={() => toggleEntityType(type)}
                    >
                      <div
                        className={cn(
                          "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                          !isHidden && "bg-primary border-primary text-primary-foreground",
                        )}
                      >
                        {!isHidden && <Check className="h-3 w-3" />}
                      </div>
                      <span className="truncate">{type}</span>
                    </button>
                  )
                })
              : filteredRelationTypes.map((type) => {
                  const isHidden = hiddenRelationTypes.has(type)
                  return (
                    <button
                      key={type}
                      className={cn(
                        "flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs transition-colors hover:bg-muted",
                        isHidden && "opacity-50",
                      )}
                      onClick={() => toggleRelationType(type)}
                    >
                      <div
                        className={cn(
                          "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                          !isHidden && "bg-primary border-primary text-primary-foreground",
                        )}
                      >
                        {!isHidden && <Check className="h-3 w-3" />}
                      </div>
                      <span className="truncate">{type}</span>
                    </button>
                  )
                })}

            {activeTab === "entity" && filteredEntityTypes.length === 0 && (
              <p className="py-4 text-center text-xs text-muted-foreground">
                No entity types found
              </p>
            )}
            {activeTab === "relation" && filteredRelationTypes.length === 0 && (
              <p className="py-4 text-center text-xs text-muted-foreground">
                No relation types found
              </p>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

export default SubgraphFilter
