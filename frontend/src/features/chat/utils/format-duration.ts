/**
 * Format duration in milliseconds to readable string.
 * Shared utility for consistent time display across components.
 */

/**
 * Format milliseconds to human-readable duration.
 * @param ms - Duration in milliseconds
 * @returns Formatted string like "500ms", "5s", "1m 30s"
 */
export function formatDuration(ms: number): string {
  if (ms < 0) return "0ms"
  if (ms < 1000) return `${Math.round(ms)}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (remainingSeconds === 0) return `${minutes}m`
  return `${minutes}m ${remainingSeconds}s`
}

/**
 * Format timestamp to relative duration from now.
 * @param startTime - Start timestamp in milliseconds
 * @param endTime - Optional end timestamp (uses Date.now() if not provided)
 * @returns Formatted duration string
 */
export function formatElapsed(startTime: number, endTime?: number): string {
  const end = endTime ?? Date.now()
  return formatDuration(end - startTime)
}