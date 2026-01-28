import { isPrintableUnicodeCharacterKeyPress } from '@baserow/modules/core/utils/events'

export default {
  data() {
    return {
      // Event handler reference for cleanup
      keydownEvent: null,
    }
  },
  methods: {
    toggleDropdown(value, query) {
      if (this.readOnly) {
        return
      }

      this.$refs.dropdown.toggle(this.$refs.dropdownLink, value, query)
    },
    hideDropdown() {
      this.$refs.dropdown.hide()
    },
    select() {
      this.keydownEvent = (event) => {
        // If the tab or arrow keys are pressed we don't want to do anything because
        // the GridViewField component will select the next field.
        const ignoredKeys = [
          'Tab',
          'ArrowLeft',
          'ArrowUp',
          'ArrowRight',
          'ArrowDown',
        ]
        if (ignoredKeys.includes(event.key)) {
          return
        }

        // If the space bar key is pressed, we don't want to do anything because it
        // should open the row edit modal.
        if (event.key === ' ') {
          return
        }

        // When the escape key is pressed while editing the value we can hide the
        // dropdown.
        if (event.key === 'Escape' && this.editing) {
          this.hideDropdown()
          return
        }

        // When the enter key, any printable character or F2 is pressed when not editing
        // the value we want to show the dropdown.
        if (
          !this.editing &&
          (event.key === 'Enter' ||
            isPrintableUnicodeCharacterKeyPress(event) ||
            event.key === 'F2')
        ) {
          this.toggleDropdown()
        }
      }
      document.body.addEventListener('keydown', this.keydownEvent)
    },
    beforeUnSelect() {
      document.body.removeEventListener('keydown', this.keydownEvent)
    },
    canSelectNext() {
      return !this.editing
    },
    canKeyboardShortcut() {
      return !this.editing
    },
  },
}
