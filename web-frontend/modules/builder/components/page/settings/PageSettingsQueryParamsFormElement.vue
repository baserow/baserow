<template>
  <FormGroup small-label :label="$t('pageForm.queryParamsTitle')" required>
    <div
      v-for="(queryParam, index) in localQueryParams"
      :key="index"
      class="page-settings-query-params"
    >
      <FormInput
        :value="queryParam.name"
        class="page-settings-query-params__name"
        @input="updateQueryParamName(index, $event)"
        @blur="finalizeQueryParamUpdate(index)"
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
          localQueryParams.length > 0
            ? $t('pageForm.addAnotherParameter')
            : $t('pageForm.addParameter')
        }}
      </ButtonText>
    </div>
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
  },
  data() {
    return {
      localQueryParams: [],
    }
  },
  watch: {
    queryParams: {
      immediate: true,
      handler(newParams) {
        this.localQueryParams = JSON.parse(JSON.stringify(newParams))
      },
    },
  },
  methods: {
    deleteQueryParam(index) {
      this.localQueryParams.splice(index, 1)
      this.$emit('update', this.localQueryParams)
    },
    updateQueryParamName(index, newName) {
      this.localQueryParams[index].name = newName
    },
    finalizeQueryParamUpdate(index) {
      this.$emit('update', this.localQueryParams)
    },
    updateQueryParamType(index, newType) {
      this.localQueryParams[index].type = newType
      this.$emit('update', this.localQueryParams)
    },
    addParameter() {
      const newParam = {
        name: `param${this.localQueryParams.length + 1}`,
        type: this.queryParamTypes[0].getType(),
      }
      this.localQueryParams.push(newParam)
      this.$emit('update', this.localQueryParams)
    },
  },
  computed: {
    queryParamTypes() {
      return this.$registry.getOrderedList('queryParamType')
    },
  },
}
</script>
