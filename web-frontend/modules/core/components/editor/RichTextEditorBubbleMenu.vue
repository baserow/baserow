<template>
  <FloatingMenu
    v-if="editor"
    v-show="visible"
    :editor="editor"
    :should-show="() => true"
    :tippy-options="{
      duration: 250,
      placement: 'top',
      offset: [0, 5],
      appendTo,
    }"
  >
    <div :style="{ visibility: 'visible' }">
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
            @click.stop.prevent="editor.chain().focus().toggleBold().run()"
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
            @click.stop.prevent="editor.chain().focus().toggleItalic().run()"
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
            @click.stop.prevent="editor.chain().focus().toggleUnderline().run()"
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
            @click.stop.prevent="editor.chain().focus().toggleStrike().run()"
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
  </FloatingMenu>
</template>

<script>
import { FloatingMenu } from '@tiptap/vue-2'
import { isElement } from '@baserow/modules/core/utils/dom'

export default {
  name: 'RichTextEditorBubbleMenu',
  components: {
    FloatingMenu,
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
  },
  data() {
    return {
      editLink: false,
      editLinkValue: '',
    }
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
    const unsetLinkMark = (event) => {
      if (
        this.editor.isActive('link') &&
        (event.key === ' ' || event.key === 'Escape')
      ) {
        this.unselectLink()
      }
    }
    this.$el.addEventListener('keyup', unsetLinkMark)
    this.$once('hook:beforeDestroy', () => {
      this.$el.removeEventListener('keyup', unsetLinkMark)
    })
  },
  methods: {
    appendTo() {
      return document.body
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
