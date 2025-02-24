<template>
  <div
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
      />
      <RichTextEditorFloatingMenu
        ref="floatingMenu"
        :editor="editor"
        :visible="floatingMenuVisible"
        :get-scrollable-area-bounding-rect="scrollableAreaBoundingRect"
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
import { Editor, EditorContent } from '@tiptap/vue-2'
import { Placeholder } from '@tiptap/extension-placeholder'
import { Mention } from '@baserow/modules/core/editor/mention'
import { Document } from '@tiptap/extension-document'
import { Paragraph } from '@tiptap/extension-paragraph'
import { HardBreak } from '@tiptap/extension-hard-break'
import { Heading } from '@tiptap/extension-heading'
import { ListItem } from '@tiptap/extension-list-item'
import { BulletList } from '@tiptap/extension-bullet-list'
import { OrderedList } from '@tiptap/extension-ordered-list'
import { Bold } from '@tiptap/extension-bold'
import { Italic } from '@tiptap/extension-italic'
import { Strike } from '@tiptap/extension-strike'
import { Link } from '@tiptap/extension-link'
import { Underline } from '@tiptap/extension-underline'
import { Subscript } from '@tiptap/extension-subscript'
import { Superscript } from '@tiptap/extension-superscript'
import { Blockquote } from '@tiptap/extension-blockquote'
import { CodeBlock } from '@tiptap/extension-code-block'
import { HorizontalRule } from '@tiptap/extension-horizontal-rule'
import { TaskItem } from '@tiptap/extension-task-item'
import { TaskList } from '@tiptap/extension-task-list'
import { Text } from '@tiptap/extension-text'
import { Dropcursor } from '@tiptap/extension-dropcursor'
import { Gapcursor } from '@tiptap/extension-gapcursor'
import { History } from '@tiptap/extension-history'
import { mergeAttributes, isActive } from '@tiptap/core'

import { Markdown } from 'tiptap-markdown'

import RichTextEditorBubbleMenu from '@baserow/modules/core/components/editor/RichTextEditorBubbleMenu'
import RichTextEditorFloatingMenu from '@baserow/modules/core/components/editor/RichTextEditorFloatingMenu'
import { EnterStopEditExtension } from '@baserow/modules/core/editor/enterStopEditExtension'
import { ScalableImage } from '@baserow/modules/core/editor/image'
import { isElement } from '@baserow/modules/core/utils/dom'
import { isOsSpecificModifierPressed } from '@baserow/modules/core/utils/events'
import { uuid } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import suggestion from '@baserow/modules/core/editor/suggestion'

const richTextEditorExtensions = ({
  openLinksOnClick = false,
  enableImages = false,
}) => {
  const extensions = [
    // Nodes
    Heading.configure({ levels: [1, 2, 3] }),
    ListItem,
    OrderedList,
    BulletList,
    CodeBlock,
    Blockquote,
    HorizontalRule,
    TaskItem,
    TaskList,
    // Marks
    Bold,
    Italic,
    Strike,
    Underline,
    Subscript,
    Superscript,
    Link.configure({
      protocols: [
        { scheme: 'ftp' },
        { scheme: 'mailto', optionalSlashes: true },
        { scheme: 'tel', optionalSlashes: true },
      ],
      autolink: false,
      openOnClick: openLinksOnClick,
    }),
    // Extensions
    Markdown.configure({
      html: false,
      breaks: true,
      transformPastedText: true,
      transformCopiedText: true,
    }),
    History,
  ]
  if (enableImages) {
    extensions.push(...[ScalableImage, Dropcursor, Gapcursor])
  }
  return extensions
}

export default {
  components: {
    EditorContent,
    RichTextEditorBubbleMenu,
    RichTextEditorFloatingMenu,
  },
  props: {
    value: {
      type: [Object, String],
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
      type: Object,
      default: null,
    },
    thinScrollbar: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      editor: null,
      resizeObserver: null,
      bubbleMenuVisible: false,
      floatingMenuVisible: false,
      loadings: [],
    }
  },
  computed: {
    ...mapGetters({
      loggedUserId: 'auth/getUserId',
    }),
    scrollableAreaBoundingRect() {
      if (this.scrollableAreaElement !== null) {
        return this.scrollableAreaElement.getBoundingClientRect()
      }
      return () => this.$el.getBoundingClientRect()
    },
    canUploadImages() {
      const enableImages = false
      return this.editable && this.enableRichTextFormatting && enableImages
    },
  },
  watch: {
    editable: {
      handler(editable) {
        this.editor.destroy()
        this.createEditor()
      },
    },
    value(value) {
      if (!_.isEqual(value, this.editor.getJSON())) {
        this.editor.commands.setContent(value, false)
      }
    },
  },
  mounted() {
    this.createEditor()
  },
  unmount() {
    if (this.editor) {
      this.editor.destroy()
    }
    this.unregisterResizeObserver()
  },
  methods: {
    registerResizeObserver() {
      const resizeObserver = new ResizeObserver(() => {
        this.$refs.floatingMenu?.updateReferenceClientRect()
        this.bubbleMenuVisible = false
      })
      resizeObserver.observe(this.$el)
      this.resizeObserver = resizeObserver
    },
    unregisterResizeObserver() {
      if (this.resizeObserver) {
        this.resizeObserver.disconnect()
        this.resizeObserver = null
      }
    },
    getConfiguredExtensions() {
      // Base extensions that are always enabled.
      const extensions = [Document, Paragraph, Text, HardBreak]

      if (this.enableRichTextFormatting) {
        extensions.push(
          ...richTextEditorExtensions({
            openLinksOnClick: !this.editable,
          })
        )
      }

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
        const users = this.mentionableUsers
        const renderHTML = this.renderHTMLMention()
        const mentionsExt = Mention.configure({
          renderHTML,
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
        content: this.value,
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
            if (plainText.startsWith('"') && plainText.endsWith('"')) {
              const cleanText = plainText.slice(1, -1)
              this.editor.commands.insertContent(cleanText)
              return true
            }
            return false
          },
        },
        extensions,
        onUpdate: () => {
          this.$emit('input', this.editor.getJSON())
        },
        onFocus: ({ editor, event }) => {
          if (this.editable && !this.bubbleMenuVisible) {
            this.floatingMenuVisible = true
          }
          this.$emit('focus')
        },
        onBlur: ({ editor, event }) => {
          if (this.isEventFromMenu(event)) {
            return // Do not emit a blur event if it is coming from one of the editor's menu.
          }

          this.bubbleMenuVisible = false
          this.floatingMenuVisible = false
          this.$emit('blur')
        },
        onSelectionUpdate: ({ editor }) => {
          if (!this.editable || !this.enableRichTextFormatting) {
            return
          }

          const emptySelection = editor.state.selection.empty === true
          const codeBlockActive = editor.isActive('codeBlock')
          const linkMarkActive = editor.isActive('link')

          if (editor.isActive('image')) {
            this.bubbleMenuVisible = false
            this.floatingMenuVisible = false
          } else if ((!emptySelection && !codeBlockActive) || linkMarkActive) {
            this.bubbleMenuVisible = true
            this.floatingMenuVisible = false
          } else {
            this.bubbleMenuVisible = false
            this.floatingMenuVisible = true
          }
        },
      })
      this.setupEditor()
    },
    setupEditor() {
      if (this.editable) {
        this.floatingMenuVisible = true

        this.registerResizeObserver()
        this.registerAutoCollapseFloatingMenuHandler()
        this.registerAutoHideBubbleMenuHandler()
      } else {
        this.unregisterResizeObserver()
      }
    },
    registerAutoCollapseFloatingMenuHandler() {
      const $refs = this.$refs

      const handler = () => {
        $refs.floatingMenu?.collapse()
      }

      this.$el.addEventListener('mousedown', handler)
      this.$once('hook:unmounted', () => {
        this.$el.removeEventListener('mousedown', handler)
      })
    },
    registerAutoHideBubbleMenuHandler() {
      const _this = this

      const handler = (event) => {
        _this.bubbleMenuVisible = false
      }

      const elem = this.scrollableAreaElement ?? this.$el

      elem.addEventListener('scroll', handler)
      this.$once('hook:unmounted', () => {
        elem.removeEventListener('scroll', handler)
      })
    },
    renderHTMLMention() {
      const loggedUserId = this.loggedUserId
      const isUserInWorkspace = (userId) =>
        this.mentionableUsers.some((user) => user.user_id === userId)

      return ({ node, options }) => {
        let className = 'rich-text-editor__mention'
        const userId = parseInt(node.attrs.id)
        if (userId === loggedUserId) {
          className += ' rich-text-editor__mention--current-user'
        } else if (!isUserInWorkspace(userId)) {
          className += ' rich-text-editor__mention--user-gone'
        }
        return [
          'span',
          mergeAttributes({ class: className }, this.HTMLAttributes),
          `@${node.attrs.label ?? node.attrs.id}`,
        ]
      }
    },
    focus() {
      this.editor.commands.focus('end')
    },
    serializeToMarkdown() {
      return this.editor.storage.markdown.getMarkdown()
    },
    isEventFromMenu(event) {
      return (
        this.$refs.bubbleMenu?.isEventTargetInside(event) ||
        this.$refs.floatingMenu?.isEventTargetInside(event)
      )
    },
    isEventTargetInside(event) {
      return isElement(this.$el, event.target) || this.isEventFromMenu(event)
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
