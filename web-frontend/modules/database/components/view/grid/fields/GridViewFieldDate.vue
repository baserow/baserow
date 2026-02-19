<template>
  <div
    ref="cell"
    class="grid-view__cell active"
    :class="{ editing: editing }"
    @contextmenu="stopContextIfEditing($event)"
  >
    <div class="grid-field-date">
      <div v-show="!editing" ref="dateDisplay" class="grid-field-date__date">
        {{ date }}
      </div>
      <div
        v-show="!editing"
        v-if="field.date_include_time"
        ref="timeDisplay"
        class="grid-field-date__time"
      >
        {{ time }}
      </div>
      <template v-if="editing">
        <input
          ref="date"
          v-model="date"
          type="text"
          class="grid-field-date__date-input"
          :placeholder="getDatePlaceholder(field)"
          @keyup="updateDate(field, date)"
          @focus="focus($refs.dateContext, $event)"
          @blur="blur($refs.dateContext, $event)"
        />
        <Context
          ref="dateContext"
          :hide-on-click-outside="false"
          class="datepicker-context"
        >
          <client-only>
            <date-picker
              :inline="true"
              :monday-first="true"
              :use-utc="true"
              :model-value="pickerDate"
              :language="datePickerLanguage"
              :open-date="pickerDate || new Date()"
              class="datepicker"
              @update:model-value="chooseDate(field, $event)"
              @selected="preventNextUnselect = true"
            />
          </client-only>
        </Context>

        <template v-if="field.date_include_time">
          <input
            ref="time"
            v-model="time"
            type="text"
            class="grid-field-date__time-input"
            :placeholder="getTimePlaceholder(field)"
            @keyup="updateTime(field, time)"
            @focus="focus($refs.timeContext, $event)"
            @blur="blur($refs.timeContext, $event)"
          />
          <TimeSelectContext
            ref="timeContext"
            :value="time"
            :hide-on-click-outside="false"
            :notation="field.date_time_format"
            @input="chooseTime(field, $event)"
          />
        </template>
      </template>
      <div v-if="field.date_show_tzinfo" class="grid-field-date__tzinfo">
        {{ getCellTimezoneAbbr(field, value, { force: editing }) }}
      </div>
    </div>
  </div>
</template>

<script>
import TimeSelectContext from '@baserow/modules/core/components/TimeSelectContext'
import { isElement } from '@baserow/modules/core/utils/dom'
import gridField from '@baserow/modules/database/mixins/gridField'
import gridFieldInput from '@baserow/modules/database/mixins/gridFieldInput'
import dateField from '@baserow/modules/database/mixins/dateField'
import { useDatePickerLanguage } from '@baserow/modules/core/composables/useDatePickerLanguage'
// TODO MIG import { en, fr } from 'vuejs-datepicker/dist/locale'

export default {
  components: { TimeSelectContext },
  mixins: [gridField, gridFieldInput, dateField],
  setup() {
    return useDatePickerLanguage()
  },
  data() {
    return {
      preventNextUnselect: false,
    }
  },
  methods: {
    /**
     * When the user initializes the editing state we automatically want to focus on
     * the date or the time field. In almost all cases we start by focusing on the
     * date field, but when the user double clicks on the time field we focus in that
     * one.
     */
    afterEdit(event) {
      this.$nextTick(() => {
        const input =
          event !== null &&
          event.type === 'click' &&
          this.field.date_include_time &&
          event.target === this.$refs.timeDisplay
            ? this.$refs.time
            : this.$refs.date

        input.focus()
        input.selectionStart = input.selectionEnd = 100000
      })
    },
    /**
     * If the user clicks inside the datepicker or time select context we do not want
     * to unselect the field. The contexts live in the root of the body element and not
     * inside the cell, so the system naturally wants to unselect when the user clicks
     * inside one of these contexts.
     */
    canUnselectByClickingOutside(event) {
      // A small hack that checks if the next unselect must be prevented. Unfortunately
      // this is needed because in some cases the date picker refreshes all his child
      // elements. Because that is done we can't simply check if the date context
      // contains the event target. That would result in hiding the date picker when we
      // don't want to do that. This makes sure that the date picker stays visible.
      if (this.editing && this.preventNextUnselect) {
        this.preventNextUnselect = false
        return false
      }

      return (
        !this.editing ||
        (!isElement(this.$refs.dateContext.$el, event.target) &&
          (!this.field.date_include_time ||
            !isElement(this.$refs.timeContext.$el, event.target)))
      )
    },
    /**
     * Normally when the user presses the tab key we automatically select the next or
     * previous cell. The date field can have two inputs, one for the date and one for
     * the time. When the user presses the tab key while the date field is selected we
     * want to focus on the time field instead of the next cell.
     */
    canSelectNext(event) {
      const original = gridFieldInput.methods.canSelectNext.call(this, event)
      if (!this.field.date_include_time) {
        return original
      }

      const previous = event.key === 'Tab' && event.shiftKey
      const next = event.key === 'Tab' && !event.shiftKey
      return (
        original &&
        !(next && this.$refs.date === document.activeElement) &&
        !(previous && this.$refs.time === document.activeElement)
      )
    },
    /**
     * When the user cancels the action we need to reset the date and time data using
     * the original value. This is needed because the date and time data are directly
     * visible to user and not the value like most other fields.
     */
    cancel() {
      gridFieldInput.methods.cancel.call(this)
      this.setDateAndTime(this.field, this.value)
    },
  },
}
</script>
