export type ParsedSseFrame =
  | { kind: "event"; event: string; data: Record<string, unknown>; id?: string }
  | { kind: "comment"; comment: string }

export function parseSseFrame(frame: string): ParsedSseFrame | null {
  const lines = frame.split(/\r?\n/)
  let event = "message"
  let id: string | undefined
  const dataLines: string[] = []

  for (const line of lines) {
    if (!line) continue
    if (line.startsWith(":")) {
      return { kind: "comment", comment: line.slice(1).trim() }
    }
    const separator = line.indexOf(":")
    const field = separator >= 0 ? line.slice(0, separator) : line
    const value = separator >= 0 ? line.slice(separator + 1).trimStart() : ""
    if (field === "event") event = value
    if (field === "id") id = value
    if (field === "data") dataLines.push(value)
  }

  if (dataLines.length === 0) return null

  try {
    return {
      kind: "event",
      event,
      id,
      data: JSON.parse(dataLines.join("\n")) as Record<string, unknown>,
    }
  } catch {
    return {
      kind: "event",
      event,
      id,
      data: { text: dataLines.join("\n") },
    }
  }
}
