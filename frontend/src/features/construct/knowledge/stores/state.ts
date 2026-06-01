import { create } from 'zustand'
import { createSelectors } from '@/features/construct/knowledge/lib/utils'

interface BackendState {
  message: string;
  setErrorMessage: (msg: string) => void;
  pipelineBusy: boolean;
}

const useBackendStateBase = create<BackendState>((set) => ({
  message: '',
  setErrorMessage: (msg) => set({ message: msg }),
  pipelineBusy: false,
}))

export const useBackendState = createSelectors(useBackendStateBase)
