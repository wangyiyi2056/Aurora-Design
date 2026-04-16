import { expect, test } from 'vitest'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

test('merges tailwind classes correctly', () => {
  expect(cn('px-2 py-1', 'px-4')).toBe('py-1 px-4')
})

test('handles conditional classes', () => {
  expect(cn('bg-red-500', false && 'text-white', 'text-black')).toBe('bg-red-500 text-black')
})
