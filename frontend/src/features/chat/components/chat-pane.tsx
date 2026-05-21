import { Fragment, useEffect, useRef, useState } from 'react';
import { useT } from '../../../i18n';
import type { Dict } from '../../../i18n/types';
import { projectRawUrl } from '../providers/registry';
import type { TodoItem } from '../runtime/todos';
import type { AppConfig, ChatAttachment, ChatCommentAttachment, ChatMessage, Conversation, PreviewComment, ProjectFile, ProjectMetadata } from '../types';
import { dayKey, dayLabel, exactDateTime, messageTime, relativeTimeLong } from '../utils/chat-time';
import { commentsToAttachments } from '../comments';
import { AgentProcessView } from './agent-process-view';
import { AssistantMessage } from './assistant-message';
import { ChatComposer, type ChatComposerHandle } from './chat-composer';
import { Icon } from './icon';

type TranslateFn = (key: keyof Dict, vars?: Record<string, string | number>) => string;

// Featured starter prompts shown on the empty chat. Clicking one fills
// the composer (does not auto-send) so users can tweak before sending.
// Each prompt is intentionally dense — it should showcase ambitious
// layout, typographic, and information-design moves rather than a
// generic landing page.
const EXAMPLE_PROMPT_KEYS: Array<{
  icon: string;
  titleKey: keyof Dict;
  tagKey: keyof Dict;
  promptKey: keyof Dict;
}> = [
  {
    icon: '▤',
    titleKey: 'chat.example1Title',
    tagKey: 'chat.example1Tag',
    promptKey: 'chat.example1Prompt',
  },
  {
    icon: '▦',
    titleKey: 'chat.example2Title',
    tagKey: 'chat.example2Tag',
    promptKey: 'chat.example2Prompt',
  },
  {
    icon: '◈',
    titleKey: 'chat.example3Title',
    tagKey: 'chat.example3Tag',
    promptKey: 'chat.example3Prompt',
  },
];

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
  error: string | null;
  projectId: string | null;
  projectFiles: ProjectFile[];
  // Names that exist in the project folder. Tool cards and chips use this
  // set to decide whether a path can be opened as a tab.
  projectFileNames?: Set<string>;
  onEnsureProject: () => Promise<string | null>;
  previewComments?: PreviewComment[];
  attachedComments?: PreviewComment[];
  onAttachComment?: (comment: PreviewComment) => void;
  onDetachComment?: (commentId: string) => void;
  onDeleteComment?: (commentId: string) => void;
  onSend: (prompt: string, attachments: ChatAttachment[], commentAttachments: ChatCommentAttachment[]) => void;
  onStop: () => void;
  // Click-to-open chain: passes a basename up to ProjectView, which sets
  // FileWorkspace's openRequest. Tool cards, attachment chips, and
  // produced-file chips all call this.
  onRequestOpenFile?: (name: string) => void;
  initialDraft?: string;
  // Question-form submissions become a normal user message; the parent
  // routes that text through onSend (no attachments).
  onSubmitForm?: (text: string) => void;
  onContinueRemainingTasks?: (assistantMessage: ChatMessage, todos: TodoItem[]) => void;
  // Header "+" button — kicks off ProjectView's create-conversation flow.
  onNewConversation?: () => void;
  // Conversation list that used to live in the topbar. The chat tab now
  // owns the list so users can browse + switch conversations without
  // leaving the pane.
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation?: (id: string, title: string) => void;
  // Composer settings/CLI button forwards to here. The dialog lives in App
  // (it owns the AppConfig lifecycle) so we just pass the open trigger.
  onOpenSettings?: () => void;
  // Optional pet wiring forwarded straight through to ChatComposer's
  // /pet button. When omitted the composer hides the button entirely.
  petConfig?: AppConfig['pet'];
  onAdoptPet?: (petId: string) => void;
  onTogglePet?: () => void;
  onOpenPetSettings?: () => void;
  projectMetadata?: ProjectMetadata;
  onProjectMetadataChange?: (metadata: ProjectMetadata) => void;
}

type Tab = 'chat' | 'comments';

export function ChatPane({
  messages,
  streaming,
  error,
  projectId,
  projectFiles,
  projectFileNames,
  onEnsureProject,
  attachedComments = [],
  onDetachComment,
  onSend,
  onStop,
  onRequestOpenFile,
  initialDraft,
  onSubmitForm,
  onContinueRemainingTasks,
  onNewConversation,
  activeConversationId,
  onOpenSettings,
  petConfig,
  onAdoptPet,
  onTogglePet,
  onOpenPetSettings,
  projectMetadata,
  onProjectMetadataChange,
}: Props) {
  const t = useT();
  const logRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<ChatComposerHandle | null>(null);
  const didInitialScrollRef = useRef(false);
  const [tab, setTab] = useState<Tab>('chat');
  const [scrolledFromBottom, setScrolledFromBottom] = useState(false);
  const lastAssistantId = [...messages].reverse().find((m) => m.role === 'assistant')?.id;
  const hasActiveRunMessage = messages.some(
    (m) => m.role === 'assistant' && isActiveRunStatus(m.runStatus),
  );
  // Map each assistant message id to the user message that follows it
  // (if any) so QuestionFormView can render its locked "answered" state
  // with the user's picks.
  const nextUserContentByAssistantId = (() => {
    const map = new Map<string, string>();
    for (let i = 0; i < messages.length - 1; i++) {
      const m = messages[i]!;
      const next = messages[i + 1]!;
      if (m.role === 'assistant' && next.role === 'user') {
        map.set(m.id, next.content);
      }
    }
    return map;
  })();

  useEffect(() => {
    didInitialScrollRef.current = false;
  }, [activeConversationId]);

  useEffect(() => {
    const el = logRef.current;
    if (!el || didInitialScrollRef.current || messages.length === 0) return;
    didInitialScrollRef.current = true;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
      setScrolledFromBottom(false);
    });
  }, [activeConversationId, messages.length]);

  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    // Auto-scroll only when we're already pinned near the bottom — preserves
    // a user's scrollback position when they're reading earlier output while
    // a new turn streams in.
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distance < 80) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, error]);

  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    function onScroll() {
      const target = logRef.current;
      if (!target) return;
      const distance =
        target.scrollHeight - target.scrollTop - target.clientHeight;
      setScrolledFromBottom(distance > 120);
    }
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  console.log('[ChatPane] messages:', messages);

  function jumpToBottom() {
    const el = logRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }

  return (
    <div className="pane">
      <div className="chat-header">
        <div className="chat-header-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'chat'}
            className={`chat-header-tab${tab === 'chat' ? ' active' : ''}`}
            onClick={() => setTab('chat')}
          >
            {t('chat.tabChat')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'comments'}
            className={`chat-header-tab${tab === 'comments' ? ' active' : ''}`}
            onClick={() => setTab('comments')}
          >
            {t('chat.tabComments')}
          </button>
        </div>
        <div className="chat-header-actions">
          <button
            type="button"
            className="icon-only"
            data-testid="new-conversation"
            title={t('chat.newConversationsTitle')}
            aria-label={t('chat.newConversation')}
            onClick={onNewConversation}
            disabled={!onNewConversation}
          >
            <Icon name="plus" size={16} />
          </button>
        </div>
      </div>
      {tab === 'chat' ? (
        <>
          <div className="chat-log-wrap">
            <div className="chat-log" ref={logRef}>
              {messages.length === 0 ? (
                <div className="chat-empty-wrap">
                  <div className="chat-empty">
                    <span className="chat-empty-title">
                      {t('chat.startTitle')}
                    </span>
                    <span className="chat-empty-hint">
                      {t('chat.startHint')}
                    </span>
                  </div>
                  <div className="chat-examples" role="list">
                    {EXAMPLE_PROMPT_KEYS.map((ex, i) => {
                      const title = t(ex.titleKey);
                      const tag = t(ex.tagKey);
                      const prompt = t(ex.promptKey);
                      return (
                        <button
                          key={ex.titleKey}
                          type="button"
                          role="listitem"
                          className="chat-example"
                          style={{ animationDelay: `${i * 70}ms` }}
                          onClick={() => composerRef.current?.setDraft(prompt)}
                          title={t('chat.fillInputTitle')}
                        >
                          <span className="chat-example-icon" aria-hidden>
                            {ex.icon}
                          </span>
                          <span className="chat-example-body">
                            <span className="chat-example-head">
                              <span className="chat-example-title">{title}</span>
                              <span className="chat-example-tag">{tag}</span>
                            </span>
                            <span className="chat-example-prompt">{prompt}</span>
                          </span>
                          <span className="chat-example-cta" aria-hidden>
                            ↵
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              {messages.map((m, i) => {
                const showDaySeparator = shouldShowDaySeparator(messages[i - 1], m);
                const messageStreaming =
                  m.role === 'assistant' &&
                  ((streaming && m.id === lastAssistantId) || isActiveRunStatus(m.runStatus));
                return (
                  <Fragment key={m.id}>
                    {showDaySeparator ? <DaySeparator ts={messageTime(m)} /> : null}
                    {m.role === 'user' ? (
                      <UserMessage
                        message={m}
                        projectFileNames={projectFileNames}
                        onRequestOpenFile={onRequestOpenFile}
                        t={t}
                      />
                    ) : (
                      <AssistantMessage
                        message={m}
                        streaming={messageStreaming}
                        projectId={projectId}
                        projectFileNames={projectFileNames}
                        onRequestOpenFile={onRequestOpenFile}
                        isLast={m.id === lastAssistantId}
                        nextUserContent={nextUserContentByAssistantId.get(m.id)}
                        onSubmitForm={onSubmitForm}
                        onContinueRemainingTasks={
                          m.id === lastAssistantId && onContinueRemainingTasks
                            ? (todos) => onContinueRemainingTasks(m, todos)
                            : undefined
                        }
                      />
                    )}
                  </Fragment>
                );
              })}
              {error ? <div className="msg error">{error}</div> : null}
            </div>
            {scrolledFromBottom ? (
              <button
                type="button"
                className="chat-jump-btn"
                onClick={jumpToBottom}
                title={t('chat.scrollToLatest')}
              >
                <Icon name="arrow-up" size={12} style={{ transform: 'rotate(180deg)' }} />
                <span>{t('chat.jumpToLatest')}</span>
              </button>
            ) : null}
          </div>
          <ChatComposer
            ref={composerRef}
            projectId={projectId}
            projectFiles={projectFiles}
            streaming={streaming || hasActiveRunMessage}
            initialDraft={initialDraft}
            onEnsureProject={onEnsureProject}
            commentAttachments={commentsToAttachments(attachedComments)}
            onRemoveCommentAttachment={onDetachComment}
            onSend={onSend}
            onStop={onStop}
            onOpenSettings={onOpenSettings}
            petConfig={petConfig}
            onAdoptPet={onAdoptPet}
            onTogglePet={onTogglePet}
            onOpenPetSettings={onOpenPetSettings}
            projectMetadata={projectMetadata}
            onProjectMetadataChange={onProjectMetadataChange}
          />
        </>
      ) : null}
      {tab === 'comments' ? (
        <AgentProcessView
          messages={messages}
          streaming={streaming || hasActiveRunMessage}
          projectFileNames={projectFileNames}
          onRequestOpenFile={onRequestOpenFile}
        />
      ) : null}
    </div>
  );
}

function isActiveRunStatus(status: ChatMessage['runStatus']): boolean {
  return status === 'queued' || status === 'running';
}

function UserMessage({
  message,
  projectFileNames,
  onRequestOpenFile,
  t,
}: {
  message: ChatMessage;
  projectFileNames?: Set<string>;
  onRequestOpenFile?: (name: string) => void;
  t: TranslateFn;
}) {
  const attachments = message.attachments ?? [];
  const commentAttachments = message.commentAttachments ?? [];
  return (
    <div className="msg user">
      <div className="role">
        <span>{t('chat.you')}</span>
        <MessageTimestamp message={message} t={t} />
      </div>
      {attachments.length > 0 ? (
        <div className="user-attachments">
          {attachments.map((a) => {
            const baseName = a.path.split('/').pop() || a.path;
            const openable =
              !!onRequestOpenFile &&
              (projectFileNames ? projectFileNames.has(baseName) : true);
            const handleOpen = openable
              ? () => onRequestOpenFile?.(baseName)
              : undefined;
            return (
              <button
                type="button"
                key={a.path}
                className={`user-attachment staged-${a.kind}${openable ? ' openable' : ''}`}
                onClick={handleOpen}
                disabled={!openable}
                title={openable ? t('chat.openFile', { name: baseName }) : a.path}
              >
                {a.kind === 'image' ? (
                  <img src={a.url ?? projectRawUrl(a.path)} alt={a.name} />
                ) : (
                  <Icon name="file" size={14} />
                )}
                <span className="staged-name">{a.name}</span>
              </button>
            );
          })}
        </div>
      ) : null}
      {commentAttachments.length > 0 ? (
        <div className="user-attachments comment-history-attachments">
          {commentAttachments.map((a) => (
            <span key={a.id} className="user-attachment staged-comment">
              <span className="staged-name">
                <strong>{a.elementId}</strong>
                <span>{a.comment}</span>
              </span>
            </span>
          ))}
        </div>
      ) : null}
      {message.content ? <div className="user-text">{message.content}</div> : null}
    </div>
  );
}

function DaySeparator({ ts }: { ts: number | undefined }) {
  if (!ts) return null;
  return (
    <div className="chat-day-separator" role="separator">
      <time dateTime={new Date(ts).toISOString()}>{dayLabel(ts)}</time>
    </div>
  );
}

function MessageTimestamp({ message, t }: { message: ChatMessage; t: TranslateFn }) {
  const ts = messageTime(message);
  if (!ts) return null;
  return (
    <time className="msg-time" dateTime={new Date(ts).toISOString()} title={exactDateTime(ts)}>
      {relativeTimeLong(ts, t)}
    </time>
  );
}

function shouldShowDaySeparator(prev: ChatMessage | undefined, curr: ChatMessage): boolean {
  const currTime = messageTime(curr);
  if (!currTime) return false;
  const prevTime = prev ? messageTime(prev) : undefined;
  if (!prevTime) return true;
  return dayKey(prevTime) !== dayKey(currTime);
}
