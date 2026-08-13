import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import GridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRichText.vue'
import FormViewDescription from '@baserow/modules/database/components/view/form/FormViewDescription.vue'
import {
  stripImageUrls,
  stripUnresolvedImageRefs,
} from '@baserow/modules/core/editor/richTextImageUtils'
import { TestApp } from '@baserow/test/helpers/testApp'

// Unresolved user file references and external values that arrive while a cell
// is open. A reference the editor cannot resolve to a URL is the shape stored
// in the database: `![alt][name]`, no `(url)` group.
const REFERENCE = '![photo][abcd_efgh.png]'

const EDITOR_STUBS = {
  RichTextEditorBubbleMenu: true,
  RichTextEditorFloatingMenu: true,
}

describe('unresolved user file reference serialization', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  // `uploadFile` is passed, so `prepareContent()` leaves the value alone and the
  // reference becomes a real image node with an empty `src`.
  const mountEditor = (modelValue) =>
    testApp.mount(RichTextEditor, {
      props: {
        modelValue,
        enableRichTextFormatting: true,
        enableImages: true,
        uploadFile: async () => ({ data: {} }),
      },
      global: { stubs: EDITOR_STUBS },
    })

  // Expected value is the storage format the backend reads and writes
  // (`![alt][name]`), not what the serializer currently emits.
  test('round trips a bare reference without adding an empty url group', async () => {
    const wrapper = await mountEditor(REFERENCE)

    expect(wrapper.vm.serializeToMarkdown()).toBe(REFERENCE)
  })

  // Every open/save cycle appends another empty group, so the value grows
  // without bound.
  test('does not accumulate empty url groups over repeated saves', async () => {
    let value = REFERENCE
    for (let i = 0; i < 5; i++) {
      const wrapper = await mountEditor(value)
      value = wrapper.vm.serializeToMarkdown()
    }

    expect(value).toBe(REFERENCE)
  })

  // `stripImageUrls` removes a resolved `(url)`; it must also remove an empty
  // one, otherwise the malformed form reaches the backend.
  test('strips an empty url group like it strips a resolved one', () => {
    expect(stripImageUrls(`${REFERENCE}()`)).toBe(REFERENCE)
  })
})

describe('unresolved reference round trips through the clipboard', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  // The placeholder is a `span`, so the parser needs a rule for it: otherwise
  // an in-editor copy/paste of an unresolved reference pastes back as literal
  // text and the user file name is lost.
  test('survives a copy and paste as HTML', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: REFERENCE,
        enableRichTextFormatting: true,
        enableImages: true,
        uploadFile: () => {},
      },
      global: { stubs: EDITOR_STUBS },
    })
    const html = wrapper.vm.editor.getHTML()
    expect(html).toContain('rich-text-editor__image-placeholder')

    const pasted = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: '',
        enableRichTextFormatting: true,
        enableImages: true,
        uploadFile: () => {},
      },
      global: { stubs: EDITOR_STUBS },
    })
    pasted.vm.editor.commands.insertContent(html)

    expect(pasted.vm.serializeToMarkdown()).toContain('abcd_efgh.png')
  })

  test('a resolved reference still renders an img', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: `${REFERENCE}(https://storage/abcd_efgh.png)`,
        enableRichTextFormatting: true,
        enableImages: true,
        uploadFile: () => {},
      },
      global: { stubs: EDITOR_STUBS },
    })

    expect(wrapper.find('.tiptap img').exists()).toBe(true)
  })
})

describe('unresolved reference in an editor without an upload handler', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  // Covers `prepareContent()`'s `!this.uploadFile` branch, which no existing
  // test observes: with the condition removed the whole suite still passes.
  test('renders a placeholder rather than raw markdown', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: REFERENCE,
        enableRichTextFormatting: true,
        enableImages: true,
      },
      global: { stubs: EDITOR_STUBS },
    })
    const text = wrapper.find('.tiptap').text()

    expect(text).not.toContain('abcd_efgh.png')
    expect(text).toContain('photo')
  })

  // The placeholder used to be substituted into the *editable* content, so the
  // filename was lost as soon as the value was saved back. The description
  // editor has no `enable-images`, so the reference round trips as escaped
  // text rather than an image node — either way it must survive the save.
  test('does not destroy the reference when the description is saved', async () => {
    const wrapper = await testApp.mount(FormViewDescription, {
      props: { value: `Intro ${REFERENCE} outro`, readOnly: false },
      global: { stubs: EDITOR_STUBS },
    })
    await wrapper.vm.edit()
    await wrapper.vm.$nextTick()
    wrapper.vm.dirty = true
    wrapper.vm.stopEditing()

    const saved = wrapper.emitted('change')[0][0]
    expect(saved.replace(/\\/g, '')).toContain('abcd_efgh.png')
    expect(saved).not.toContain('\uD83D\uDDBC')
  })

  // `stripUnresolvedImageRefs` matches the grammar, not real user files, so
  // ordinary prose that happens to look like a reference is rewritten too. It
  // is now only reachable from the read-only `parseMarkdown` preview, where the
  // result is never saved back, so this is a display wart rather than data
  // loss. Pinned so a future caller on a save path is noticed.
  test('rewrites prose that merely looks like a reference (display only)', () => {
    const prose = 'Use ![the flag][max_retries.conf] here'

    expect(stripUnresolvedImageRefs(prose)).toBe(
      'Use \uD83D\uDDBC\uFE0E the flag here'
    )
  })
})

describe('a realtime update that arrives while a cell is open', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  // The editable editor stopped tracking `modelValue`, so the mounted document
  // no longer reflects a value another user saved.
  test('is reflected in an editable editor', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: 'original',
        enableRichTextFormatting: true,
        editable: true,
      },
      global: { stubs: EDITOR_STUBS },
    })
    await wrapper.setProps({ modelValue: 'newer from another user' })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.serializeToMarkdown()).toBe('newer from another user')
  })

  // The incoming value sets `hasEdits` through the `richCopy` watcher even
  // though the user typed nothing, so `beforeSave()` serializes the stale
  // editor and saves it over the newer text.
  test('is not overwritten when the cell is closed without typing', async () => {
    const wrapper = await testApp.mount(GridViewFieldRichText, {
      props: {
        field: {
          id: 1,
          name: 'Notes',
          type: 'long_text',
          long_text_enable_rich_text: true,
        },
        value: 'original',
        selected: true,
        readOnly: false,
        storePrefix: 'page/',
        workspaceId: 1,
      },
      global: { stubs: EDITOR_STUBS },
    })

    // Open the cell without typing. The inline editor only mounts once
    // `opened` is true.
    wrapper.vm.editing = true
    wrapper.vm.opened = true
    await wrapper.vm.$nextTick()
    await new Promise((resolve) => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    // Another user's update arrives.
    await wrapper.setProps({ value: 'newer from another user' })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.beforeSave()).toBe('newer from another user')
  })
})
