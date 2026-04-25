import { apiClient } from "@/lib/api-client"

export interface ModelTestRequest {
  base_url: string
  api_key: string
  model_type: string
}

export interface ModelTestResponse {
  success: boolean
  message: string
  model_info?: Record<string, unknown>
}

export async function testModelConnection(
  baseUrl: string,
  apiKey: string,
  modelType?: string
): Promise<ModelTestResponse> {
  const response = await apiClient.post("/v1/models/test", {
    base_url: baseUrl,
    api_key: apiKey,
    model_type: modelType || "llm",
  })
  return response.data as ModelTestResponse
}
