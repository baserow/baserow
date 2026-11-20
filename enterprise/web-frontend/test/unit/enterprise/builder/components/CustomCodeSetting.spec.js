import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { useRuntimeConfig } from '#imports'

import CustomCodeSetting from '@baserow_enterprise/components/builder/CustomCodeSetting'

enableAutoUnmount(afterEach)

const savedHtml = '<meta name="description" content="Saved">'
const newHtml = '  <meta name="description" content="Draft">\n'

async function mountSetting(previous = {}) {
  const builder =
    previous.builder ??
    reactive({
      id: 1,
      workspace: { id: 2 },
      custom_code: { css: '', js: '' },
      head_html: savedHtml,
      scripts: [],
    })
  const applyUpdate = async (_action, { values }) => {
    Object.assign(builder, values)
  }
  const dispatch = previous.dispatch ?? vi.fn(applyUpdate)
  const wrapper = await mountSuspended(CustomCodeSetting, {
    props: { builder },
    global: {
      mocks: { $store: { dispatch }, $hasPermission: () => true },
      stubs: {
        ApplicationUntrustedContentAlert: true,
        CodeEditor: {
          props: ['modelValue', 'language', 'placeholder'],
          emits: ['update:modelValue', 'blur'],
          template: `<textarea :data-language="language" :value="modelValue"
            :placeholder="placeholder" @blur="$emit('blur', $event)"
            @input="$emit('update:modelValue', $event.target.value)"></textarea>`,
        },
      },
    },
  })

  const html = wrapper.get('textarea[data-language="html"]')
  return { builder, dispatch, applyUpdate, wrapper, html }
}

test('autosaves and clears HTML independently of the CSS and script forms', async () => {
  const { builder, dispatch, wrapper, html } = await mountSetting()

  expect(html.element.value).toBe(savedHtml)
  expect(wrapper.find('button[type="submit"]').exists()).toBe(false)
  await wrapper.get('textarea[data-language="css"]').setValue('body {}')

  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledOnce())
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { custom_code: { css: 'body {}', js: '' }, scripts: [] },
  })
  expect(builder.head_html).toBe(savedHtml)

  // An invalid external-script URL must not block the independent HTML field.
  await wrapper.get('.custom-code__add-script button').trigger('click')
  await wrapper
    .get('input[placeholder="customCodeSettingScriptForm.urlPlaceholder"]')
    .setValue('not-a-url')
  expect(wrapper.text()).toContain('error.invalidURL')
  await html.setValue(newHtml)
  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledTimes(2))
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { head_html: newHtml },
  })

  await html.setValue('')
  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledTimes(3))
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { head_html: '' },
  })
  expect(builder.custom_code.css).toBe('body {}')
})

test('keeps HTML when an earlier CSS response arrives later', async () => {
  const { builder, dispatch, applyUpdate, wrapper, html } = await mountSetting()
  let finishAutosave
  const pendingAutosave = new Promise((resolve) => {
    finishAutosave = resolve
  })
  dispatch.mockImplementationOnce(async (...args) => {
    await pendingAutosave
    await applyUpdate(...args)
  })
  await wrapper
    .get('textarea[data-language="javascript"]')
    .setValue('let a = 1')
  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledOnce())
  await html.setValue(newHtml)
  await html.trigger('blur')
  await flushPromises()
  expect(dispatch).toHaveBeenCalledTimes(2)
  expect(builder.head_html).toBe(newHtml)

  finishAutosave()
  await flushPromises()
  expect(builder.head_html).toBe(newHtml)
  expect(builder.custom_code.js).toBe('let a = 1')
})

test('retains a failed close-time save across reopening and retries on edit', async () => {
  const first = await mountSetting()
  first.dispatch.mockRejectedValueOnce(new Error('Unable to save'))
  await first.html.setValue(newHtml)
  expect(first.dispatch).not.toHaveBeenCalled()
  first.wrapper.unmount()
  await flushPromises()

  expect(first.dispatch).toHaveBeenCalledExactlyOnceWith('application/update', {
    application: first.builder,
    values: { head_html: newHtml },
  })
  const second = await mountSetting(first)
  expect(second.html.element.value).toBe(newHtml)
  expect(second.wrapper.get('[role="alert"]').text()).toBe(
    'customCodeSettingForm.customHtmlSaveError'
  )
  const retryHtml = `${newHtml}\n`
  await second.html.setValue(retryHtml)
  await vi.waitFor(() => expect(first.dispatch).toHaveBeenCalledTimes(2))
  expect(second.wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(first.builder.head_html).toBe(retryHtml)
})

test('persists a revert to the original HTML while a different value is saving', async () => {
  const { builder, dispatch, applyUpdate, html } = await mountSetting()
  let finishFirstSave
  const firstSave = new Promise((resolve) => {
    finishFirstSave = resolve
  })
  dispatch.mockImplementationOnce(async (...args) => {
    await firstSave
    await applyUpdate(...args)
  })

  await html.setValue(newHtml)
  await html.trigger('blur')
  expect(dispatch).toHaveBeenCalledOnce()
  await html.setValue(savedHtml)
  await html.trigger('blur')
  finishFirstSave()
  await flushPromises()

  expect(dispatch).toHaveBeenCalledTimes(2)
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { head_html: savedHtml },
  })
  expect(builder.head_html).toBe(savedHtml)
  expect(html.element.value).toBe(savedHtml)
})

describe('Preview notice', () => {
  // Test locales are empty, so $t renders the key.
  const notice = 'customCodeSettingForm.customHtmlNotInPreview'
  let publicConfig
  let original

  beforeEach(() => {
    publicConfig = useRuntimeConfig().public
    original = {
      builderPreviewUrl: publicConfig.builderPreviewUrl,
      publicWebFrontendUrl: publicConfig.publicWebFrontendUrl,
    }
  })

  afterEach(() => {
    Object.assign(publicConfig, original)
  })

  test.each([
    ['shares the editor hostname', 'http://localhost:3001', true],
    ['has its own hostname', 'http://preview.localhost:3000', false],
  ])('when Preview %s', async (_, builderPreviewUrl, shown) => {
    Object.assign(publicConfig, {
      builderPreviewUrl,
      publicWebFrontendUrl: 'http://localhost:3000',
    })
    const { wrapper } = await mountSetting()

    expect(wrapper.text().includes(notice)).toBe(shown)
  })
})
