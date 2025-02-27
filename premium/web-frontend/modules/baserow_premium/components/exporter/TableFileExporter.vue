<template>
  <div>
    <div class="row">
      <div class="col col-12">
        <FormGroup
          :label="$t('tableFileExporter.organizeFiles')"
          required
          small-label
          class="margin-bottom-2"
        >
          <Checkbox v-model="values.organize_files" :disabled="loading">{{
            $t('common.yes')
          }}</Checkbox>
        </FormGroup>
      </div>
    </div>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'TableFileExporter',
  mixins: [form],
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      values: {
        organize_files: false,
      },
    }
  },
}
</script>
