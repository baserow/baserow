<template>
  <FloatingMenu
    v-if="editor"
    v-show="open && visible && insideContainer"
    ref="menu"
    :editor="editor"
    :tippy-options="{
      duration: 250,
      placement: 'left',
      appendTo,
      getReferenceClientRect: updateReferenceClientRect,
      onShow,
      onHidden,
    }"
    :should-show="() => true"
  >
    <div :style="{ visibility: 'visible' }">
      <div
        v-if="!expanded"
        class="rich-text-editor__floating-menu rich-text-editor__floating-menu--collapsed"
      >
        <div class="rich-text-editor__floating-menu-button">
          <button class="is-active" @click.stop.prevent="expand()">
            <i :class="activeNodeIcon"></i>
          </button>
        </div>
      </div>
      <div
        v-else
        class="rich-text-editor__floating-menu rich-text-editor__floating-menu--expanded"
      >
        <div
          :title="$t('richTextEditorFloatingMenu.paragraph')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'p' }"
            @click.stop.prevent="editor.chain().focus().setParagraph().run()"
          >
            <i class="baserow-icon-paragraph"></i>
          </button>
        </div>
        <div
          :title="$t('richTextEditorFloatingMenu.heading1')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'h1' }"
            @click.stop.prevent="
              editor.chain().focus().toggleHeading({ level: 1 }).run()
            "
          >
            <i class="baserow-icon-heading-1"></i>
          </button>
        </div>
        <div
          :title="$t('richTextEditorFloatingMenu.heading2')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'h2' }"
            @click.stop.prevent="
              editor.chain().focus().toggleHeading({ level: 2 }).run()
            "
          >
            <i class="baserow-icon-heading-2"></i>
          </button>
        </div>
        <div
          :title="$t('richTextEditorFloatingMenu.heading3')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'h3' }"
            @click.stop.prevent="
              editor.chain().focus().toggleHeading({ level: 3 }).run()
            "
          >
            <i class="baserow-icon-heading-3"></i>
          </button>
        </div>
        <div
          :title="$t('richTextEditorFloatingMenu.code')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'code' }"
            @click.stop.prevent="editor.chain().focus().toggleCodeBlock().run()"
          >
            <i class="iconoir-code"></i>
          </button>
        </div>
        <div
          :title="$t('richTextEditorFloatingMenu.orderedList')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'ol' }"
            @click.stop.prevent="
              editor.chain().focus().toggleOrderedList().run()
            "
          >
            <i class="baserow-icon-ordered-list"></i>
          </button>
        </div>
        <div
          :title="$t('richTextEditorFloatingMenu.unorderedList')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'ul' }"
            @click.stop.prevent="
              editor.chain().focus().toggleBulletList().run()
            "
          >
            <i class="iconoir-list"></i>
          </button>
        </div>
        <div
          :title="$t('richTextEditorFloatingMenu.taskList')"
          class="rich-text-editor__floating-menu-button"
        >
          <button
            :class="{ 'is-active': activeNode == 'tl' }"
            @click.stop.prevent="editor.chain().focus().toggleTaskList().run()"
          >
            <i class="iconoir-task-list"></i>
          </button>
        </div>
      </div>
    </div>
  </FloatingMenu>
</template>

<script>
import { posToDOMRect } from '@tiptap/core'
import { FloatingMenu } from '@tiptap/vue-2'
import { isElement } from '@baserow/modules/core/utils/dom'

export default {
  name: 'RichTextEditorBubbleMenuContext',
  components: { FloatingMenu },
  props: {
    editor: {
      type: Object,
      required: false,
      default: null,
    },
    getScrollableAreaBoundingRect: {
      type: Function,
      default: () => null,
    },
    visible: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      open: true,
      insideContainer: true,
      expanded: false,
    }
  },
  computed: {
    activeNode() {
      if (this.editor.isActive('heading', { level: 1 })) {
        return 'h1'
      } else if (this.editor.isActive('heading', { level: 2 })) {
        return 'h2'
      } else if (this.editor.isActive('heading', { level: 3 })) {
        return 'h3'
      } else if (this.editor.isActive('orderedList')) {
        return 'ol'
      } else if (this.editor.isActive('bulletList')) {
        return 'ul'
      } else if (this.editor.isActive('codeBlock')) {
        return 'code'
      } else if (this.editor.isActive('taskList')) {
        return 'tl'
      } else {
        return 'p'
      }
    },
    activeNodeIcon() {
      switch (this.activeNode) {
        case 'h1':
          return 'baserow-icon-heading-1'
        case 'h2':
          return 'baserow-icon-heading-2'
        case 'h3':
          return 'baserow-icon-heading-3'
        case 'code':
          return 'iconoir-code'
        case 'ol':
          return 'baserow-icon-ordered-list'
        case 'ul':
          return 'iconoir-list'
        case 'tl':
          return 'iconoir-task-list'
        default:
          return 'baserow-icon-paragraph'
      }
    },
  },
  methods: {
    isEventTargetInside(event) {
      return (
        isElement(this.$el, event.target) ||
        isElement(this.$el, event.relatedTarget) ||
        /// Safari set the relatedTarget to the tippyjs popover that contains this.$el,
        // but since we cannot access it by reference, try inverting the check.
        isElement(event.relatedTarget, this.$el)
      )
    },
    onShow() {
      this.$emit('show')
    },
    onHidden() {
      this.$emit('hidden')
    },
    expand() {
      this.open = true
      this.expanded = true
    },
    collapse() {
      this.open = true
      this.expanded = false
    },
    appendTo() {
      return document.body
    },
    updateInsideContainerFlag(boundingRect) {
      const containerBoundingRect = this.getScrollableAreaBoundingRect()
      if (!containerBoundingRect) {
        return
      }
      this.insideContainer =
        containerBoundingRect.top < boundingRect.bottom &&
        containerBoundingRect.bottom > boundingRect.top
    },
    updateReferenceClientRect() {
      const view = this.editor.view
      const { state } = view
      const { from } = state.selection
      const boundingRect = posToDOMRect(view, from, from)

      // Open the menu to the left of the editor with a small offset.
      const editorBoundingRect = view.dom.getBoundingClientRect()
      const offset = 4
      boundingRect.left = editorBoundingRect.left - offset
      boundingRect.right = editorBoundingRect.left - offset

      this.updateInsideContainerFlag(boundingRect)

      return boundingRect
    },
  },
}
</script>
