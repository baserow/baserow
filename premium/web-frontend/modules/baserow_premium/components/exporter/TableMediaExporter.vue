<template>
  <div>
    <div class="row">
      <div class="col col-12">
        <FormGroup
          :label="$t('tableMediaExporter.organizeMediaFiles')"
          required
          small-label
          class="margin-bottom-2"
        >
          <Checkbox v-model="values.organize_media_files" :disabled="loading">{{
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
  name: 'TableMediaExporter',
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
        organize_media_files: true,
      },
    }
  },
}
</script>
