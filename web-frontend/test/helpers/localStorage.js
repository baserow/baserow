/**
 * The Nuxt/happy-dom vitest environment does not provide localStorage. Install
 * a minimal in-memory implementation on the global scope for tests that need it.
 */
export function installLocalStorageMock() {
  if (globalThis.localStorage) {
    return
  }
  // Null-prototype store so keys like `toString` or `__proto__` behave like
  // real localStorage entries instead of hitting inherited properties.
  const store = Object.create(null)
  globalThis.localStorage = {
    getItem: (key) => (key in store ? store[key] : null),
    setItem: (key, value) => {
      store[key] = String(value)
    },
    removeItem: (key) => {
      delete store[key]
    },
    clear: () => {
      Object.keys(store).forEach((key) => delete store[key])
    },
    key: (index) => Object.keys(store)[index] ?? null,
    get length() {
      return Object.keys(store).length
    },
  }
}
