// @vitest-environment happy-dom
import { afterEach, describe, expect, test, vi } from 'vitest'
import { createSSRApp, h, nextTick, ref } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { Registry } from '@baserow/modules/core/registry'
import {
  BooleanFieldType,
  TextFieldType,
} from '@baserow/modules/database/fieldTypes'
import FormElement from '@baserow/modules/core/components/FormElement'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FormInput from '@baserow/modules/core/components/FormInput'
import { DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY } from '@baserow/modules/database/constants'

describe('server-rendered async form fields', () => {
  let clientApp, container

  afterEach(() => {
    clientApp?.unmount()
    container?.remove()
    clientApp = null
    container = null
    vi.useRealTimers()
  })

  async function hydrateField(FieldType, initialValue) {
    const appContext = {
      $i18n: { t: (key) => key },
      $config: { public: { baserowMaxFieldTextLength: 100_000 } },
    }
    const registry = new Registry()
    registry.registerNamespace('field')
    const fieldType = new FieldType({ app: appContext })
    registry.register('field', fieldType)
    const field = { id: 1, type: fieldType.type }
    const component =
      fieldType.getFormViewFieldComponents(field)[
        DEFAULT_FORM_VIEW_FIELD_COMPONENT_KEY
      ].component
    const value = ref(initialValue)
    const root = {
      render() {
        return h(component, {
          field,
          value: value.value,
          workspaceId: 0,
          readOnly: false,
          touched: false,
          onUpdate: (newValue) => {
            value.value = newValue
          },
        })
      },
    }
    const createApp = () => {
      const app = createSSRApp(root)
      Object.assign(app.config.globalProperties, {
        $registry: registry,
        $t: appContext.$i18n.t,
      })
      app.component('FormElement', FormElement)
      app.component('FormGroup', FormGroup)
      app.component('FormInput', FormInput)
      return app
    }

    container = document.createElement('div')
    container.innerHTML = await renderToString(createApp())
    document.body.appendChild(container)
    // Keep idle callbacks pending: users must be able to interact as soon as
    // component code is available, without waiting for a later idle period.
    vi.useFakeTimers()
    clientApp = createApp()
    clientApp.mount(container)
    await nextTick()
    return value
  }

  test('preserves the first text edit before any idle callback runs', async () => {
    const submittedValue = await hydrateField(TextFieldType, '')
    const input = container.querySelector('input')
    expect(input).not.toBeNull()

    input.dispatchEvent(new Event('focus'))
    input.value = 'First response'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('blur'))
    await nextTick()

    expect(submittedValue.value).toBe('First response')
    expect(input.value).toBe('First response')
  })

  test('preserves the first checkbox click before any idle callback runs', async () => {
    const submittedValue = await hydrateField(BooleanFieldType, false)
    const checkbox = container.querySelector('.field-boolean__checkbox')
    expect(checkbox).not.toBeNull()

    checkbox.click()
    await nextTick()

    expect(submittedValue.value).toBe(true)
    expect(checkbox.classList.contains('active')).toBe(true)
  })
})
