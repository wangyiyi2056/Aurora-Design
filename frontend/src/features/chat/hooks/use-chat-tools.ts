import { useRef, useState } from "react"
import { uploadFile } from "@/services/files"

export interface ChatAttachment {
  type: "file" | "skill" | "knowledge" | "database"
  name: string
  content?: string
}

export function useChatTools() {
  const [attachments, setAttachments] = useState<ChatAttachment[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const attachFile = () => {
    // Use requestAnimationFrame to escape any event-handling context
    // that could block the file picker (e.g. Radix dropdown close)
    requestAnimationFrame(() => {
      fileInputRef.current?.click()
    })
  }

  const handleFileSelect = async (file: File) => {
    if (file.type.startsWith("image/")) {
      const reader = new FileReader()
      reader.onload = () => {
        const dataUrl = String(reader.result || "")
        setAttachments((prev) => [
          ...prev.filter((a) => a.type !== "file"),
          { type: "file", name: file.name, content: dataUrl },
        ])
      }
      reader.readAsDataURL(file)
      return
    }

    try {
      const res = await uploadFile(file)
      setAttachments((prev) => [
        ...prev.filter((a) => a.type !== "file"),
        { type: "file", name: res.file_name, content: res.file_path },
      ])
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("Upload file failed", err)
    }
  }

  const setSkill = (name: string) => {
    setAttachments((prev) => [
      ...prev.filter((a) => a.type !== "skill"),
      { type: "skill", name },
    ])
  }

  const setKnowledge = (name: string) => {
    setAttachments((prev) => [
      ...prev.filter((a) => a.type !== "knowledge"),
      { type: "knowledge", name },
    ])
  }

  const setDatabase = (name: string) => {
    setAttachments((prev) => [
      ...prev.filter((a) => a.type !== "database"),
      { type: "database", name },
    ])
  }

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  const clearAttachments = () => {
    setAttachments([])
  }

  return {
    attachments,
    fileInputRef,
    attachFile,
    handleFileSelect,
    setSkill,
    setKnowledge,
    setDatabase,
    removeAttachment,
    clearAttachments,
  }
}
