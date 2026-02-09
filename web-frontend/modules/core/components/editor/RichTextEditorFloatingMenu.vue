<template>
  <BubbleMenu
    v-if="editor"
    v-show="open"
    ref="menu"
    class="rich-text-editor__menu-container"
    :editor="editor"
    :plugin-key="pluginKey"
    :append-to="appendTo"
    :should-show="shouldShowMenu"
    :update-delay="0"
    :resize-delay="0"
    :options="menuOptions"
    :get-referenced-virtual-element="getVirtualElement"
  >
    <div>
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
            @click.stop.prevent="setBlockType('paragraph')"
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
            @click.stop.prevent="setBlockType('h1')"
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
            @click.stop.prevent="setBlockType('h2')"
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
            @click.stop.prevent="setBlockType('h3')"
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
            @click.stop.prevent="setBlockType('code')"
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
            @click.stop.prevent="setBlockType('ol')"
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
            @click.stop.prevent="setBlockType('ul')"
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
            @click.stop.prevent="setBlockType('tl')"
          >
            <i class="iconoir-task-list"></i>
          </button>
        </div>
      </div>
    </div>
  </BubbleMenu>
</template>

<script>
import { posToDOMRect } from '@tiptap/core'
import { BubbleMenu } from '@tiptap/vue-3/menus'
import { isElement } from '@baserow/modules/core/utils/dom'

export default {
  name: 'RichTextEditorFloatingMenu',
  components: { BubbleMenu },
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
      default: 'floatingBlockMenu',
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
      open: true,
      expanded: false,
    }
  },
  computed: {
    menuOptions() {
      const opts = {
        strategy: 'fixed',
        placement: 'left',
        offset: { mainAxis: 14, crossAxis: 0 },
        flip: false,
        duration: 0,
      }
      if (this.scrollTarget) {
        opts.scrollTarget = this.scrollTarget
      }
      return opts
    },
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
    shouldShowMenu({ editor }) {
      if (!this.visible) return false
      const emptySelection = editor.state.selection.empty
      if (editor.isActive('image')) return false
      if (
        (!emptySelection && !editor.isActive('codeBlock')) ||
        editor.isActive('link')
      ) {
        return false
      }
      return true
    },
    isEventTargetInside(event) {
      return (
        isElement(this.$el, event.target) ||
        isElement(this.$el, event.relatedTarget) ||
        // Safari set the relatedTarget to the floating-ui popover that contains this.$el,
        // but since we cannot access it by reference, try inverting the check.
        isElement(event.relatedTarget, this.$el)
      )
    },
    expand() {
      this.open = true
      this.expanded = true
      this.triggerPositionUpdate()
    },
    collapse() {
      this.open = true
      this.expanded = false
      this.triggerPositionUpdate()
    },
    triggerPositionUpdate() {
      this.$nextTick(() => {
        const { tr } = this.editor.state
        tr.setMeta('bubbleMenu', 'updatePosition')
        this.editor.view.dispatch(tr)
      })
    },
    setBlockType(type) {
      if (!this.editor) {
        return
      }

      const chain = this.editor.chain().focus().clearNodes()

      switch (type) {
        case 'paragraph':
          chain.setParagraph()
          break
        case 'h1':
          chain.setHeading({ level: 1 })
          break
        case 'h2':
          chain.setHeading({ level: 2 })
          break
        case 'h3':
          chain.setHeading({ level: 3 })
          break
        case 'code':
          chain.setCodeBlock()
          break
        case 'ol':
          chain.toggleOrderedList()
          break
        case 'ul':
          chain.toggleBulletList()
          break
        case 'tl':
          chain.toggleTaskList()
          break
      }

      chain.run()
      this.open = true
      // Trigger position recalculation after format change (line height may change)
      this.triggerPositionUpdate()
    },
    getVirtualElement() {
      const editor = this.editor
      return {
        // Compute fresh coordinates on each call so floating-ui's autoUpdate
        // always gets the current cursor and editor position.
        getBoundingClientRect: () => {
          const view = editor.view
          const { from } = view.state.selection
          const cursorRect = posToDOMRect(view, from, from)
          const editorRect = view.dom.getBoundingClientRect()
          return {
            top: cursorRect.top,
            bottom: cursorRect.bottom,
            left: editorRect.left,
            right: editorRect.left,
            x: editorRect.left,
            y: cursorRect.top,
            width: 0,
            height: cursorRect.height,
          }
        },
      }
    },
  },
}
</script>
