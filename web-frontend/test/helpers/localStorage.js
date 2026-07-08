/**
 * The Nuxt/happy-dom vitest environment does not provide localStorage. Install
 * a minimal in-memory implementation on the global scope for tests that need it.
 */
export function installLocalStorageMock() {
  if (global.localStorage) {
    return
  }
  const store = {}
  global.localStorage = {
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
