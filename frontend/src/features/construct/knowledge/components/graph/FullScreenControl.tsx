// @ts-nocheck
import { useFullScreen } from '@react-sigma/core'
import { MaximizeIcon, MinimizeIcon } from 'lucide-react'
import { controlButtonVariant } from '@/features/construct/knowledge/lib/constants'
import { Button } from '@/components/ui/button'
import { useTranslation } from 'react-i18next'

/**
 * Component that toggles full screen mode.
 */
const FullScreenControl = () => {
  const { isFullScreen, toggle } = useFullScreen()
  const { t } = useTranslation()

  return (
    <>
      {isFullScreen ? (
        <Button
          variant={controlButtonVariant}
          onClick={toggle}
          tooltip={t('graphPanel.sideBar.fullScreenControl.toggle')}
          size="icon"
        >
          <MinimizeIcon />
        </Button>
      ) : (
        <Button
          variant={controlButtonVariant}
          onClick={toggle}
          tooltip={t('graphPanel.sideBar.fullScreenControl.toggle')}
          size="icon"
        >
          <MaximizeIcon />
        </Button>
      )}
    </>
  )
}

export default FullScreenControl
