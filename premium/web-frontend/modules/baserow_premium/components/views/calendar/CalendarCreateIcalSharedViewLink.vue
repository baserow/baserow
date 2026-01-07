<!--
Additional 'sync with external calendar' button for share view link.

This button will be rendered differently depending on view.ical_public
-->
<template>
  <div>
    <Button
      v-if="!view.ical_public && location === 'content'"
      type="secondary"
      :icon="iconCssClasses"
      @click="onClick"
    >
      {{ $t('calendarViewType.sharedViewEnableSyncToExternalCalendar') }}
    </Button>

    <ButtonText
      v-if="!view.ical_public && location === 'footer'"
      :icon="iconCssClasses"
      @click="onClick"
    >
      {{ $t('calendarViewType.sharedViewEnableSyncToExternalCalendar') }}
    </ButtonText>

    <ButtonText v-if="view.ical_public" :icon="iconCssClasses" @click="onClick">
      {{ $t('calendarViewType.sharedViewDisableSyncToExternalCalendar') }}
    </ButtonText>
  </div>
</template>
<script>
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'CalendarCreateIcalSharedViewLink',
  emits: ['update-view'],
  props: {
    view: { type: Object, required: false, default: null },
    /**
     * The location of the button in its parent component.
     */
    location: {
      type: String,
      default: 'content',
      validator: (value) => ['content', 'footer'].includes(value),
    },
  },
  computed: {
    iconCssClasses() {
      const css = this.view.ical_public
        ? ['iconoir-cancel']
        : ['iconoir-calendar']

      return css.join(' ')
    },
  },
  methods: {
    async onClick(evt) {
      await this.updateView({ ical_public: !this.view.ical_public })
      this.$emit('update-view', { ...this.view })
    },

    async updateView(values) {
      const view = this.view

      try {
        await this.$store.dispatch('view/update', {
          view,
          values,
          refreshFromFetch: true,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>
