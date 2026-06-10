# Knowledge Graph Enhancement Plan

## Current State Analysis

The project already has a substantial knowledge feature at `frontend/src/features/construct/knowledge/`:
- **GraphViewer**: Sigma.js + graphology with force-directed layout, drag, search, zoom, fullscreen, properties, legend
- **DocumentManager**: Full CRUD, upload, pagination, status filter, pipeline monitoring
- **QueryPanel**: Chat-style with 6 modes, streaming, references, COT, advanced settings
- **KnowledgeSettings**: Config panel for knowledge base
- **Graph subcomponents**: GraphControl, GraphSearch, GraphLabels, LayoutsControl, PropertiesView, etc.
- **Stores**: graph.ts (Zustand), settings.ts, state.ts
- **Services**: knowledge-v2.ts with full API coverage

## Enhancement Roadmap

### Phase 1: Graph Exploration (Priority: HIGH) ✅
- [x] 1.1 Add N-hop expansion UI (1-hop, 2-hop buttons on selected node)
- [x] 1.2 Implement shortest path finding between two nodes (BFS algorithm)
- [x] 1.3 Add subgraph filter by entity type and relation type
- [x] 1.4 Node importance visualization (already implemented via degree-based sizing)

### Phase 2: Query Enhancements (Priority: HIGH) ✅
- [x] 2.1 Add query history panel with localStorage persistence
- [x] 2.2 Implement citation source highlighting in response text
- [x] 2.3 Add clear history and re-query from history

### Phase 3: Document Preview (Priority: MEDIUM) ✅
- [x] 3.1 Add document preview slide-over with Markdown rendering
- [x] 3.2 Add document metadata bar (status, date, size, chunks)

### Phase 4: E2E Tests (Priority: HIGH) ✅
- [x] 4.1 Knowledge list page tests (6 tests)
- [x] 4.2 Knowledge detail page navigation tests (4 tests)
- [x] 4.3 Graph viewer interaction tests (4 tests)
- [x] 4.4 Document management tests (5 tests)
- [x] 4.5 Query panel tests (9 tests)
- [x] 4.6 Responsive design tests (3 tests)
- [x] 4.7 Navigation tests (2 tests)

## File Changes

### New Files Created
| File | Purpose | Lines |
|------|---------|-------|
| `hooks/useQueryHistory.ts` | Query history hook with localStorage persistence | ~80 |
| `hooks/usePathFinder.ts` | BFS shortest path algorithm hook | ~110 |
| `components/graph/NodeExpansionControl.tsx` | N-hop expansion buttons for selected node | ~100 |
| `components/graph/PathFinder.tsx` | Shortest path finding UI with path highlighting | ~200 |
| `components/graph/SubgraphFilter.tsx` | Entity/relation type filter with checkbox list | ~210 |
| `components/QueryHistory.tsx` | Query history sidebar panel | ~170 |
| `components/DocumentPreview.tsx` | Document preview slide-over with Markdown | ~170 |
| `e2e/knowledge.spec.ts` | Comprehensive E2E tests (33 tests) | ~350 |

### Modified Files
| File | Changes |
|------|---------|
| `components/GraphViewer.tsx` | Added NodeExpansionControl, PathFinder, SubgraphFilter to control panel |
| `components/QueryPanel.tsx` | Added history sidebar, citation highlighting, HighlightedContent component |
| `components/DocumentManager.tsx` | Added preview button in table, DocumentPreview slide-over integration |
| `pages/knowledge-detail-page.tsx` | Added Query tab to tab navigation |

## Verification

- TypeScript: 0 errors (clean compilation)
- Vite build: Succeeds
- Unit tests: All 22 pre-existing test files pass (63 tests)
- E2E tests: 33 new test cases covering all 4 core areas
