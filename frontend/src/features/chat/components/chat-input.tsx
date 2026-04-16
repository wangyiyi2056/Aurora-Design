import {
  PaperClipOutlined,
  ThunderboltOutlined,
  BookOutlined,
  DatabaseOutlined,
  UpOutlined,
  CloseOutlined,
} from "@ant-design/icons"
import { Button, Input, Tag } from "antd"
import { useTranslation } from "react-i18next"

interface ChatAttachmentTag {
  type: "file" | "skill" | "knowledge" | "database"
  name: string
}

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  loading: boolean
  attachments?: ChatAttachmentTag[]
  onRemoveAttachment?: (index: number) => void
  onAttachFile?: () => void
  onUseSkill?: () => void
  onUseKnowledge?: () => void
  onUseDatabase?: () => void
}

export function ChatInput({
  value,
  onChange,
  onSend,
  loading,
  attachments,
  onRemoveAttachment,
  onAttachFile,
  onUseSkill,
  onUseKnowledge,
  onUseDatabase,
}: ChatInputProps) {
  const { t } = useTranslation("chat")

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="pt-4 pb-2">
      <div className="bg-surface border border-border rounded-3xl shadow-sm px-4 py-3">
        <Input.TextArea
          className="!bg-transparent !border-0 !shadow-none focus:!ring-0 resize-none text-base min-h-[24px] max-h-[200px] py-1"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("chat.placeholder")}
          disabled={loading}
          aria-label={t("chat.placeholder")}
          autoSize={{ minRows: 1, maxRows: 6 }}
        />
        {attachments && attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {attachments.map((att, idx) => (
              <Tag
                key={`${att.type}-${idx}`}
                closable
                onClose={() => onRemoveAttachment?.(idx)}
                className="text-xs"
                closeIcon={<CloseOutlined className="text-[10px] ml-1" />}
              >
                {att.type === "file" && (
                  <PaperClipOutlined className="mr-1 text-[10px]" />
                )}
                {att.type === "skill" && (
                  <ThunderboltOutlined className="mr-1 text-[10px]" />
                )}
                {att.type === "knowledge" && (
                  <BookOutlined className="mr-1 text-[10px]" />
                )}
                {att.type === "database" && (
                  <DatabaseOutlined className="mr-1 text-[10px]" />
                )}
                {att.name}
              </Tag>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1 flex-wrap">
            <Button
              type="text"
              size="small"
              icon={<PaperClipOutlined />}
              onClick={onAttachFile}
              className="!text-text-secondary hover:!text-text"
            >
              {t("chat.attachFile")}
            </Button>
            <Button
              type="text"
              size="small"
              icon={<ThunderboltOutlined />}
              onClick={onUseSkill}
              className="!text-text-secondary hover:!text-text"
            >
              {t("chat.useSkill")}
            </Button>
            <Button
              type="text"
              size="small"
              icon={<BookOutlined />}
              onClick={onUseKnowledge}
              className="!text-text-secondary hover:!text-text"
            >
              {t("chat.useKnowledge")}
            </Button>
            <Button
              type="text"
              size="small"
              icon={<DatabaseOutlined />}
              onClick={onUseDatabase}
              className="!text-text-secondary hover:!text-text"
            >
              {t("chat.useDatabase")}
            </Button>
          </div>
          <Button
            type="primary"
            shape="circle"
            icon={<UpOutlined />}
            onClick={onSend}
            loading={loading}
            disabled={!value.trim() || loading}
            aria-label={t("chat.send")}
          />
        </div>
      </div>
    </div>
  )
}
