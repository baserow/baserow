<template>
  <BubbleMenu
    v-if="editor"
    class="rich-text-editor__menu-container"
    :editor="editor"
    :plugin-key="pluginKey"
    :append-to="appendTo"
    :should-show="shouldShowMenu"
    :update-delay="0"
    :resize-delay="0"
    :options="menuOptions"
  >
    <div>
      <div v-if="editLink" class="rich-text-editor__bubble-menu">
        <div class="rich-text-editor__bubble-menu-link-edit">
          <input
            ref="linkInput"
            v-model="editLinkValue"
            class="rich-text-editor__bubble-menu-link-edit-input"
            :placeholder="$t('richTextEditorBubbleMenu.linkEditPlaceholder')"
            @keyup.enter="setLink"
          />

          <button
            v-if="editor.getAttributes('link').href"
            class="rich-text-editor__bubble-menu-link-edit-delete"
            @click.stop.prevent="deleteLink"
          >
            <i class="iconoir-cancel"></i>
          </button>
        </div>
        <button
          class="rich-text-editor__bubble-menu-link-edit-set"
          :class="{
            'rich-text-editor__bubble-menu-link-edit-set--disabled':
              editLinkValue === '',
          }"
          :disabled="editLinkValue === ''"
          @click.stop.prevent="setLink"
        >
          {{ $t('richTextEditorBubbleMenu.linkEditDone') }}
        </button>
      </div>
      <div v-else-if="shouldShowLink()" class="rich-text-editor__bubble-menu">
        <div class="rich-text-editor__bubble-menu-link-show">
          <div class="rich-text-editor__bubble-menu-link-show-href">
            <a
              :href="editor.getAttributes('link').href"
              rel="noopener noreferrer nofollow"
              target="_blank"
            >
              {{ editor.getAttributes('link').href }}
            </a>
          </div>
          <button
            class="rich-text-editor__bubble-menu-link-show-button"
            @click.stop.prevent="showEditLinkInput"
          >
            <i class="iconoir-edit-pencil"></i>
          </button>
          <button
            class="rich-text-editor__bubble-menu-link-show-button"
            @click.stop.prevent="deleteLink"
          >
            <i class="iconoir-bin"></i>
          </button>
        </div>
      </div>
      <ul v-else class="rich-text-editor__bubble-menu">
        <li
          :title="$t('richTextEditorBubbleMenu.bold')"
          class="rich-text-editor__bubble-menu-button"
        >
          <button
            :class="{ 'is-active': editor.isActive('bold') }"
            @click.stop.prevent="toggleMark('bold')"
          >
            <i class="iconoir-bold"></i>
          </button>
        </li>
        <li
          :title="$t('richTextEditorBubbleMenu.italic')"
          class="rich-text-editor__bubble-menu-button"
        >
          <button
            :class="{ 'is-active': editor.isActive('italic') }"
            @click.stop.prevent="toggleMark('italic')"
          >
            <i class="iconoir-italic"></i>
          </button>
        </li>
        <li
          :title="$t('richTextEditorBubbleMenu.underline')"
          class="rich-text-editor__bubble-menu-button"
        >
          <button
            :class="{ 'is-active': editor.isActive('underline') }"
            @click.stop.prevent="toggleMark('underline')"
          >
            <i class="iconoir-underline"></i>
          </button>
        </li>
        <li
          :title="$t('richTextEditorBubbleMenu.strikethrough')"
          class="rich-text-editor__bubble-menu-button"
        >
          <button
            :class="{ 'is-active': editor.isActive('strike') }"
            @click.stop.prevent="toggleMark('strike')"
          >
            <i class="iconoir-strikethrough"></i>
          </button>
        </li>
        <li
          :title="$t('richTextEditorBubbleMenu.link')"
          class="rich-text-editor__bubble-menu-button"
        >
          <button
            :class="{ 'is-active': editor.isActive('link') }"
            @click.stop.prevent="showEditLinkInput"
          >
            <i class="iconoir-link"></i>
          </button>
        </li>
      </ul>
    </div>
  </BubbleMenu>
</template>

<script>
import { BubbleMenu } from '@tiptap/vue-3/menus'
import { isElement } from '@baserow/modules/core/utils/dom'

export default {
  name: 'RichTextEditorBubbleMenu',
  components: {
    BubbleMenu,
  },
  props: {
    editor: {
      type: Object,
      required: false,
      default: null,
    },
    visible: {
      type: Boolean,
      default: true,
    },
    pluginKey: {
      type: [String, Object],
      default: 'inlineBubbleMenu',
    },
    appendTo: {
      type: [Object, Function],
      default: undefined,
    },
    scrollTarget: {
      type: Object,
      default: null,
    },
  },
  data() {
    return {
      editLink: false,
      editLinkValue: '',
      unsetLinkMarkHandler: null,
    }
  },
  computed: {
    menuOptions() {
      const opts = {
        strategy: 'fixed',
        placement: 'top',
        offset: 5,
      }
      if (this.scrollTarget) {
        opts.scrollTarget = this.scrollTarget
      }
      return opts
    },
  },
  watch: {
    visible(value) {
      if (!value) {
        this.editLink = false
      }
    },
  },
  mounted() {
    // if the space key or escape is pressed, we should unselect the link.
    this.unsetLinkMarkHandler = (event) => {
      if (
        this.editor?.isActive('link') &&
        (event.key === ' ' || event.key === 'Escape')
      ) {
        this.unselectLink()
      }
    }
    this.$el.addEventListener('keyup', this.unsetLinkMarkHandler)
  },
  beforeUnmount() {
    if (this.unsetLinkMarkHandler) {
      this.$el.removeEventListener('keyup', this.unsetLinkMarkHandler)
    }
  },
  methods: {
    shouldShowMenu({ editor, view, element }) {
      if (!this.visible) return false

      const isChildOfMenu = element.contains(document.activeElement)
      const hasEditorFocus = view.hasFocus() || isChildOfMenu

      if (!hasEditorFocus || !editor.isEditable) {
        return false
      }

      if (editor.isActive('image')) {
        return false
      }

      const emptySelection = editor.state.selection.empty
      const codeBlockActive = editor.isActive('codeBlock')
      const linkMarkActive = editor.isActive('link')

      return (!emptySelection && !codeBlockActive) || linkMarkActive
    },
    toggleMark(type) {
      if (!this.editor) {
        return
      }

      const chain = this.editor.chain().focus()

      switch (type) {
        case 'bold':
          chain.toggleBold()
          break
        case 'italic':
          chain.toggleItalic()
          break
        case 'underline':
          chain.toggleUnderline()
          break
        case 'strike':
          chain.toggleStrike()
          break
      }

      chain.run()
    },
    isEventTargetInside(event) {
      return (
        isElement(this.$el, event.target) ||
        isElement(this.$el, event.relatedTarget) ||
        // Safari set the relatedTarget to the tippyjs popover that contains this.$el,
        // but since we cannot access it by reference, try inverting the check.
        isElement(event.relatedTarget, this.$el)
      )
    },
    shouldShowLink() {
      return (
        this.editor.isActive('link') &&
        this.editor.state.selection.empty === true
      )
    },
    unselectLink() {
      const { to } = this.editor.state.selection
      this.editor.commands.setTextSelection({ from: to, to })
      this.editor.commands.unsetMark('link')
      this.editLink = false
      this.editLinkValue = ''
    },
    showEditLinkInput() {
      const { from, to } = this.editor.state.selection
      const selectedText = this.editor.state.doc.textBetween(from, to)
      this.editLinkValue =
        this.editor.getAttributes('link').href || selectedText
      this.editLink = true
      this.$nextTick(() => this.$refs.linkInput.select())
    },
    prependDefaultProtocolIfNeeded(href) {
      if (href.startsWith('http://') || href.startsWith('https://')) {
        return href
      }

      const linkExtension = this.editor.extensionManager.extensions.find(
        (extension) => extension.name === 'link'
      )
      for (const protocol of linkExtension.options.protocols) {
        const scheme =
          protocol.scheme + (!protocol.optionalSlashes ? '://' : '')
        if (href.startsWith(scheme)) {
          return href
        }
      }

      return `https://${href}`
    },
    setLink() {
      const href = this.prependDefaultProtocolIfNeeded(this.editLinkValue)
      this.editor
        .chain()
        .focus()
        .extendMarkRange('link')
        .setLink({ href })
        .run()
      this.unselectLink()
    },
    deleteLink() {
      this.editor.chain().focus().unsetLink().run()
      this.unselectLink()
    },
  },
}
</script>
