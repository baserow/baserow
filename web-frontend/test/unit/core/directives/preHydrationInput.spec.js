import { flushPromises } from '@vue/test-utils'
import { createSSRApp, defineComponent, h, ref, Suspense } from 'vue'
import { renderToString } from 'vue/server-renderer'

import Checkbox from '@baserow/modules/core/components/Checkbox.vue'
import FormInput from '@baserow/modules/core/components/FormInput.vue'

// The server rendered inputs can be used before the page is hydrated. What the user
// did in that window must survive the hydration.
describe('preHydrationInput', () => {
  let container = null

  const createApp = (component, state, props) =>
    createSSRApp({
      render: () =>
        h(component, {
          ...props,
          modelValue: state.value.value,
          'onUpdate:modelValue': (value) => (state.value.value = value),
          onFocus: () => state.events.push('focus'),
          onBlur: () => state.events.push('blur'),
        }),
    })

  // Renders on the server, lets `interact` use the static input, then hydrates.
  const hydrate = async (
    interact,
    component = FormInput,
    initial = '',
    props
  ) => {
    const server = { value: ref(initial), events: [] }
    container = document.createElement('div')
    container.innerHTML = await renderToString(
      createApp(component, server, props)
    )
    document.body.appendChild(container)
    interact(container.querySelector('input'))

    const client = { value: ref(initial), events: [] }
    createApp(component, client, props).mount(container)
    await Promise.resolve()
    return { input: container.querySelector('input'), ...client }
  }

  afterEach(() => container?.remove())

  test('keeps a value typed and left before hydration', async () => {
    const { input, value, events } = await hydrate((input) => {
      input.value = 'Jane Doe'
    })

    expect(input.value).toBe('Jane Doe')
    expect(value.value).toBe('Jane Doe')
    expect(events).toEqual(['focus', 'blur'])
  })

  test('reports the focus the input got before hydration', async () => {
    const { value, events } = await hydrate((input) => input.focus())

    expect(value.value).toBe('')
    expect(events).toEqual(['focus'])
  })

  test('does nothing for an untouched input', async () => {
    const { events } = await hydrate(() => {})

    expect(events).toEqual([])
  })

  test('keeps a checkbox ticked before hydration', async () => {
    const { input, value } = await hydrate(
      (input) => input.click(),
      Checkbox,
      false
    )

    expect(input.checked).toBe(true)
    expect(value.value).toBe(true)
  })

  test('keeps a value typed while an async sibling delays the mount', async () => {
    let resume = null
    const AsyncSibling = defineComponent({
      async setup() {
        if (resume) {
          await new Promise((resolve) => (resume = resolve))
        }
        return () => h('span')
      },
    })
    const createSuspenseApp = (state) =>
      createSSRApp({
        render: () =>
          h(Suspense, null, () =>
            h('div', [
              h(FormInput, {
                modelValue: state.value,
                'onUpdate:modelValue': (value) => (state.value = value),
              }),
              h(AsyncSibling),
            ])
          ),
      })

    container = document.createElement('div')
    container.innerHTML = await renderToString(createSuspenseApp(ref('')))
    document.body.appendChild(container)
    const input = container.querySelector('input')
    input.value = 'Jane'

    resume = true
    const state = ref('')
    createSuspenseApp(state).mount(container)
    input.value = 'Jane Doe'
    input.dispatchEvent(new Event('input'))
    resume()
    await flushPromises()

    expect(input.value).toBe('Jane Doe')
    expect(state.value).toBe('Jane Doe')
  })
})
