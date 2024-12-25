<template>
  <FormGroup small-label :label="$t('pageForm.pathParamsTitle')" required>
    <div
      v-for="pathParam in pathParams"
      :key="pathParam.name"
      class="page-settings-path-params"
    >
      <span class="page-settings-path-params__name">{{ pathParam.name }}</span>
      <div class="page-settings-path-params__dropdown">
        <Dropdown
          :value="pathParam.type"
          :disabled="disabled"
          @input="$emit('update', pathParam.name, $event)"
        >
          <DropdownItem
            v-for="pathParamType in pathParamTypes"
            :key="pathParamType.getType()"
            :name="pathParamType.name"
            :value="pathParamType.getType()"
          ></DropdownItem>
        </Dropdown>
      </div>
    </div>

    <template #helper>
      <template v-if="Object.keys(pathParams).length > 0">
        {{ $t('pageForm.pathParamsSubtitle') }}
      </template>
      <template v-else>
        {{ $t('pageForm.pathParamsSubtitleTutorial') }}
      </template>
    </template>
  </FormGroup>
</template>

<script>
export default {
  name: 'PageSettingsPathParamsFormElement',
  props: {
    pathParams: {
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
    pathParamTypes() {
      return this.$registry.getOrderedList('pathParamType')
    },
  },
}
</script>
