export interface ElectronAPI {
  getBackendUrl: () => Promise<string>
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}
