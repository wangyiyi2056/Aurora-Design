import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
// import { MiniMap } from '@react-sigma/minimap'
import { SigmaContainer, useRegisterEvents, useSigma } from '@react-sigma/core'
import { Settings as SigmaSettings } from 'sigma/settings'
import { GraphSearchOption, OptionItem } from '@react-sigma/graph-search'
import { EdgeArrowProgram, NodePointProgram, NodeCircleProgram } from 'sigma/rendering'
import { NodeBorderProgram } from '@sigma/node-border'
import { EdgeCurvedArrowProgram, createEdgeCurveProgram } from '@sigma/edge-curve'

import FocusOnNode from '@/features/construct/knowledge/components/graph/FocusOnNode'
import LayoutsControl from '@/features/construct/knowledge/components/graph/LayoutsControl'
import GraphControl from '@/features/construct/knowledge/components/graph/GraphControl'
// import ThemeToggle from '@/components/ThemeToggle'
import ZoomControl from '@/features/construct/knowledge/components/graph/ZoomControl'
import FullScreenControl from '@/features/construct/knowledge/components/graph/FullScreenControl'
import Settings from '@/features/construct/knowledge/components/graph/Settings'
import GraphSearch from '@/features/construct/knowledge/components/graph/GraphSearch'
import GraphLabels from '@/features/construct/knowledge/components/graph/GraphLabels'
import PropertiesView from '@/features/construct/knowledge/components/graph/PropertiesView'
import SettingsDisplay from '@/features/construct/knowledge/components/graph/SettingsDisplay'
import Legend from '@/features/construct/knowledge/components/graph/Legend'
import LegendButton from '@/features/construct/knowledge/components/graph/LegendButton'
import NodeExpansionControl from '@/features/construct/knowledge/components/graph/NodeExpansionControl'
import PathFinder from '@/features/construct/knowledge/components/graph/PathFinder'
import SubgraphFilter from '@/features/construct/knowledge/components/graph/SubgraphFilter'

import { useSettingsStore } from '@/features/construct/knowledge/stores/settings'
import { useGraphStore } from '@/features/construct/knowledge/stores/graph'
import { labelColorDarkTheme, labelColorLightTheme } from '@/features/construct/knowledge/lib/constants'

import '@react-sigma/core/lib/style.css'
import '@react-sigma/graph-search/lib/style.css'

// Function to create sigma settings based on theme
const createSigmaSettings = (isDarkTheme: boolean): Partial<SigmaSettings> => ({
  allowInvalidContainer: true,
  defaultNodeType: 'default',
  defaultEdgeType: 'curvedNoArrow',
  renderEdgeLabels: false,
  edgeProgramClasses: {
    arrow: EdgeArrowProgram,
    curvedArrow: EdgeCurvedArrowProgram,
    curvedNoArrow: createEdgeCurveProgram()
  },
  nodeProgramClasses: {
    default: NodeBorderProgram,
    circel: NodeCircleProgram,
    point: NodePointProgram
  },
  labelGridCellSize: 60,
  labelRenderedSizeThreshold: 12,
  enableEdgeEvents: true,
  labelColor: {
    color: isDarkTheme ? labelColorDarkTheme : labelColorLightTheme,
    attribute: 'labelColor'
  },
  edgeLabelColor: {
    color: isDarkTheme ? labelColorDarkTheme : labelColorLightTheme,
    attribute: 'labelColor'
  },
  edgeLabelSize: 8,
  labelSize: 12
  // minEdgeThickness: 2
  // labelFont: 'Lato, sans-serif'
})

import { useLightragGraph } from '@/features/construct/knowledge/hooks/useLightragGraph'

const GraphEvents = () => {
  const registerEvents = useRegisterEvents()
  const sigma = useSigma()
  const [draggedNode, setDraggedNode] = useState<string | null>(null)

  useEffect(() => {
    // Register the events
    registerEvents({
      downNode: (e) => {
        setDraggedNode(e.node)
        sigma.getGraph().setNodeAttribute(e.node, 'highlighted', true)
      },
      // On mouse move, if the drag mode is enabled, we change the position of the draggedNode
      mousemovebody: (e) => {
        if (!draggedNode) return
        // Get new position of node
        const pos = sigma.viewportToGraph(e)
        sigma.getGraph().setNodeAttribute(draggedNode, 'x', pos.x)
        sigma.getGraph().setNodeAttribute(draggedNode, 'y', pos.y)

        // Prevent sigma to move camera:
        e.preventSigmaDefault()
        e.original.preventDefault()
        e.original.stopPropagation()
      },
      // On mouse up, we reset the autoscale and the dragging mode
      mouseup: () => {
        if (draggedNode) {
          setDraggedNode(null)
          sigma.getGraph().removeNodeAttribute(draggedNode, 'highlighted')
        }
      },
      // Disable the autoscale at the first down interaction
      mousedown: (e) => {
        // Only set custom BBox if it's a drag operation (mouse button is pressed)
        const mouseEvent = e.original as MouseEvent;
        if (mouseEvent.buttons !== 0 && !sigma.getCustomBBox()) {
          sigma.setCustomBBox(sigma.getBBox())
        }
      }
    })
  }, [registerEvents, sigma, draggedNode])

  return null
}

const GraphViewer = ({ knowledgeName }: { knowledgeName: string }) => {
  const { t } = useTranslation()
  useLightragGraph(knowledgeName)
  const sigmaRef = useRef<any>(null)
  const prevTheme = useRef<string>('')

  const selectedNode = useGraphStore.use.selectedNode()
  const focusedNode = useGraphStore.use.focusedNode()
  const moveToSelectedNode = useGraphStore.use.moveToSelectedNode()
  const isFetching = useGraphStore.use.isFetching()
  const rawGraph = useGraphStore.use.rawGraph()

  const showPropertyPanel = useSettingsStore.use.showPropertyPanel()
  const showNodeSearchBar = useSettingsStore.use.showNodeSearchBar()
  const enableNodeDrag = useSettingsStore.use.enableNodeDrag()
  const showLegend = useSettingsStore.use.showLegend()
  const theme = useSettingsStore.use.theme()

  const [isThemeSwitching, setIsThemeSwitching] = useState(false)

  // Memoize sigma settings to prevent unnecessary re-creation
  const memoizedSigmaSettings = useMemo(() => {
    const isDarkTheme = theme === 'dark'
    return createSigmaSettings(isDarkTheme)
  }, [theme])

  // Detect theme changes and briefly show a loading overlay to avoid flash of
  // unstyled content. setState is inside setTimeout (async), not synchronously
  // in the effect body, so react-hooks/set-state-in-effect is not triggered.
  useEffect(() => {
    const isThemeChange = prevTheme.current && prevTheme.current !== theme
    if (isThemeChange) {
      console.log('Theme switching detected:', prevTheme.current, '->', theme)
      prevTheme.current = theme

      const switchTimer = setTimeout(() => setIsThemeSwitching(true), 0)
      const timer = setTimeout(() => {
        setIsThemeSwitching(false)
        console.log('Theme switching completed')
      }, 150)

      return () => {
        clearTimeout(switchTimer)
        clearTimeout(timer)
      }
    }
    prevTheme.current = theme
    console.log('Initialized sigma settings for theme:', theme)
  }, [theme])

  // Clean up sigma instance when component unmounts
  useEffect(() => {
    return () => {
      // TAB is mount twice in vite dev mode, this is a workaround

      const sigma = useGraphStore.getState().sigmaInstance;
      if (sigma) {
        try {
          // Destroy sigma，and clear WebGL context
          sigma.kill();
          useGraphStore.getState().setSigmaInstance(null);
          console.log('Cleared sigma instance on Graphviewer unmount');
        } catch (error) {
          console.error('Error cleaning up sigma instance:', error);
        }
      }
    };
  }, []);

  // Note: There was a useLayoutEffect hook here to set up the sigma instance and graph data,
  // but testing showed it wasn't executing or having any effect, while the backup mechanism
  // in GraphControl was sufficient. This code was removed to simplify implementation

  const onSearchFocus = useCallback((value: GraphSearchOption | null) => {
    if (value === null) useGraphStore.getState().setFocusedNode(null)
    else if (value.type === 'nodes') useGraphStore.getState().setFocusedNode(value.id)
  }, [])

  const onSearchSelect = useCallback((value: GraphSearchOption | null) => {
    if (value === null) {
      useGraphStore.getState().setSelectedNode(null)
    } else if (value.type === 'nodes') {
      useGraphStore.getState().setSelectedNode(value.id, true)
    }
  }, [])

  const autoFocusedNode = useMemo(() => focusedNode ?? selectedNode, [focusedNode, selectedNode])
  const searchInitSelectedNode = useMemo(
    (): OptionItem | null => (selectedNode ? { type: 'nodes', id: selectedNode } : null),
    [selectedNode]
  )

  const nodeCount = rawGraph?.nodes.length ?? 0
  const edgeCount = rawGraph?.edges.length ?? 0

  // Always render SigmaContainer but control its visibility with CSS
  return (
    <div className="relative h-full w-full overflow-hidden">
      <SigmaContainer
        settings={memoizedSigmaSettings}
        className="!bg-background !size-full overflow-hidden"
        ref={sigmaRef}
      >
        <GraphControl />

        {enableNodeDrag && <GraphEvents />}

        <FocusOnNode node={autoFocusedNode} move={moveToSelectedNode} />

        {/* Graph stats — bottom right */}
        {nodeCount > 0 && (
          <div className="absolute bottom-2 right-2 z-10 flex items-center gap-3 rounded-lg border bg-background/70 px-3 py-1.5 text-xs font-medium backdrop-blur-lg">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
              {nodeCount} {t('graphPanel.entities', '实体')}
            </span>
            <span className="text-muted-foreground">|</span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-orange-500" />
              {edgeCount} {t('graphPanel.edges', '边')}
            </span>
          </div>
        )}

        <div className="absolute top-2 left-2 flex items-start gap-2">
          <GraphLabels knowledgeName={knowledgeName} />
          {showNodeSearchBar && !isThemeSwitching && (
            <GraphSearch
              value={searchInitSelectedNode}
              onFocus={onSearchFocus}
              onChange={onSearchSelect}
            />
          )}
        </div>

        <div className="bg-background/60 absolute bottom-2 left-2 flex w-10 flex-col items-center rounded-xl border-2 backdrop-blur-lg [&>button]:h-10 [&>button]:w-10 [&>button]:p-0 [&_svg]:h-4 [&_svg]:w-4">
          <LayoutsControl />
          <ZoomControl />
          <FullScreenControl />
          <NodeExpansionControl />
          <PathFinder />
          <SubgraphFilter />
          <LegendButton />
          <Settings />
          {/* <ThemeToggle /> */}
        </div>

        {showPropertyPanel && (
          <div className="absolute top-2 right-2 z-10 max-w-[300px]">
            <PropertiesView />
          </div>
        )}

        {showLegend && (
          <div className="absolute bottom-10 right-2 z-10">
            <Legend className="bg-background/60 backdrop-blur-lg" />
          </div>
        )}

        {/* <div className="absolute bottom-2 right-2 flex flex-col rounded-xl border-2">
          <MiniMap width="100px" height="100px" />
        </div> */}

        <SettingsDisplay />
      </SigmaContainer>

      {/* Loading overlay - shown when data is loading or theme is switching */}
      {(isFetching || isThemeSwitching) && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
          <div className="text-center">
            <div className="mb-2 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto"></div>
            <p>{isThemeSwitching ? t('graphPanel.switchingTheme', 'Switching Theme...') : t('graphPanel.loadingGraphData', 'Loading Graph Data...')}</p>
          </div>
        </div>
      )}
    </div>
  )
}

export { GraphViewer }
