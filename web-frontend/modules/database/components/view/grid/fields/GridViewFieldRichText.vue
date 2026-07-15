<!-- eslint-disable vue/no-v-html -->
<template>
  <div
    ref="cell"
    class="grid-view__cell grid-field-rich-text__cell active"
    :class="{
      editing: opened && !isModalOpen(),
      'field-rich-text--preview': !opened || isModalOpen(),
      invalid: editing && !isModalOpen() && !isValid(),
    }"
    @contextmenu="stopContextIfEditing($event)"
  >
    <div
      v-if="!opened || isModalOpen()"
      class="grid-field-rich-text__cell-content"
      :class="{
        'grid-field-rich-text__cell-content--preview': !opened || isModalOpen(),
      }"
      v-html="formattedValue"
    />
    <RichTextEditor
      v-else
      ref="input"
      v-model="richCopy"
      v-prevent-parent-scroll="editing"
      class="grid-field-rich-text__textarea"
      :class="{ 'grid-field-rich-text__textarea--resizable': editing }"
      :editable="editing && !isModalOpen()"
      :enable-rich-text-formatting="true"
      :mentionable-users="workspace ? workspace.users : null"
      :thin-scrollbar="true"
      :menu-container="getMenuContainer"
    />
    <i
      v-if="editing && !isModalOpen()"
      class="baserow-icon-enlarge grid-field-rich-text__textarea-expand-icon"
      @click="($refs.expandedModal.toggle(), resetCellSize())"
    />
    <div
      v-show="editing && !isModalOpen() && !isValid()"
      class="grid-view__cell-error align-right"
    >
      {{ getError() }}
    </div>
    <FieldRichTextModal
      ref="expandedModal"
      v-model="richCopy"
      :field="field"
      :error="getModalError()"
      :mentionable-users="workspace ? workspace.users : null"
      @hidden="onExpandedModalHidden"
    />
  </div>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import gridField from '@baserow/modules/database/mixins/gridField'
import gridFieldInput from '@baserow/modules/database/mixins/gridFieldInput'
import FieldRichTextModal from '@baserow/modules/database/components/view/FieldRichTextModal'
import { parseMarkdown } from '@baserow/modules/core/editor/markdown'

export default {
  components: { RichTextEditor, FieldRichTextModal },
  mixins: [gridField, gridFieldInput],
  data() {
    return {
      // local copy of the value storing the JSON representation of the rich text editor
      richCopy: '',
      hasEdits: false,
    }
  },
  computed: {
    formattedValue() {
      return parseMarkdown(this.value, {
        openLinkOnClick: true,
        workspaceUsers: this.workspace ? this.workspace.users : null,
        loggedUserId: this.$store.getters['auth/getUserId'],
      })
    },
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
  },
  watch: {
    value: {
      handler(value) {
        this.richCopy = value || ''
      },
      immediate: true,
    },
    editing(editing) {
      this.hasEdits = false
      if (!editing) {
        this.richCopy = this.value || ''
      }
    },
    richCopy() {
      if (this.editing) {
        this.hasEdits = true
      }
    },
  },
  methods: {
    getMenuContainer() {
      return document.body
    },
    isModalOpen() {
      return this.$refs.expandedModal?.isOpen()
    },
    scrollHeight() {
      return {
        sh: this.$refs.container.scrollHeight,
        st: this.$refs.container.scrollTop,
      }
    },
    cancel() {
      // While the modal is open it owns closing (it blocks close on invalid content).
      if (this.isModalOpen()) {
        return
      }
      if (!this.isValid()) {
        this.opened = false
        this.editing = false
        return
      }
      return this.save()
    },
    getError() {
      if (!this.editing) {
        return this.getValidationError(this.value)
      }
      const ref = this.isModalOpen() ? 'expandedModal' : 'input'
      return this.getValidationError(this.$refs[ref]?.serializeToMarkdown())
    },
    getModalError() {
      return this.isModalOpen() ? this.getError() : null
    },
    beforeSave() {
      // Reserializing an untouched legacy value could rewrite it on mere blur.
      if (!this.hasEdits) {
        return this.value
      }
      const ref = this.isModalOpen() ? 'expandedModal' : 'input'
      return this.$refs[ref].serializeToMarkdown()
    },
    afterEdit() {
      this.$nextTick(() => {
        this.$refs.input.focus()
      })
    },
    onExpandedModalHidden() {
      this.preventNextUnselect = true
      if (!this.isValid()) {
        this.opened = false
        this.editing = false
        return
      }
      this.save()
    },
    onPaste() {
      // Prevent the grid paste handler from intercepting TipTap editor pastes.
      return this.editing
    },
    canSaveByPressingEnter() {
      return false
    },
    resetCellSize() {
      // remove any custom width and height set by the user resizing the cell
      this.$refs.input.$el.style.width = ''
      this.$refs.input.$el.style.height = ''
    },
    canUnselectByClickingOutside(event) {
      // The RichTextEditorBubbleMenuContext component is a context menu and so it's not
      // a direct child of the RichTextEditorBubbleMenu component. This means that the
      // when you click on an item, we have to prevent the next unselect event from
      // happening otherwise the cell will lose focus and the editor will close.
      if (this.preventNextUnselect) {
        this.preventNextUnselect = false
        return false
      }

      return (
        !this.editing ||
        (!this.$refs.input?.isEventTargetInside(event) && !this.isModalOpen())
      )
    },
  },
}
</script>
