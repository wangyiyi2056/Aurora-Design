import { useCallback, useState } from "react"
import type { DirectedGraph } from "graphology"

export interface PathResult {
  nodes: string[]
  edges: string[]
  distance: number
}

/**
 * BFS shortest path on a graphology DirectedGraph.
 * Treats edges as undirected for path finding (knowledge graphs
 * typically have meaningful paths in both directions).
 */
function bfsShortestPath(
  graph: DirectedGraph,
  sourceId: string,
  targetId: string,
): PathResult | null {
  if (!graph.hasNode(sourceId) || !graph.hasNode(targetId)) return null
  if (sourceId === targetId) {
    return { nodes: [sourceId], edges: [], distance: 0 }
  }

  const visited = new Set<string>([sourceId])
  const parent = new Map<string, { node: string; edge: string }>()
  const queue: string[] = [sourceId]

  while (queue.length > 0) {
    const current = queue.shift()!

    // Explore neighbors in both directions (undirected traversal)
    const neighbors: Array<{ neighbor: string; edge: string }> = []

    graph.forEachOutEdge(current, (edge, _attrs, _src, tgt) => {
      neighbors.push({ neighbor: tgt, edge })
    })
    graph.forEachInEdge(current, (edge, _attrs, src, _tgt) => {
      neighbors.push({ neighbor: src, edge })
    })

    for (const { neighbor, edge } of neighbors) {
      if (visited.has(neighbor)) continue
      visited.add(neighbor)
      parent.set(neighbor, { node: current, edge })

      if (neighbor === targetId) {
        // Reconstruct path
        const nodes: string[] = [targetId]
        const edges: string[] = []
        let cur = targetId
        while (parent.has(cur)) {
          const { node: prev, edge: e } = parent.get(cur)!
          nodes.push(prev)
          edges.push(e)
          cur = prev
        }
        nodes.reverse()
        edges.reverse()
        return { nodes, edges, distance: edges.length }
      }

      queue.push(neighbor)
    }
  }

  return null // No path found
}

export function usePathFinder() {
  const [sourceNode, setSourceNode] = useState<string | null>(null)
  const [targetNode, setTargetNode] = useState<string | null>(null)
  const [result, setResult] = useState<PathResult | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const findPath = useCallback(
    (graph: DirectedGraph | null, source: string, target: string) => {
      if (!graph) {
        setError("Graph not loaded")
        return
      }
      setIsSearching(true)
      setError(null)
      setResult(null)

      // Use requestAnimationFrame to avoid blocking UI on large graphs
      requestAnimationFrame(() => {
        try {
          const path = bfsShortestPath(graph, source, target)
          if (path) {
            setResult(path)
          } else {
            setError("No path found between selected nodes")
          }
        } catch (e) {
          setError(
            e instanceof Error ? e.message : "Path finding failed",
          )
        } finally {
          setIsSearching(false)
        }
      })
    },
    [],
  )

  const clearPath = useCallback(() => {
    setSourceNode(null)
    setTargetNode(null)
    setResult(null)
    setError(null)
  }, [])

  return {
    sourceNode,
    setSourceNode,
    targetNode,
    setTargetNode,
    result,
    isSearching,
    error,
    findPath,
    clearPath,
  }
}
