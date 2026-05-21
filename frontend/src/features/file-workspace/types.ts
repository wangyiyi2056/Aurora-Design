export type WorkspaceFileKind =
  | "html"
  | "image"
  | "video"
  | "audio"
  | "sketch"
  | "text"
  | "code"
  | "markdown"
  | "json"
  | "pdf"
  | "document"
  | "presentation"
  | "spreadsheet"
  | "binary"

export interface WorkspaceFile {
  name: string
  path?: string
  type?: "file" | "dir"
  size: number
  mtime: number
  kind: WorkspaceFileKind
  mime: string
}

export interface WorkspaceTabsState {
  tabs: string[]
  active: string | null
}

export interface WorkspaceUploadFailure {
  name: string
  code?: string
  error?: string
}

export interface WorkspaceUploadResult {
  files: WorkspaceFile[]
  failed: WorkspaceUploadFailure[]
  error?: string
}
