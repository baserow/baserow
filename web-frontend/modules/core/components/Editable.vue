<template>
  <span
    ref="editable"
    :contenteditable="editing"
    :placeholder="placeholder"
    :class="{
      'forced-user-select-initial': editing,
      'whitespace-pre-wrap': multiline,
      'editable--multi-line': multiline,
    }"
    @input="update"
    @keydown="keydown"
    @focusout="change"
    @paste="paste"
    >{{ value }}</span
  >
</template>

<script>
import { focusEnd } from '@baserow/modules/core/utils/dom'

export default {
  name: 'Editable',
  props: {
    value: {
      type: String,
      required: true,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
    multiline: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['change', 'editing'],
  data() {
    return {
      editing: false,
      oldValue: '',
      newValue: '',
      oldTextOverflow: '',
    }
  },
  watch: {
    value(value) {
      this.set(value)
    },
  },
  mounted() {
    this.set(this.value)
  },
  methods: {
    /**
     * This method must be called when the is going to be edited. It will enable the
     * contenteditable state and will focus the element.
     */
    edit() {
      this.editing = true
      this.$emit('editing', true)
      this.$nextTick(() => {
        if (!this.$refs.editable) return
        focusEnd(this.$refs.editable)
        // In almost all use cases, the parent has overflow hidden and in that case we
        // need to see if the scrollLeft must be changed so that we can see the cursor
        // which has been placed at the end.
        const parent = this.$el.parentElement
        if (!parent) return
        parent.scrollLeft = parent.scrollWidth - parent.clientWidth
        parent.classList.add('forced-text-overflow-initial')
      })
    },
    /**
     * This method is called when the value has changed and needs to be saved. It will
     * change the editing state and will emit a change event if the new value has
     * changed.
     */
    change() {
      this.editing = false
      this.$emit('editing', false)
      this.$nextTick(() => {
        // In almost all use cases, the parent has overflow hidden and it could be that
        // because of the cursor, the scrollLeft value has changed. Here we change it
        // back to what is was before.
        const parent = this.$el.parentElement
        parent.classList.remove('forced-text-overflow-initial')
        if (parent.scrollWidth > parent.clientWidth) {
          parent.scrollLeft = 0
        }
      })

      if (this.oldValue === this.newValue) {
        return
      }

      this.$emit('change', {
        oldValue: this.value,
        value: this.newValue,
      })
      this.oldValue = this.newValue
    },
    /**
     * Everytime a key is pressed inside the editable this event will be trigger which
     * will update the new value.
     */
    update(event) {
      const target = event.target
      let text = target.textContent

      if (this.multiline && target.innerText !== undefined) {
        // textContent doesn't support new lines
        // so we need innerText in multiline mode
        text = target.innerText
      }

      this.newValue = text
    },
    /**
     * When someone pastes something we want to only insert the plain text instead of
     * the styled content.
     */
    paste(event) {
      event.preventDefault()
      const text = (event.originalEvent || event).clipboardData.getData(
        'text/plain'
      )
      document.execCommand('insertText', false, text)
    },
    /**
     * If a key is pressed and it is an enter or esc key the change event will be called
     * to end the editing and save the value.
     */
    keydown(event) {
      // Allow users to create new lines with Shift+Enter
      if (event.key === 'Enter' && event.shiftKey && this.multiline) {
        return false
      }

      if (event.key === 'Enter' || event.key === 'Escape') {
        event.preventDefault()
        this.change()
        return false
      }
    },
    /**
     *
     */
    set(value) {
      this.oldValue = this.value
      this.newValue = this.value
      if (this.$refs.editable) {
        this.$refs.editable.textContent = this.value
      }
    },
  },
}
</script>
