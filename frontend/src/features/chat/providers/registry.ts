import { uploadFile } from "@/services/files"

export function projectRawUrl(path: string): string {
  return path
}

export async function uploadProjectFiles(files: File[]): Promise<
  Array<{ path: string; name: string; kind: "image" | "file"; size?: number }>
> {
  const uploaded = await Promise.all(
    files.map(async (file) => ({ source: file, uploaded: await uploadFile(file) }))
  )
  return uploaded.map(({ source, uploaded }) => ({
    path: uploaded.file_path,
    name: uploaded.file_name,
    kind: source.type.startsWith("image/") ? "image" : "file",
    size: source.size,
  }))
}
