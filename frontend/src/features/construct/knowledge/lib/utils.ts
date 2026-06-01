// @ts-nocheck
export const errorMessage = (e: any) => e?.message || String(e);

export const createSelectors = <S extends import("zustand").UseBoundStore<import("zustand").StoreApi<object>>>(
  _store: S,
) => {
  let store = _store as any
  store.use = {}
  for (let k of Object.keys(store.getState())) {
    ;(store.use as any)[k] = () => store((s: any) => s[k as keyof typeof s])
  }
  return store
}
