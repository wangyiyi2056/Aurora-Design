// @ts-nocheck
import { useCallback, useEffect, useState } from 'react'
import { AsyncSelect } from '@/components/ui/AsyncSelect'
import { useSettingsStore } from '@/features/construct/knowledge/stores/settings'
import { useGraphStore } from '@/features/construct/knowledge/stores/graph'
import {
  dropdownDisplayLimit,
  controlButtonVariant,
  searchLabelsDefaultLimit
} from '@/features/construct/knowledge/lib/constants'
import { useTranslation } from 'react-i18next'
import { RefreshCw, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchHistoryManager } from '@/features/construct/knowledge/utils/SearchHistoryManager'
import { searchLabels } from '@/services/knowledge-v2'
import { getGraphRefreshLabel, normalizeGraphQueryLabel, requestGraphLabelRefresh } from './graph-label-refresh'


const GraphLabels = ({ knowledgeName }: { knowledgeName: string }) => {
  const { t } = useTranslation()
  const label = useSettingsStore.use.queryLabel()
  const dropdownRefreshTrigger = useSettingsStore.use.searchLabelDropdownRefreshTrigger()
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [selectKey, setSelectKey] = useState(0)

  // Dynamic tooltip based on current label state
  const getRefreshTooltip = useCallback(() => {
    if (isRefreshing) {
      return t('graphPanel.graphLabels.refreshingTooltip')
    }

    if (!label || label === '*') {
      return t('graphPanel.graphLabels.refreshGlobalTooltip')
    } else {
      return t('graphPanel.graphLabels.refreshCurrentLabelTooltip', { label })
    }
  }, [label, t, isRefreshing])

  // Force AsyncSelect to re-render when label or dropdownRefreshTrigger changes.
  // Uses render-time previous-value comparison to avoid cascading renders from
  // setState-in-useEffect, while still bumping the key on external changes.
  const [previousLabel, setPreviousLabel] = useState(label)
  const [previousDropdownTrigger, setPreviousDropdownTrigger] = useState(dropdownRefreshTrigger)
  if (label !== previousLabel) {
    setPreviousLabel(label)
    setSelectKey(prev => prev + 1)
  }
  if (dropdownRefreshTrigger !== previousDropdownTrigger) {
    setPreviousDropdownTrigger(dropdownRefreshTrigger)
    if (dropdownRefreshTrigger > 0) {
      setSelectKey(prev => prev + 1)
    }
  }

  // No default labels — only show user's search history

  const fetchData = useCallback(
    async (query?: string): Promise<string[]> => {
      let results: string[];
      if (!query || query.trim() === '' || query.trim() === '*') {
        // Empty query: return search history
        results = SearchHistoryManager.getHistoryLabels(dropdownDisplayLimit)
      } else {
        // Non-empty query: call backend search API
        try {
          const apiResults = await searchLabels(knowledgeName, query.trim(), searchLabelsDefaultLimit)
          results = apiResults.length <= dropdownDisplayLimit
            ? apiResults
            : [...apiResults.slice(0, dropdownDisplayLimit), '...']
        } catch (error) {
          console.error('Search API failed, falling back to local history search:', error)

          // Fallback to local history search
          const history = SearchHistoryManager.getHistory()
          const queryLower = query.toLowerCase().trim()
          results = history
            .filter(item => item.label.toLowerCase().includes(queryLower))
            .map(item => item.label)
            .slice(0, dropdownDisplayLimit)
        }
      }
      // Always show '*' at the top, and remove duplicates
      const finalResults = ['*', ...results.filter(label => label !== '*')];
      return finalResults;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [refreshTrigger] // Intentionally added to trigger re-creation when data changes
  )

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true)

    // Clear legend cache to ensure legend is re-generated on refresh
    useGraphStore.getState().setTypeColorMap(new Map<string, string>())

    try {
      const currentLabel = requestGraphLabelRefresh(
        getGraphRefreshLabel(label, useGraphStore.getState().graphIsEmpty)
      )

      if (currentLabel === '*') {
        // Ensure data update completes before triggering UI refresh.
        await new Promise(resolve => setTimeout(resolve, 0))

        // Trigger both refresh mechanisms to ensure dropdown updates
        setRefreshTrigger(prev => prev + 1)
        setSelectKey(prev => prev + 1)
      }
    } catch (error) {
      console.error('Error during refresh:', error)
    } finally {
      setIsRefreshing(false)
    }
  }, [label])

  // Handle dropdown before open - no-op, history is user-driven
  const handleDropdownBeforeOpen = useCallback(async () => {
    // No automatic label loading — only user's search history is shown
  }, [])

  const handleDeleteHistoryLabel = useCallback((historyLabel: string) => {
    SearchHistoryManager.removeLabel(historyLabel)
    if (normalizeGraphQueryLabel(label) === historyLabel) {
      requestGraphLabelRefresh('*')
    }
    setRefreshTrigger(prev => prev + 1)
    setSelectKey(prev => prev + 1)
  }, [label])

  return (
    <div className="flex items-center">
      {/* Always show refresh button */}
      <Button
        size="icon"
        variant={controlButtonVariant}
        onClick={handleRefresh}
        
        className="mr-2"
        disabled={isRefreshing}
      >
        <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
      </Button>
      <div className="w-full min-w-[280px] max-w-[500px]">
        <AsyncSelect<string>
          key={selectKey} // Force re-render when data changes
          className="min-w-[300px]"
          triggerClassName="max-h-8 w-full overflow-hidden"
          searchInputClassName="max-h-8"
          triggerTooltip={t('graphPanel.graphLabels.selectTooltip')}
          fetcher={fetchData}
          onBeforeOpen={handleDropdownBeforeOpen}
          renderOption={(item) => {
            const canDelete = item !== '*' && item !== '...' && SearchHistoryManager.hasLabel(item)
            return (
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <div className="min-w-0 flex-1 truncate" title={item}>
                  {item}
                </div>
                {canDelete && (
                  <button
                    type="button"
                    aria-label={t('graphPanel.graphLabels.deleteHistoryLabel', { label: item })}
                    title={t('graphPanel.graphLabels.deleteHistoryLabel', { label: item })}
                    className="text-muted-foreground hover:text-destructive rounded p-0.5 opacity-70 transition-opacity hover:opacity-100"
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      handleDeleteHistoryLabel(item)
                    }}
                    onMouseDown={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                    }}
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            )
          }}
          getOptionValue={(item) => item}
          getDisplayValue={(item) => (
            <div className="min-w-0 flex-1 truncate text-left" title={item}>
              {item}
            </div>
          )}
          notFound={<div className="py-6 text-center text-sm">{t('graphPanel.graphLabels.noLabels')}</div>}
          ariaLabel={t('graphPanel.graphLabels.label')}
          placeholder={t('graphPanel.graphLabels.placeholder')}
          searchPlaceholder={t('graphPanel.graphLabels.placeholder')}
          noResultsMessage={t('graphPanel.graphLabels.noLabels')}
          value={label !== null ? label : '*'}
          onChange={(newLabel) => {
            const selectedLabel = normalizeGraphQueryLabel(newLabel);

            // Add selected label to search history (except for special cases)
            if (selectedLabel !== '*') {
              SearchHistoryManager.addToHistory(selectedLabel);
            }

            requestGraphLabelRefresh(selectedLabel);
          }}
          clearable={false}  // Prevent clearing value on reselect
          debounceTime={500}
        />
      </div>
    </div>
  )
}

export default GraphLabels
