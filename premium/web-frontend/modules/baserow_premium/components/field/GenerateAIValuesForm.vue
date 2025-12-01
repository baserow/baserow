<template>
  <form @submit.prevent="submit">
    <div class="row">
      <div class="col col-12">
        <FormGroup
          small-label
          :label="$t('generateAIValuesForm.scopeLabel')"
          required
          class="margin-bottom-2"
        >
          <Dropdown
            v-model="values.view_id"
            :show-search="true"
            :disabled="loading"
          >
            <DropdownItem
              :name="$t('generateAIValuesForm.entireTable')"
              :value="null"
            ></DropdownItem>

            <DropdownItem
              v-for="v in filterableViews"
              :key="v.id"
              :name="v.name"
              :value="v.id"
              :icon="v._.type.iconClass"
            >
            </DropdownItem>
          </Dropdown>
        </FormGroup>

        <FormGroup small-label class="margin-bottom-2">
          <Checkbox v-model="values.skip_populated" :disabled="loading">
            {{ $t('generateAIValuesForm.skipPopulated') }}
          </Checkbox>
        </FormGroup>

        <Alert type="warning" class="margin-bottom-2">
          <template #title>
            {{ $t('generateAIValuesForm.warningTitle') }}
          </template>
          <p>{{ $t('generateAIValuesForm.warningMessage') }}</p>
        </Alert>
      </div>
    </div>
    <slot></slot>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import Dropdown from '@baserow/modules/core/components/Dropdown'
import DropdownItem from '@baserow/modules/core/components/DropdownItem'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import Alert from '@baserow/modules/core/components/Alert'
import FormGroup from '@baserow/modules/core/components/FormGroup'

export default {
  name: 'GenerateAIValuesForm',
  components: {
    FormGroup,
    Dropdown,
    DropdownItem,
    Checkbox,
    Alert,
  },
  mixins: [form],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: false,
      default: null,
    },
    views: {
      type: Array,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      values: {
        view_id: null,
        skip_populated: false,
      },
    }
  },
  computed: {
    filterableViews() {
      return this.views.filter((view) => {
        const viewType = this.$registry.get('view', view.type)
        return viewType.canFilter
      })
    },
    selectedView() {
      return this.views.find((view) => view.id === this.values.view_id) || null
    },
  },
  created() {
    this.values.view_id = this.view === null ? null : this.view.id
    this.values.skip_populated = false
  },
}
</script>
