export async function patchProject<T extends Record<string, unknown>>(
  _id: string,
  patch: Partial<T>
): Promise<Partial<T>> {
  return patch
}
