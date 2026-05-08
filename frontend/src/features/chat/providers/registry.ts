import { uploadFile } from "@/services/files"

import type {
  ChatAttachment,
  CodexPetSummary,
  CodexPetsResponse,
  ProjectFile,
  ProjectMetadata,
} from "../types"

export function projectRawUrl(projectIdOrPath: string, maybePath?: string): string {
  const rawPath = maybePath ?? projectIdOrPath
  if (
    rawPath.startsWith("/api/") ||
    rawPath.startsWith("http://") ||
    rawPath.startsWith("https://") ||
    rawPath.startsWith("data:") ||
    rawPath.startsWith("blob:")
  ) {
    return rawPath
  }
  return `/api/v1/files/raw?path=${encodeURIComponent(rawPath)}`
}

export function projectFileUrl(projectId: string, name: string): string {
  return projectRawUrl(projectId, name)
}

export interface UploadProjectFilesResult {
  uploaded: ChatAttachment[]
  failed: Array<{ name: string; code?: string; error?: string }>
  error?: string
}

export async function uploadProjectFiles(
  _projectId: string,
  files: File[]
): Promise<UploadProjectFilesResult> {
  const uploaded: ChatAttachment[] = []
  const failed: UploadProjectFilesResult["failed"] = []

  for (const file of files) {
    try {
      const result = await uploadFile(file)
      uploaded.push({
        fileId: result.file_id,
        path: result.file_path,
        name: result.file_name,
        kind: file.type.startsWith("image/") ? "image" : "file",
        url: projectRawUrl(result.file_path),
        size: file.size,
      })
    } catch (error) {
      failed.push({
        name: file.name,
        error: error instanceof Error ? error.message : "upload failed",
      })
    }
  }

  return {
    uploaded,
    failed,
    error: failed.length > 0 ? "upload failed" : undefined,
  }
}

export async function openFolderDialog(): Promise<string | null> {
  return null
}

export async function fetchCodexPets(): Promise<CodexPetsResponse> {
  return { pets: [], rootDir: "" }
}

export function codexPetSpritesheetUrl(pet: CodexPetSummary): string {
  return pet.spritesheetUrl
}

export function looksLikeImage(path: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg)$/i.test(path)
}

export function fileToProjectFile(file: ChatAttachment): ProjectFile {
  return {
    name: file.name,
    path: file.path,
    kind: file.kind,
    size: file.size ?? 0,
  }
}

export async function patchProjectMetadata(
  metadata: ProjectMetadata
): Promise<{ metadata: ProjectMetadata }> {
  return { metadata }
}
