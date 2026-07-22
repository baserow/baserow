<template>
  <div class="form-view__description-editor">
    <!--
      Edit mode. The editor is only mounted while editing, so unselected fields
      don't pay the rich-text instantiation cost and no floating menu lingers on
      the form. `model-value` is passed one-way as the initial content; the saved
      value is always read back with serializeToMarkdown() on blur, which avoids
      round-tripping tiptap JSON through the parent and resetting the cursor.
    -->
    <RichTextEditor
      v-if="editing"
      ref="editor"
      :model-value="buffer"
      :editable="true"
      :enable-rich-text-formatting="true"
      :placeholder="placeholder"
      :scrollable-area-element="scrollAreaElement"
      @update:model-value="dirty = true"
      @blur="stopEditing"
    ></RichTextEditor>
    <template v-else>
      <RichTextEditor
        v-if="hasValue"
        class="form-view__description-rendered"
        :model-value="value"
        :editable="false"
        :enable-rich-text-formatting="true"
      ></RichTextEditor>
      <span
        v-else-if="!readOnly"
        class="form-view__description-placeholder"
        @click="edit"
        >{{ placeholder }}</span
      >
      <a v-if="!readOnly" class="form-view__edit" @click="edit">
        <i class="form-view__edit-icon iconoir-edit-pencil"></i>
      </a>
    </template>
  </div>
</template>

<script>
import {
  loadRichTextEditor,
  RichTextEditor,
} from '@baserow/modules/core/components/editor/richTextEditorAsync'

export default {
  name: 'FormViewDescription',
  components: { RichTextEditor },
  props: {
    value: {
      type: String,
      required: false,
      default: '',
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
    // Resolver returning the scrollable preview container, provided by the
    // component that owns it (FormViewPreview) instead of a DOM lookup here.
    getScrollAreaElement: {
      type: Function,
      required: false,
      default: null,
    },
  },
  emits: ['change'],
  data() {
    return {
      editing: false,
      dirty: false,
      // Initial content handed to the editor when entering edit mode.
      buffer: '',
      // Scrolling container of the form preview, so the editor's floating/
      // bubble menu sticks to the cursor line while the page scrolls.
      scrollAreaElement: null,
    }
  },
  computed: {
    hasValue() {
      return (this.value || '').trim().length > 0
    },
  },
  methods: {
    edit() {
      if (this.readOnly) {
        return
      }
      // Resolve the form preview's scroll container so the editor menus track
      // it. When no resolver is provided the editor falls back to its own root.
      this.scrollAreaElement = this.getScrollAreaElement?.() || null
      this.buffer = this.value || ''
      this.dirty = false
      this.editing = true
      loadRichTextEditor().then(() => {
        this.$nextTick(() => {
          this.$refs.editor?.focus()
        })
      })
    },
    stopEditing() {
      // Read the markdown before unmounting the editor. Only save when the
      // content actually changed, so opening and closing a legacy description
      // doesn't rewrite it (markdown serialization can escape stray characters).
      if (this.dirty) {
        const markdown = this.$refs.editor.serializeToMarkdown()
        if (markdown !== (this.value || '')) {
          this.$emit('change', markdown)
        }
      }
      this.editing = false
      this.dirty = false
    },
  },
}
</script>
