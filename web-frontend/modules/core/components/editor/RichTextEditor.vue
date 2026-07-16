<template>
  <div
    ref="root"
    class="rich-text-editor"
    :class="{ 'rich-text-editor--scrollbar-thin': thinScrollbar }"
    @drop.prevent="dropImage($event)"
    @dragover.prevent
    @dragenter.prevent="dragEnter($event)"
    @dragleave="dragLeave($event)"
  >
    <div v-if="editable && enableRichTextFormatting">
      <RichTextEditorBubbleMenu
        ref="bubbleMenu"
        :editor="editor"
        :visible="bubbleMenuVisible"
        :append-to="resolvedMenuContainer"
        :scroll-target="scrollElement"
        :visibility-targets="visibilityElements"
      />
      <RichTextEditorFloatingMenu
        ref="floatingMenu"
        :editor="editor"
        :visible="floatingMenuVisible"
        :append-to="resolvedMenuContainer"
        :scroll-target="scrollElement"
        :visibility-targets="visibilityElements"
      />
    </div>
    <EditorContent
      class="rich-text-editor__content"
      :class="[
        { 'rich-text-editor__content--loading': loadings.length > 0 },
        editorClass,
      ]"
      :editor="editor"
    />
    <div v-if="loadings.length > 0" class="loading-spinner"></div>
  </div>
</template>

<script>
import _ from 'lodash'
import { mapGetters } from 'vuex'
import { Editor, EditorContent } from '@tiptap/vue-3'
import { Placeholder } from '@tiptap/extension-placeholder'
import { isActive } from '@tiptap/core'

import RichTextEditorBubbleMenu from '@baserow/modules/core/components/editor/RichTextEditorBubbleMenu'
import RichTextEditorFloatingMenu from '@baserow/modules/core/components/editor/RichTextEditorFloatingMenu'
import { EnterStopEditExtension } from '@baserow/modules/core/editor/enterStopEditExtension'
import {
  createPlainTextEditorExtensions,
  createRichTextEditorExtensions,
} from '@baserow/modules/core/editor/richTextExtensions'
import { createMention } from '@baserow/modules/core/editor/mention'
import {
  decodeQuotedGridCell,
  plainTextToRichTextContent,
} from '@baserow/modules/core/editor/richTextClipboard'
import { isRichTextSelectionVisible } from '@baserow/modules/core/editor/richTextMenuPosition'
import { isElement } from '@baserow/modules/core/utils/dom'
import { isOsSpecificModifierPressed } from '@baserow/modules/core/utils/events'
import { uuid } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'
import suggestion from '@baserow/modules/core/editor/suggestion'

export default {
  components: {
    EditorContent,
    RichTextEditorBubbleMenu,
    RichTextEditorFloatingMenu,
  },
  props: {
    modelValue: {
      type: [Object, String, null],
      required: true,
    },
    placeholder: {
      type: String,
      default: null,
    },
    editable: {
      type: Boolean,
      default: true,
    },
    editorClass: {
      type: String,
      default: '',
    },
    mentionableUsers: {
      type: [Array, null],
      default: null,
    },
    enterStopEdit: {
      type: Boolean,
      default: false,
    },
    shiftEnterStopEdit: {
      type: Boolean,
      default: false,
    },
    enableRichTextFormatting: {
      type: Boolean,
      default: false,
    },
    scrollableAreaElement: {
      type: [Object, Array, Function],
      default: null,
    },
    thinScrollbar: {
      type: Boolean,
      default: false,
    },
    menuContainer: {
      type: [Object, Function],
      default: undefined,
    },
  },
  emits: ['blur', 'focus', 'update:modelValue', 'stop-edit'],
  data() {
    return {
      editor: null,
      resizeObserver: null,
      bubbleMenuVisible: true,
      floatingMenuVisible: true,
      loadings: [],
      mousedownEvent: null,
      scrollEvent: null,
      scrollElement: null,
      scrollEventElements: [],
      visibilityElements: [],
      scrollAnimationFrame: null,
    }
  },
  computed: {
    ...mapGetters({
      loggedUserId: 'auth/getUserId',
    }),
    canUploadImages() {
      const enableImages = false
      return this.editable && this.enableRichTextFormatting && enableImages
    },
    // Body-level default: floating-ui's fixed strategy mis-positions under a
    // positioned ancestor. Keep the lookup lazy so server rendering never touches
    // the browser-only document global.
    resolvedMenuContainer() {
      return this.menuContainer ?? (() => document.body)
    },
  },
  watch: {
    editable: {
      handler() {
        this.teardownEditor()
        this.createEditor()
      },
    },
    modelValue(value) {
      if (!_.isEqual(value, this.editor.getJSON())) {
        this.editor.commands.setContent(value, {
          emitUpdate: false,
          contentType: this.getContentType(value),
        })
        this.initialDocument = clone(this.editor.getJSON())
      }
    },
  },
  mounted() {
    this.scrollElement = this.getScrollElement()
    this.visibilityElements = this.getVisibilityElements()
    this.scrollEventElements = this.getScrollEventElements()
    this.createEditor()
  },
  beforeUnmount() {
    this.teardownEditor()
  },
  methods: {
    teardownEditor() {
      this.unregisterAutoCollapseFloatingMenuHandler()
      this.unregisterMenuScrollHandlers()
      this.unregisterResizeObserver()
      if (this.editor && !this.editor.isDestroyed) {
        this.editor.destroy()
      }
      this.editor = null
    },
    registerResizeObserver() {
      this.unregisterResizeObserver()
      let lastWidth = null
      let lastHeight = null
      const resizeObserver = new ResizeObserver((entries) => {
        const entry = entries[0]
        if (!entry) return
        const newWidth = entry.contentRect.width
        const newHeight = entry.contentRect.height

        if (lastWidth !== null && lastWidth !== newWidth) {
          this.bubbleMenuVisible = false
        }

        const sizeChanged =
          lastWidth !== null &&
          (lastWidth !== newWidth || lastHeight !== newHeight)
        lastWidth = newWidth
        lastHeight = newHeight

        // Check bounds after resize, deferred so ProseMirror can re-layout
        if (sizeChanged && this.editor && this.scrollElement) {
          requestAnimationFrame(() => {
            if (!this.editor || !this.scrollElement) return
            this.setMenuScrollVisibility(
              isRichTextSelectionVisible(this.editor, this.visibilityElements)
            )
            this.updateMenuPosition()
          })
        }
      })
      resizeObserver.observe(this.$refs.root)
      this.resizeObserver = resizeObserver
    },
    unregisterResizeObserver() {
      if (this.resizeObserver) {
        this.resizeObserver.disconnect()
        this.resizeObserver = null
      }
    },
    getContentType(content) {
      return typeof content === 'string' ? 'markdown' : 'json'
    },
    getConfiguredExtensions() {
      const extensions = this.enableRichTextFormatting
        ? createRichTextEditorExtensions({
            openLinksOnClick: !this.editable,
          })
        : createPlainTextEditorExtensions()

      if (this.enterStopEdit || this.shiftEnterStopEdit) {
        const enterKeyExt = EnterStopEditExtension.configure({
          vueComponent: this,
          shiftKey: this.shiftEnterStopEdit,
        })
        extensions.push(enterKeyExt)
      }

      // If mentionable users are provided, add the mention extension.
      const users = this.mentionableUsers
      if (users !== null) {
        const mentionsExt = createMention({
          loggedUserId: this.loggedUserId,
          suggestion: suggestion({ users }),
          users,
        })
        extensions.push(mentionsExt)
      }

      if (this.placeholder) {
        extensions.push(
          Placeholder.configure({
            placeholder: this.placeholder,
          })
        )
      }
      return extensions
    },
    createEditor() {
      const extensions = this.getConfiguredExtensions()
      this.editor = new Editor({
        content: this.modelValue,
        contentType: this.getContentType(this.modelValue),
        editable: this.editable,
        editorProps: {
          handleClickOn: (view, pos, node, nodePos, event, direct) => {
            // Open links in a new tab when the user clicks on them while holding Cmd/Ctrl..
            if (
              isActive(view.state, 'link') &&
              isOsSpecificModifierPressed(event)
            ) {
              window.open(this.editor.getAttributes('link').href, '_blank')
              event.preventDefault()
              return true
            }
          },
          handlePaste: (view, event) => {
            const plainText = event.clipboardData.getData('text/plain')
            const gridCellText = decodeQuotedGridCell(plainText)
            const plainTextWithBlankLines =
              this.enableRichTextFormatting &&
              !event.clipboardData.getData('text/html') &&
              /\r?\n[\t ]*\r?\n/.test(plainText)
                ? plainText
                : null
            const textToInsert = gridCellText ?? plainTextWithBlankLines
            if (textToInsert !== null) {
              this.editor.commands.insertContent(
                this.enableRichTextFormatting
                  ? plainTextToRichTextContent(textToInsert)
                  : textToInsert
              )
              return true
            }
            return false
          },
        },
        extensions,
        onUpdate: () => {
          this.$emit('update:modelValue', clone(this.editor.getJSON()))
        },
        onFocus: ({ editor, event }) => {
          this.bubbleMenuVisible = true
          this.floatingMenuVisible = true
          this.setMenuScrollVisibility(true)
          this.$emit('focus')
        },
        onBlur: ({ editor, event }) => {
          if (this.isEventFromMenu(event)) {
            return // Do not emit a blur event if it is coming from one of the editor's menu.
          }
          this.$emit('blur')
        },
        onSelectionUpdate: () => {
          if (!this.editable || !this.enableRichTextFormatting) {
            return
          }
          this.bubbleMenuVisible = true
          this.floatingMenuVisible = true
          this.setMenuScrollVisibility(true)
        },
      })
      this.initialDocument = clone(this.editor.getJSON())
      this.setupEditor()
    },
    setupEditor() {
      if (this.editable) {
        this.registerResizeObserver()
        this.registerAutoCollapseFloatingMenuHandler()
        this.registerMenuScrollHandlers()
      } else {
        this.unregisterAutoCollapseFloatingMenuHandler()
        this.unregisterMenuScrollHandlers()
        this.unregisterResizeObserver()
      }
    },
    registerAutoCollapseFloatingMenuHandler() {
      this.unregisterAutoCollapseFloatingMenuHandler()
      this.mousedownEvent = (event) => {
        if (this.$refs.floatingMenu?.isEventTargetInside(event)) {
          return
        }
        this.$refs.floatingMenu?.collapse()
      }
      this.$refs.root.addEventListener('mousedown', this.mousedownEvent)
    },
    unregisterAutoCollapseFloatingMenuHandler() {
      if (this.mousedownEvent !== null) {
        this.$refs.root?.removeEventListener('mousedown', this.mousedownEvent)
        this.mousedownEvent = null
      }
    },
    getScrollElement() {
      return this.getConfiguredScrollElements()[0] ?? this.$refs.root
    },
    getConfiguredScrollElements() {
      const configured =
        typeof this.scrollableAreaElement === 'function'
          ? this.scrollableAreaElement()
          : this.scrollableAreaElement
      return (Array.isArray(configured) ? configured : [configured]).filter(
        Boolean
      )
    },
    getVisibilityElements() {
      return [
        ...new Set([this.$refs.root, ...this.getConfiguredScrollElements()]),
      ]
    },
    getScrollEventElements() {
      const elements = []
      let element = this.$refs.root
      while (element) {
        elements.push(element)
        element = element.parentElement
      }
      elements.push(window)
      return [...new Set(elements)]
    },
    setMenuScrollVisibility(visible) {
      const floatingEl = this.$refs.floatingMenu?.$el
      const bubbleEl = this.$refs.bubbleMenu?.$el
      if (floatingEl) floatingEl.style.visibility = visible ? '' : 'hidden'
      if (bubbleEl) bubbleEl.style.visibility = visible ? '' : 'hidden'
    },
    updateMenuPosition() {
      if (!this.editor) return
      const transaction = this.editor.state.tr
        .setMeta('inlineBubbleMenu', 'updatePosition')
        .setMeta('floatingBlockMenu', 'updatePosition')
      this.editor.view.dispatch(transaction)
    },
    registerMenuScrollHandlers() {
      this.unregisterMenuScrollHandlers()
      this.scrollEvent = () => {
        if (this.scrollAnimationFrame !== null) return
        this.scrollAnimationFrame = requestAnimationFrame(() => {
          this.scrollAnimationFrame = null
          if (!this.editor) return
          this.setMenuScrollVisibility(
            isRichTextSelectionVisible(this.editor, this.visibilityElements)
          )
          this.updateMenuPosition()
        })
      }

      this.scrollEventElements.forEach((element) =>
        element.addEventListener('scroll', this.scrollEvent)
      )
    },
    unregisterMenuScrollHandlers() {
      if (this.scrollEvent !== null) {
        this.scrollEventElements.forEach((element) =>
          element.removeEventListener('scroll', this.scrollEvent)
        )
        this.scrollEvent = null
      }
      if (this.scrollAnimationFrame !== null) {
        cancelAnimationFrame(this.scrollAnimationFrame)
        this.scrollAnimationFrame = null
      }
    },
    focus() {
      this.editor.commands.focus('end')
    },
    serializeToMarkdown() {
      return this.enableRichTextFormatting
        ? this.editor.getMarkdown()
        : this.editor.getText({ blockSeparator: '\n' })
    },
    isDirty() {
      return !_.isEqual(this.editor.getJSON(), this.initialDocument)
    },
    isEventFromMenu(event) {
      return (
        this.$refs.bubbleMenu?.isEventTargetInside(event) ||
        this.$refs.floatingMenu?.isEventTargetInside(event)
      )
    },
    isEventTargetInside(event) {
      return (
        isElement(this.$refs.root, event.target) || this.isEventFromMenu(event)
      )
    },
    addImages(imageFiles) {
      for (const image of imageFiles) {
        this.editor.commands.setImage({
          src: image.url,
          alt: image.original_name.split('.')[0],
        })
      }
    },
    async dropImage(event) {
      const files = [...event.dataTransfer.items].map((item) =>
        item.getAsFile()
      )
      const images = files.filter((file) => file?.type.startsWith('image/'))
      if (images.length === 0) {
        return
      }
      await this.uploadFiles(images)
    },
    async uploadFiles(fileArray) {
      this.dragging = false

      if (!this.canUploadImages) {
        return
      }

      const files = fileArray.map((file) => ({ id: uuid(), file }))

      // First add the file ids to the loading list so the user sees a visual loading
      // indication for each file.
      files.forEach((file) => {
        this.loadings.push({ id: file.id })
      })

      // Now upload the files one by one to not overload the backend. When finished,
      // regardless of is has succeeded, the loading state for that file can be removed
      // because it has already been added as a file.
      for (const fileObj of files) {
        const id = fileObj.id
        const file = fileObj.file

        // FIXME: provide uploadUserFile as prop
        try {
          const { data } = await this.uploadUserFile(file)
          this.addImages([data])
        } catch (error) {
          notifyIf(error, 'userFile')
        }

        const index = this.loadings.findIndex((l) => l.id === id)
        this.loadings.splice(index, 1)
      }
    },
    dragEnter(event) {
      if (!this.canUploadImages) {
        return
      }
      this.dragging = true
      this.dragTarget = event.target
    },
    dragLeave(event) {
      if (this.dragTarget === event.target && !this.canUploadImages) {
        event.stopPropagation()
        event.preventDefault()
        this.dragging = false
        this.dragTarget = null
      }
    },
  },
}
</script>
