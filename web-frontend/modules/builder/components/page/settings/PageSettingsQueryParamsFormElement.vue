<template>
  <FormGroup
    small-label
    :label="$t('pageForm.queryParamsTitle')"
    :error="hasErrors || validationState.uniqueQueryParams.$invalid"
    required
  >
    <div
      v-for="(queryParam, index) in values.queryParams"
      :key="index"
      class="page-settings-query-params"
    >
      <FormInput
        :value="queryParam.name"
        class="page-settings-query-params__name"
        @input="updateQueryParamName(index, $event)"
      ></FormInput>
      <div class="page-settings-query-params__dropdown">
        <Dropdown
          :value="queryParam.type"
          :disabled="disabled"
          @input="updateQueryParamType(index, $event)"
        >
          <DropdownItem
            v-for="queryParamType in queryParamTypes"
            :key="queryParamType.getType()"
            :name="queryParamType.name"
            :value="queryParamType.getType()"
          ></DropdownItem>
        </Dropdown>
      </div>
      <ButtonIcon
        tag="a"
        class="filters__remove page-settings-query-params__remove"
        icon="iconoir-bin"
        @click="deleteQueryParam(index)"
      />
    </div>

    <template #helper>
      <template v-if="queryParams.length == 0">
        {{ $t('pageForm.queryParamsSubtitleTutorial') }}
      </template>
    </template>
    <div>
      <ButtonText
        class="page-settings-query-params__add-button"
        icon="iconoir-plus"
        @click.prevent="addParameter"
      >
        {{
          values.queryParams.length > 0
            ? $t('pageForm.addAnotherParameter')
            : $t('pageForm.addParameter')
        }}
      </ButtonText>
    </div>

    <template #error>
      {{ $t('pageErrors.errorUniqueValidQueryParams') }}
    </template>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'

export default {
  name: 'PageSettingsQueryParamsFormElement',
  mixins: [form],
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
    validationState: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    hasErrors: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      values: {
        queryParams: [],
      },
    }
  },
  computed: {
    queryParamTypes() {
      return this.$registry.getOrderedList('queryParamType')
    },
    existingNames() {
      return [...this.values.queryParams.map(({ name }) => name), 'param']
    },
  },
  watch: {
    queryParams: {
      immediate: true,
      handler(newParams) {
        if (
          JSON.stringify(this.values.queryParams) !== JSON.stringify(newParams)
        ) {
          this.values.queryParams = JSON.parse(JSON.stringify(newParams))
        }
      },
    },
  },
  methods: {
    deleteQueryParam(index) {
      this.values.queryParams.splice(index, 1)
      this.$emit('update', this.values.queryParams)
    },
    updateQueryParamName(index, newName) {
      this.values.queryParams[index].name = newName
      this.$emit('update', this.values.queryParams)
    },
    updateQueryParamType(index, newType) {
      this.values.queryParams[index].type = newType
      this.$emit('update', this.values.queryParams)
    },
    addParameter() {
      // Prevents name conflicts
      const name = getNextAvailableNameInSequence('param', this.existingNames, {
        pattern: (baseName, index) => `${baseName}${index + 1}`,
      })
      const newParam = {
        name,
        type: this.queryParamTypes[0].getType(),
      }
      this.values.queryParams.push(newParam)
      this.$emit('update', this.values.queryParams)
    },
  },
}
</script>
