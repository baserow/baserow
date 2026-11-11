/**
 * The permission plugin allows everything in tests and can't be replaced. A
 * spec decides per test through `permission.check` once it mocks `#app` with
 * `mockHasPermission`:
 *
 *   vi.mock('#app', async (importOriginal) =>
 *     (await import('@baserow/test/helpers/permission')).mockHasPermission(
 *       importOriginal
 *     )
 *   )
 */
export const permission = { check: () => true }

export const mockHasPermission = async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    useNuxtApp: () =>
      new Proxy(original.useNuxtApp(), {
        get(target, property) {
          return property === '$hasPermission'
            ? (...args) => permission.check(...args)
            : Reflect.get(target, property)
        },
      }),
  }
}
