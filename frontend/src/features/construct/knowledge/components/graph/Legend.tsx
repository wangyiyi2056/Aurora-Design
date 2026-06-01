// @ts-nocheck
import React from 'react'
import { useTranslation } from 'react-i18next'
import { useGraphStore } from '@/features/construct/knowledge/stores/graph'
import { Card } from '@/components/ui/card'

interface LegendProps {
  className?: string
}

const Legend: React.FC<LegendProps> = ({ className }) => {
  const { t } = useTranslation()
  const typeColorMap = useGraphStore.use.typeColorMap()

  if (!typeColorMap || typeColorMap.size === 0) {
    return null
  }

  return (
    <Card className={`absolute bottom-4 left-4 z-50 flex flex-col pointer-events-auto ${className}`}>
      <div className="flex-1 overflow-y-auto w-32 p-1">
        <h3 className="text-sm font-medium mb-2">{t('graphPanel.legend')}</h3>
        <div className="flex flex-col gap-1">
          {Array.from(typeColorMap.entries()).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-xs truncate" title={type}>
                {t(`graphPanel.nodeTypes.${type.toLowerCase().replace(/\s+/g, '')}`, type)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

export default Legend
