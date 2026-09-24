<template>
  <div
    ref="root"
    class="rich-text-editor"
    :class="{ 'rich-text-editor--scrollbar-thin': thinScrollbar }"
    @drop.prevent
    @dragover.prevent
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
import { GapCursor } from '@tiptap/pm/gapcursor'
import { NodeSelection } from '@tiptap/pm/state'

import RichTextEditorBubbleMenu from '@baserow/modules/core/components/editor/RichTextEditorBubbleMenu'
import RichTextEditorFloatingMenu from '@baserow/modules/core/components/editor/RichTextEditorFloatingMenu'
import { EnterStopEditExtension } from '@baserow/modules/core/editor/enterStopEditExtension'
import {
  createPlainTextEditorExtensions,
  createRichTextEditorExtensions,
  parseMarkdownClipboard,
} from '@baserow/modules/core/editor/richTextExtensions'
import { createMention } from '@baserow/modules/core/editor/mention'
import {
  decodeQuotedGridCell,
  isRichTextEditorClipboard,
  plainTextToRichTextContent,
} from '@baserow/modules/core/editor/richTextClipboard'
import { isRichTextSelectionVisible } from '@baserow/modules/core/editor/richTextMenuPosition'
import {
  isRenderableUserFile,
  stripImageUrls,
  sanitizeUploadFileName,
  imageUploadType,
  isImageUploadCandidate,
} from '@baserow/modules/core/editor/richTextImageUtils'
import {
  isTrustedImageUrl,
  registerTrustedImageUrl,
  registerTrustedImageUrlsFromMarkdown,
} from '@baserow/modules/core/editor/trustedImageUrls'
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
    // Adds the image node. Off by default so comments, form descriptions and
    // row history keep rendering image markdown as text.
    enableImages: {
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
    clipboardMarkdownResolver: {
      type: Function,
      default: null,
    },
    uploadFile: {
      type: Function,
      default: null,
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
      return (
        this.editable &&
        this.enableRichTextFormatting &&
        this.enableImages &&
        !!this.uploadFile
      )
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
    enableImages() {
      this.teardownEditor()
      this.createEditor()
    },
    modelValue(value) {
      // Values this editor emitted itself come back through `modelValue`.
      // Reloading those would reset the selection on every keystroke, so they
      // are ignored. Anything else is an external change (a realtime update,
      // or the parent swapping the value) and must reach the document, even
      // while editing: keeping a stale document lets a later save serialize it
      // over the newer value.
      if (_.isEqual(value, this.lastEmittedValue)) {
        return
      }
      if (!_.isEqual(value, this.editor.getJSON())) {
        this.loadContent(value, { preserveSelection: this.editable })
      }
    },
  },
  created() {
    // Not reactive: this is bookkeeping for in-flight uploads, and the
    // `editable`/`enableImages` watchers can tear the editor down before
    // `mounted` runs.
    this._activeUploads = new Set()
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
      // Cancels every in-flight upload, not just the most recent one.
      this._activeUploads.forEach((upload) => {
        upload.cancelled = true
      })
      this._activeUploads.clear()
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
            enableImages: this.enableImages,
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
      const content = this.modelValue
      this.registerTrustedImageUrls(content)
      // The new editor has emitted nothing yet, so an echo remembered from the
      // previous one must not suppress the next external update.
      this.lastEmittedValue = null
      this.editor = new Editor({
        content,
        contentType: this.getContentType(this.modelValue),
        editable: this.editable,
        editorProps: {
          // Open links in a new tab when the user clicks on them while holding Cmd/Ctrl.
          handleClickOn: (view, pos, node, nodePos, event, direct) => {
            if (
              isActive(view.state, 'link') &&
              isOsSpecificModifierPressed(event)
            ) {
              window.open(this.editor.getAttributes('link').href, '_blank')
              event.preventDefault()
              return true
            }
          },
          handleDrop: (view, event) => {
            if (!this.canUploadImages || !event.dataTransfer) {
              return false
            }
            const files = Array.from(event.dataTransfer.files).filter(
              isImageUploadCandidate
            )
            if (files.length === 0) {
              return false
            }
            event.preventDefault()
            const dropPos = view.posAtCoords({
              left: event.clientX,
              top: event.clientY,
            })
            this.uploadFiles(files, dropPos?.pos ?? null)
            return true
          },
          handlePaste: (view, event) => {
            const plainText = event.clipboardData.getData('text/plain')
            // "Copy image" in a browser, or copying a picture out of an office
            // document, puts the image file on the clipboard next to a
            // `text/html` `<img>` pointing at a host we will not load from. The
            // file is what the user means, so `text/html` alone does not turn
            // this into a text paste; only real plain text does.
            if (this.canUploadImages && !plainText.trim()) {
              const items = event.clipboardData?.items
                ? Array.from(event.clipboardData.items)
                : []
              const files = items
                .filter((item) => item.kind !== 'string')
                .map((item) => item.getAsFile())
                .filter(isImageUploadCandidate)
              if (files.length > 0) {
                // Like a drop, the image lands where it was pasted, not
                // wherever the selection is when the upload finishes. A
                // selection is replaced, as any paste would.
                if (!view.state.selection.empty) {
                  view.dispatch(view.state.tr.deleteSelection())
                }
                this.uploadFiles(files, view.state.selection.from)
                return true
              }
            }
            const copiedFromRichTextEditor =
              this.enableRichTextFormatting &&
              isRichTextEditorClipboard(plainText)
            const resolvedClipboardMarkdown =
              this.enableRichTextFormatting &&
              !copiedFromRichTextEditor &&
              this.clipboardMarkdownResolver
                ? this.clipboardMarkdownResolver(plainText)
                : null
            if (typeof resolvedClipboardMarkdown === 'string') {
              const slice = parseMarkdownClipboard(
                this.editor,
                resolvedClipboardMarkdown,
                false
              )
              view.dispatch(
                view.state.tr.replaceSelection(slice).scrollIntoView()
              )
              return true
            }
            const gridCellText = copiedFromRichTextEditor
              ? null
              : decodeQuotedGridCell(plainText)
            const plainTextWithBlankLines =
              this.enableRichTextFormatting &&
              !copiedFromRichTextEditor &&
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
          const json = clone(this.editor.getJSON())
          // Remembered so the `modelValue` watcher can tell this echo apart
          // from an externally changed value.
          this.lastEmittedValue = json
          this.$emit('update:modelValue', json)
        },
        onFocus: ({ editor, event }) => {
          this.bubbleMenuVisible = true
          this.floatingMenuVisible = true
          this.setMenuScrollVisibility(true)
          this.$emit('focus')
        },
        onBlur: ({ editor, event }) => {
          // Do not emit a blur event if it is coming from one of the editor's menu.
          if (this.isEventFromMenu(event)) {
            return
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
      // `end` selects a trailing block image as a node, so the first keystroke
      // would replace it. Put a gap cursor after it instead.
      const { state, view } = this.editor
      if (state.selection instanceof NodeSelection) {
        const $after = state.doc.resolve(state.selection.to)
        if (GapCursor.valid($after)) {
          view.dispatch(state.tr.setSelection(new GapCursor($after)))
        }
      }
    },
    serializeToMarkdown() {
      // A URL the editor didn't get from Baserow (pasted) would load in the optimistic preview.
      return this.enableRichTextFormatting
        ? stripImageUrls(this.editor.getMarkdown(), isTrustedImageUrl)
        : this.editor.getText({ blockSeparator: '\n' })
    },
    isDirty() {
      return !_.isEqual(this.editor.getJSON(), this.initialDocument)
    },
    /**
     * Replaces the document with ``value``. When ``preserveSelection`` is set
     * the caret is restored afterwards, so an external update landing while the
     * user is typing does not send the cursor back to the start. The offset is
     * clamped because the new document can be shorter than the old one.
     */
    loadContent(value, { preserveSelection = false } = {}) {
      const previousSelection = preserveSelection
        ? this.editor.state.selection.anchor
        : null
      this.registerTrustedImageUrls(value)
      this.editor.commands.setContent(value, {
        emitUpdate: false,
        contentType: this.getContentType(value),
      })
      if (previousSelection !== null) {
        const size = this.editor.state.doc.content.size
        this.editor.commands.setTextSelection(
          Math.min(previousSelection, Math.max(size - 1, 0))
        )
      }
      this.initialDocument = clone(this.editor.getJSON())
    },
    /**
     * A Markdown value handed to the editor comes from the backend, which
     * resolved every `![alt][name](url)` itself, so those URLs may be loaded.
     */
    registerTrustedImageUrls(value) {
      if (this.enableImages && typeof value === 'string') {
        registerTrustedImageUrlsFromMarkdown(value)
      }
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
    addImages(imageFiles, insertPos = null) {
      const validImages = []
      for (const image of imageFiles) {
        if (isRenderableUserFile(image)) {
          validImages.push(image)
        } else {
          this.$store.dispatch('toast/error', {
            title: this.$t('richTextEditor.errorUnsupportedImageTitle'),
            message: this.$t('richTextEditor.errorUnsupportedImageMessage', {
              name: image.original_name,
            }),
          })
        }
      }
      for (const image of validImages) {
        // The URL comes from the upload response, so it is safe to load.
        registerTrustedImageUrl(image.url)
        const chain = this.editor.chain()
        if (insertPos != null) {
          chain.focus(insertPos)
        }
        chain
          .setImage({
            src: image.url,
            alt: image.original_name.replace(/\.[^.]+$/, ''),
            userFileName: image.name,
          })
          .createParagraphNear()
          .run()
      }
    },
    /**
     * Tracks ``pos`` across the document changes that happen while an upload is
     * in flight, so a second drop still inserts where it was dropped after an
     * earlier upload has shifted the document. Returns a getter for the mapped
     * position and a ``dispose`` to stop tracking.
     */
    trackPosition(pos) {
      if (pos == null) {
        return { get: () => null, dispose: () => {} }
      }
      let current = pos
      const onTransaction = ({ transaction }) => {
        if (transaction.docChanged) {
          current = transaction.mapping.map(current)
        }
      }
      this.editor.on('transaction', onTransaction)
      return {
        get: () => current,
        set: (pos) => {
          current = pos
        },
        dispose: () => this.editor?.off('transaction', onTransaction),
      }
    },
    /**
     * The stored reference is `![alt][<name>_<hash>.<ext>]`, and the backend
     * derives `<ext>` from the uploaded name. Characters the reference cannot
     * carry in the extension (`photo.png)`) are dropped so the image does not
     * lose its reference after saving.
     */
    sanitizeUploadFile(file) {
      const name = file?.name
      if (typeof name !== 'string') {
        return file
      }
      const cleanName = sanitizeUploadFileName(name)
      const type = imageUploadType(file) || file.type
      return cleanName === name && type === file.type
        ? file
        : new File([file], cleanName, { type })
    },
    async uploadFiles(fileArray, insertPos = null) {
      if (!this.canUploadImages) {
        return
      }

      // Each call owns its cancellation state: a shared flag would let one
      // finishing or cancelled drop abort the uploads of another.
      const upload = { cancelled: false }
      this._activeUploads.add(upload)

      const tracked = this.trackPosition(insertPos)

      const files = fileArray.map((file) => ({
        id: uuid(),
        file: this.sanitizeUploadFile(file),
      }))

      // First add the file ids to the loading list so the user sees a visual loading
      // indication for each file.
      files.forEach((file) => {
        this.loadings.push({ id: file.id })
      })

      // Now upload the files one by one to not overload the backend. When finished,
      // regardless of if it has succeeded, the loading state for that file can be
      // removed because it has already been added as a file.
      const useTrackedPos = insertPos != null
      try {
        for (const fileObj of files) {
          const id = fileObj.id
          const file = fileObj.file

          if (upload.cancelled) {
            break
          }

          try {
            const { data } = await this.uploadFile(file)
            if (!this.editor || this.editor.isDestroyed || upload.cancelled) {
              break
            }
            // Mapped through any edit made while this file was uploading.
            this.addImages([data], useTrackedPos ? tracked.get() : null)
            if (useTrackedPos) {
              // The next file of this drop goes right after the image that was
              // just inserted, even if the user moves the cursor meanwhile.
              tracked.set(this.editor.state.selection.from)
            }
          } catch (error) {
            notifyIf(error, 'userFile')
          }

          const index = this.loadings.findIndex((l) => l.id === id)
          if (index !== -1) {
            this.loadings.splice(index, 1)
          }
        }
      } finally {
        tracked.dispose()
        this._activeUploads.delete(upload)
        // Only entries belonging to this call are cleared, so a concurrent
        // upload keeps its own loading indicators.
        this.loadings = this.loadings.filter(
          (l) => !files.some((f) => f.id === l.id)
        )
      }
    },
  },
}
</script>
