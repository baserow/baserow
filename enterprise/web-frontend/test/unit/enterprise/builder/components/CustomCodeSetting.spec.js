import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'

import CustomCodeSetting from '@baserow_enterprise/components/builder/CustomCodeSetting'

enableAutoUnmount(afterEach)

const savedHtml = '<meta name="description" content="Saved">'
const newHtml = '  <meta name="description" content="Draft">\n'

async function mountSetting() {
  const builder = reactive({
    id: 1,
    workspace: { id: 2 },
    custom_code: { css: '', js: '', html: savedHtml },
    scripts: [],
  })
  const applyUpdate = async (_action, { values }) => {
    builder.custom_code = { ...builder.custom_code, ...values.custom_code }
  }
  const dispatch = vi.fn(applyUpdate)
  const wrapper = await mountSuspended(CustomCodeSetting, {
    props: { builder },
    global: {
      mocks: { $store: { dispatch }, $hasPermission: () => true },
      stubs: {
        ApplicationUntrustedContentAlert: true,
        CodeEditor: {
          props: ['modelValue', 'language'],
          emits: ['update:modelValue'],
          template: `<textarea :data-language="language" :value="modelValue"
            @input="$emit('update:modelValue', $event.target.value)"></textarea>`,
        },
      },
    },
  })

  const label = wrapper
    .findAll('label[for]')
    .find((label) => label.text() === 'customCodeSettingForm.customHtml')
  const html = wrapper.get(`textarea[id="${label.attributes('for')}"]`)
  return { builder, dispatch, applyUpdate, wrapper, html }
}

test('autosaves HTML independently of CSS and can clear it', async () => {
  const { builder, dispatch, wrapper, html } = await mountSetting()

  const javascript = wrapper.get('textarea[data-language="javascript"]')
  const externalScripts = wrapper.get('.custom-code__add-script')
  expect(
    javascript.element.compareDocumentPosition(html.element) &
      Node.DOCUMENT_POSITION_FOLLOWING
  ).toBeTruthy()
  expect(
    html.element.compareDocumentPosition(externalScripts.element) &
      Node.DOCUMENT_POSITION_FOLLOWING
  ).toBeTruthy()
  expect(html.element.value).toBe(savedHtml)
  expect(wrapper.find('button[type="submit"]').exists()).toBe(false)
  await wrapper.get('textarea[data-language="css"]').setValue('body {}')

  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledOnce())
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { custom_code: { css: 'body {}', js: '' }, scripts: [] },
  })
  expect(builder.custom_code.html).toBe(savedHtml)

  await html.setValue(newHtml)
  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledTimes(2))
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { custom_code: { html: newHtml } },
  })

  await html.setValue('')
  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledTimes(3))
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { custom_code: { html: '' } },
  })
  expect(builder.custom_code.css).toBe('body {}')
})

test('waits for an in-flight autosave and keeps the HTML draft after a failed save', async () => {
  const { builder, dispatch, applyUpdate, wrapper, html } = await mountSetting()
  let finishAutosave
  const pendingAutosave = new Promise((resolve) => {
    finishAutosave = resolve
  })
  dispatch.mockImplementationOnce(async (...args) => {
    await pendingAutosave
    await applyUpdate(...args)
  })
  dispatch.mockRejectedValueOnce(new Error('Unable to save'))

  await wrapper
    .get('textarea[data-language="javascript"]')
    .setValue('let a = 1')
  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledOnce())
  await html.setValue(newHtml)
  await html.trigger('blur')
  expect(dispatch).toHaveBeenCalledOnce()
  expect(html.element.disabled).toBe(false)

  finishAutosave()
  await flushPromises()
  expect(dispatch).toHaveBeenCalledTimes(2)
  expect(builder.custom_code.html).toBe(savedHtml)
  expect(html.element.value).toBe(newHtml)
  expect(wrapper.get('[role="alert"]').text()).toBe(
    'customCodeSettingForm.customHtmlSaveError'
  )

  const retryHtml = `${newHtml}\n`
  await html.setValue(retryHtml)
  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledTimes(3))
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(builder.custom_code.html).toBe(retryHtml)
  expect(builder.custom_code.js).toBe('let a = 1')
})

test('flushes a scheduled HTML autosave when the settings close', async () => {
  const { builder, dispatch, wrapper, html } = await mountSetting()

  await html.setValue(newHtml)
  expect(dispatch).not.toHaveBeenCalled()
  wrapper.unmount()
  await flushPromises()

  expect(dispatch).toHaveBeenCalledExactlyOnceWith('application/update', {
    application: builder,
    values: { custom_code: { html: newHtml } },
  })
  expect(builder.custom_code.html).toBe(newHtml)
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
    values: { custom_code: { html: savedHtml } },
  })
  expect(builder.custom_code.html).toBe(savedHtml)
  expect(html.element.value).toBe(savedHtml)
})
