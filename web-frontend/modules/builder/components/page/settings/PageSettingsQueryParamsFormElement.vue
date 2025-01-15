<template>
  <FormGroup
    small-label
    :label="$t('pageForm.queryParamsTitle')"
    :error="
      hasErrors ||
      (validationState.$dirty && !validationState.uniqueQueryParams)
    "
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
      <a
        class="filters__remove page-settings-query-params__remove"
        @click.stop="deleteQueryParam(index)"
      >
        <i class="iconoir-bin"></i>
      </a>
    </div>

    <template #helper>
      <template v-if="queryParams.length == 0">
        {{ $t('pageForm.queryParamsSubtitleTutorial') }}
      </template>
    </template>
    <div>
      <ButtonText icon="iconoir-plus" @click.prevent="addParameter">
        {{
          values.queryParams.length > 0
            ? $t('pageForm.addAnotherParameter')
            : $t('pageForm.addParameter')
        }}
      </ButtonText>
    </div>
    <span
      v-if="validationState.$dirty && !validationState.uniqueQueryParams"
      class="error"
    >
      {{ $t('pageErrors.errorUniqueValidQueryParams') }}
    </span>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

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
      const newParam = {
        name: `param${this.values.queryParams.length + 1}`,
        type: this.queryParamTypes[0].getType(),
      }
      this.values.queryParams.push(newParam)
      this.$emit('update', this.values.queryParams)
    },
  },
  computed: {
    queryParamTypes() {
      return this.$registry.getOrderedList('queryParamType')
    },
  },
}
</script>
