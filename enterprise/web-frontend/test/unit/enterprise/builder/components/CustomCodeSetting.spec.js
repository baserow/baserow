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
  const save = wrapper.get('button[type="submit"]')
  const saveHtml = async () => {
    await wrapper.get('form:has(button[type="submit"])').trigger('submit')
    await flushPromises()
  }
  return { builder, dispatch, applyUpdate, wrapper, html, save, saveHtml }
}

test('saves the HTML text explicitly and can clear it', async () => {
  const { builder, dispatch, wrapper, html, save, saveHtml } =
    await mountSetting()

  expect(html.element.value).toBe(savedHtml)
  expect(save.element.disabled).toBe(true)
  await html.setValue(newHtml)
  await wrapper.get('textarea[data-language="css"]').setValue('body {}')

  await vi.waitFor(() => expect(dispatch).toHaveBeenCalledOnce())
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { custom_code: { css: 'body {}', js: '' }, scripts: [] },
  })
  expect(builder.custom_code.html).toBe(savedHtml)

  await saveHtml()
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { custom_code: { html: newHtml } },
  })
  expect(save.element.disabled).toBe(true)

  await html.setValue('')
  await saveHtml()
  expect(dispatch).toHaveBeenLastCalledWith('application/update', {
    application: builder,
    values: { custom_code: { html: '' } },
  })
  expect(builder.custom_code.css).toBe('body {}')
})

test('waits for an in-flight autosave and keeps the HTML draft after a failed save', async () => {
  const { builder, dispatch, applyUpdate, wrapper, html, save, saveHtml } =
    await mountSetting()
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
  await saveHtml()
  expect(dispatch).toHaveBeenCalledOnce()
  expect(save.element.disabled).toBe(true)

  finishAutosave()
  await flushPromises()
  expect(dispatch).toHaveBeenCalledTimes(2)
  expect(builder.custom_code.html).toBe(savedHtml)
  expect(html.element.value).toBe(newHtml)
  expect(wrapper.get('[role="alert"]').text()).toBe(
    'customCodeSettingForm.customHtmlSaveError'
  )
  expect(save.element.disabled).toBe(false)

  await saveHtml()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(builder.custom_code.html).toBe(newHtml)
  expect(builder.custom_code.js).toBe('let a = 1')
})
