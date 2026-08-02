<template>
  <div class="open-url-workflow-action-form">
    <div class="open-url-workflow-action-form__row">
      <div class="open-url-workflow-action-form__label">
        {{ $t('openUrlWorkflowActionForm.url') }}
      </div>
      <div class="open-url-workflow-action-form__control">
        <DatabaseFormulaInput
          :value="values.url"
          :data-providers-allowed="['fields']"
          :placeholder="$t('openUrlWorkflowActionForm.urlPlaceholder')"
          @input="values.url = $event"
          @update:invalid="urlInvalid = $event"
        />
      </div>
    </div>
    <div class="open-url-workflow-action-form__row">
      <div class="open-url-workflow-action-form__label">
        {{ $t('openUrlWorkflowActionForm.openIn') }}
      </div>
      <div class="open-url-workflow-action-form__control">
        <SegmentControl
          size="small"
          :segments="targetSegments"
          :active-index="values.target === 'blank' ? 1 : 0"
          @update:active-index="values.target = $event === 1 ? 'blank' : 'self'"
        ></SegmentControl>
      </div>
    </div>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import DatabaseFormulaInput from '@baserow/modules/database/components/field/DatabaseFormulaInput'

/**
 * The config form of an `open_url` workflow action: the URL formula and the
 * tab it opens in. Unlike the row actions it is backed by no service, so it
 * edits the action's own fields directly.
 */
export default {
  name: 'OpenUrlWorkflowActionForm',
  components: { SegmentControl, DatabaseFormulaInput },
  mixins: [form],
  data() {
    return {
      allowedValues: ['url', 'target'],
      values: {
        url: { formula: '', mode: 'simple' },
        target: 'self',
      },
      urlInvalid: false,
    }
  },
  computed: {
    targetSegments() {
      return [
        { label: this.$t('openUrlWorkflowActionForm.sameTab') },
        { label: this.$t('openUrlWorkflowActionForm.newTab') },
      ]
    },
  },
  methods: {
    /**
     * The formula input only emits `input` for parseable formulas, so block
     * submission while the editor content is invalid instead of saving the
     * last parseable formula the user has since edited away.
     */
    isFormValid(deep = false) {
      return !this.urlInvalid && form.methods.isFormValid.call(this, deep)
    },
  },
}
</script>
