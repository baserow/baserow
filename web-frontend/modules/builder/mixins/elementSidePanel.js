import { mapActions, mapGetters } from 'vuex'
import _ from 'lodash'

import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  inject: ['workspace', 'builder', 'applicationContext'],
  provide() {
    return {
      applicationContext: {
        ...this.applicationContext,
        element: this.element,
        page: this.elementPage,
      },
      // We add the current element page
      elementPage: this.elementPage,
    }
  },
  computed: {
    ...mapGetters({
      element: 'element/getSelected',
    }),

    elementType() {
      if (this.element) {
        return this.$registry.get('element', this.element.type)
      }
      return null
    },

    parentElement() {
      return this.$store.getters['element/getElementById'](
        this.elementPage,
        this.element?.parent_element_id
      )
    },

    elementPage() {
      // We use the page from the element itself
      return this.$store.getters['page/getById'](
        this.builder,
        this.element.page_id
      )
    },

    defaultValues() {
      return this.element
    },
  },
  methods: {
    ...mapActions({
      actionDebouncedUpdateSelectedElement: 'element/debouncedUpdateSelected',
    }),
    async onChange(newValues) {
      if (
        !this.$hasPermission(
          'builder.page.element.update',
          this.element,
          this.workspace.id
        ) ||
        !this.$refs.panelForm?.isFormValid(true)
      ) {
        return
      }

      const differences = Object.fromEntries(
        Object.entries(newValues).filter(
          ([key, value]) => !_.isEqual(value, this.element[key])
        )
      )

      // We never want to update the order this way
      delete differences.order

      if (Object.keys(differences).length > 0) {
        try {
          await this.actionDebouncedUpdateSelectedElement({
            page: this.elementPage,
            // Here we clone the values to prevent
            // "modification outside of the store" error
            values: clone(differences),
          })
        } catch (error) {
          // Restore the previous saved values from the store
          this.$refs.panelForm?.reset(true)
          notifyIf(error)
        }
      }
    },
  },
}
