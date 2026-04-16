import { apiClient } from "@/lib/api-client"

export async function uploadFile(file: File) {
  const form = new FormData()
  form.append("file", file)
  const res = await apiClient.post("/v1/files/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return res.data as { file_name: string; file_path: string }
}
