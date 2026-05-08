export type ChatRole = "user" | "assistant" | "system"
export type ChatRunStatus = "queued" | "running" | "succeeded" | "failed" | "canceled"

export interface ChatAttachment {
  fileId?: string
  path: string
  name: string
  kind: "image" | "file"
  url?: string
  size?: number
}

export interface ChatCommentAttachment {
  id: string
  order: number
  filePath: string
  elementId: string
  selector: string
  label: string
  comment: string
  currentText: string
  pagePosition: PreviewCommentPosition
  htmlHint: string
  selectionKind?: PreviewCommentSelectionKind
  memberCount?: number
  podMembers?: PreviewCommentMember[]
  source?: "saved-comment" | "board-batch"
}

export type PersistedAgentEvent =
  | { kind: "status"; label: string; detail?: string }
  | { kind: "text"; text: string }
  | { kind: "thinking"; text: string }
  | { kind: "tool_use"; id: string; name: string; input: unknown }
  | { kind: "tool_result"; toolUseId: string; content: string; isError: boolean }
  | { kind: "usage"; inputTokens?: number; outputTokens?: number; costUsd?: number; durationMs?: number }
  | { kind: "raw"; line: string }
  | {
      kind: "live_artifact"
      action: "created" | "updated" | "deleted"
      projectId: string
      artifactId: string
      title: string
      refreshStatus?: string
    }
  | {
      kind: "live_artifact_refresh"
      phase: "started" | "succeeded" | "failed"
      projectId: string
      artifactId: string
      refreshId?: string
      title?: string
      refreshedSourceCount?: number
      error?: string
    }

export type AgentEvent = PersistedAgentEvent

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  agentId?: string
  agentName?: string
  events?: PersistedAgentEvent[]
  createdAt?: number
  runId?: string
  runStatus?: ChatRunStatus
  lastRunEventId?: string
  startedAt?: number
  endedAt?: number
  startTime?: number
  endTime?: number
  attachments?: ChatAttachment[]
  commentAttachments?: ChatCommentAttachment[]
  producedFiles?: ProjectFile[]
}

export interface Conversation {
  id: string
  title: string
  createdAt?: number
  updatedAt: number
}

export type ProjectFileKind = "html" | "image" | "sketch" | "code" | "file"

export interface ProjectFile {
  name: string
  path?: string
  type?: "file" | "directory"
  kind: ProjectFileKind
  size: number
}

export interface ProjectMetadata {
  kind?: "prototype" | string
  linkedDirs?: string[]
}

export interface PreviewCommentPosition {
  x: number
  y: number
  width: number
  height: number
}

export type PreviewCommentSelectionKind = "element" | "text" | "area" | "pod"

export interface PreviewCommentMember {
  id?: string
  elementId?: string
  label?: string
  selector?: string
  text?: string
  position: PreviewCommentPosition
  htmlHint?: string
}

export interface PreviewCommentTarget {
  filePath: string
  elementId: string
  selector: string
  label: string
  text: string
  htmlHint: string
  selectionKind?: PreviewCommentSelectionKind
  podMembers?: PreviewCommentMember[]
  memberCount?: number
  position: PreviewCommentPosition
}

export type PreviewCommentStatus = "open" | "resolved"

export interface PreviewComment {
  id: string
  filePath: string
  elementId: string
  selector: string
  label: string
  comment: string
  note: string
  text: string
  currentText?: string
  htmlHint: string
  position: PreviewCommentPosition
  status?: PreviewCommentStatus
  createdAt?: number
  updatedAt?: number
  selectionKind?: PreviewCommentSelectionKind
  podMembers?: PreviewCommentMember[]
  memberCount?: number
}

export interface PreviewCommentUpsertRequest extends Partial<PreviewComment> {
  comment: string
}

export interface PetAtlasRowDef {
  index: number
  id: string
  frames: number
  fps: number
}

export interface PetAtlasLayout {
  cols: number
  rows: number
  rowsDef: PetAtlasRowDef[]
}

export interface PetCustom {
  name: string
  glyph: string
  accent: string
  greeting: string
  imageUrl?: string
  frames?: number
  fps?: number
  atlas?: PetAtlasLayout
}

export interface PetConfig {
  adopted: boolean
  enabled: boolean
  petId: string
  custom: PetCustom
}

export interface AppConfig {
  pet: PetConfig
}

export interface CodexPetSummary {
  id: string
  name: string
  displayName?: string
  spritesheetUrl: string
  accent?: string
  greeting?: string
  atlas?: PetAtlasLayout
}

export interface CodexPetsResponse {
  pets: CodexPetSummary[]
  rootDir: string
}

export interface SkillSummary {
  id: string
  title?: string
  name?: string
  description: string
  examplePrompt?: string
}

export interface DesignSystemSummary {
  id: string
  title?: string
  name?: string
  summary?: string
  category?: string
}

export type MediaAspect = "1:1" | "4:3" | "16:9" | "9:16" | string

export interface PromptTemplateSummary {
  id: string
  surface: "image" | "video"
  title: string
  summary: string
  category: string
  tags?: string[]
  model?: string
  aspect?: MediaAspect
}

export type AudioKind = "music" | "voice" | "sfx"

export interface AgentInfo {
  id: string
  name: string
}

export interface AgentModelPrefs {
  model?: string
  reasoning?: string
}

export interface Project {
  id: string
  name: string
  metadata?: ProjectMetadata
}

export type ProjectKind = string
export type ProjectDisplayStatus = string
export type Surface = "web" | "image" | "video" | "audio"

export interface AppVersionInfo { version: string }
export interface AppVersionResponse { version: string }
export interface DeployConfigResponse { enabled?: boolean }
export interface DeployProjectFileResponse { url?: string }
export interface DesignSystemDetail extends DesignSystemSummary {}
export interface LiveArtifact { id: string }
export interface LiveArtifactDetailResponse { artifact?: LiveArtifact }
export interface LiveArtifactListResponse { artifacts: LiveArtifact[] }
export interface LiveArtifactRefreshLogEntry { id: string }
export type LiveArtifactRefreshStatus = string
export type LiveArtifactStatus = string
export interface LiveArtifactSummary { id: string }
export interface ProjectDeploymentsResponse { deployments: unknown[] }
export interface SyncCommunityPetsRequest { force?: boolean }
export interface SyncCommunityPetsResponse {
  wrote: number
  skipped: number
  failed: number
  total: number
  rootDir: string
  errors: string[]
}
export interface SkillDetail extends SkillSummary {}
export interface UpdateDeployConfigRequest { enabled?: boolean }
