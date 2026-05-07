import type { ChatMessage } from '../types';
import type { Dict } from '../../../i18n/types';

type TranslateFn = (key: keyof Dict, vars?: Record<string, string | number>) => string;

export function messageTime(message: ChatMessage): number | undefined {
  if (message.role === 'assistant') {
    return message.startedAt ?? message.createdAt ?? message.startTime ?? message.endedAt ?? message.endTime;
  }
  return message.createdAt ?? message.startedAt ?? message.startTime ?? message.endedAt ?? message.endTime;
}

export function dayKey(ts: number): string {
  const d = new Date(ts);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export function dayLabel(ts: number): string {
  return new Date(ts).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function exactDateTime(ts: number): string {
  return new Date(ts).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function relativeTimeLong(ts: number, t?: TranslateFn): string {
  const diff = Math.max(0, Date.now() - ts);
  const min = 60_000;
  const hr = 60 * min;
  const day = 24 * hr;
  if (diff < min) return t ? t('common.justNow') : '刚刚';
  if (diff < hr) {
    const n = Math.floor(diff / min);
    return t ? t('common.minutesAgo', { n }) : `${n} 分钟前`;
  }
  if (diff < day) {
    const n = Math.floor(diff / hr);
    return t ? t('common.hoursAgo', { n }) : `${n} 小时前`;
  }
  if (diff < 7 * day) {
    const n = Math.floor(diff / day);
    return t ? t('common.daysAgo', { n }) : `${n} 天前`;
  }
  return new Date(ts).toLocaleDateString();
}
