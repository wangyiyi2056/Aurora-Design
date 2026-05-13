import axios from "axios"

async function getBaseURL(): Promise<string> {
  if (typeof window !== "undefined" && window.electronAPI) {
    const backendUrl = await window.electronAPI.getBackendUrl()
    return backendUrl
  }
  return "/api"
}

const apiClient = axios.create({
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
})

// Dynamically set baseURL for Electron
let baseURLInitialized = false
apiClient.interceptors.request.use(async (config) => {
  if (!baseURLInitialized) {
    config.baseURL = await getBaseURL()
    baseURLInitialized = true
  } else if (!config.baseURL) {
    config.baseURL = await getBaseURL()
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error?.response?.data?.detail || error?.message || "Unknown error"
    return Promise.reject(new Error(message))
  }
)

export { apiClient }
