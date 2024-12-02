<template>
  <FormGroup small-label :label="$t('pageForm.queryParamsTitle')" required>
    <div
      v-for="queryParam in queryParams"
      :key="queryParam.name"
      class="page-settings-query-params"
    >
      <FormInput
        ref="name"
        v-model="queryParam.name"
        :placeholder="$t('pageForm.QueryParamNamePlaceholder')"
      ></FormInput>
      <div class="page-settings-query-params__dropdown">
        <Dropdown
          :value="queryParam.type"
          :disabled="disabled"
          @input="$emit('update', queryParam.name, $event)"
        >
          <DropdownItem
            v-for="queryParamType in queryParamTypes"
            :key="queryParamType.getType()"
            :name="queryParamType.name"
            :value="queryParamType.getType()"
          ></DropdownItem>
        </Dropdown>
      </div>
    </div>

    <template #helper>
      <template v-if="Object.keys(queryParams).length > 0">
        {{ $t('pageForm.queryParamsSubtitle') }}
      </template>
      <template v-else>
        {{ $t('pageForm.queryParamsSubtitleTutorial') }}
      </template>
    </template>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'PageSettingsqueryParamsFormElement',
  mixins: [form, ],
  props: {
    queryParams: {
      type: Array,
      required: false,
      default: () => [],
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    queryParamTypes() {
      return this.$registry.getOrderedList('queryParamType')
    },
  },
}
</script>
