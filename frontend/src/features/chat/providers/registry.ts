import { uploadWorkspaceFiles, workspaceRawUrl } from "@/features/file-workspace/services/workspace-files"

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
  projectId: string,
  files: File[]
): Promise<UploadProjectFilesResult> {
  const result = await uploadWorkspaceFiles(projectId, files)
  const uploaded: ChatAttachment[] = result.files.map((file) => ({
    path: file.name,
    name: file.name.split("/").filter(Boolean).at(-1) ?? file.name,
    kind: file.kind === "image" ? "image" : "file",
    url: workspaceRawUrl(projectId, file.name),
    size: file.size,
  }))

  return {
    uploaded,
    failed: result.failed,
    error: result.error,
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
