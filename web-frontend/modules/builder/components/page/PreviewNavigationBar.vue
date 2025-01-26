<template>
  <div class="preview-navigation-bar">
    <div class="preview-navigation-bar__user-selector">
      <UserSelector />
    </div>
    <div class="preview-navigation-bar__address-bar">
      <template v-for="pathPart in splitPath">
        <PreviewNavigationBarInput
          v-if="pathPart.type === 'variable'"
          :key="pathPart.key"
          :class="`preview-navigation-bar__parameter-input--${
            paramTypeMap[pathPart.value]
          }`"
          :validation-fn="pathPart.validationFn"
          :default-value="pageParameters[pathPart.value]"
          @change="
            actionSetParameter({
              page,
              name: pathPart.value,
              value: $event,
            })
          "
        />
        <div
          v-else
          :key="`else_${pathPart.key}`"
          class="preview-navigation-bar__address-bar-path"
        >
          {{ pathPart.value }}
        </div>
      </template>
      <template v-for="(queryParam, index) in queryParams">
        <span
          :key="`separator-${queryParam.key}`"
          class="preview-navigation-bar__query-separator"
        >
          {{ index === 0 ? '?' : '&' }}
        </span>
        <PreviewNavigationBarQueryParam
          :key="`param-${queryParam.key}`"
          :class="`preview-navigation-bar__query-parameter-input--${queryParam.type}`"
          :validation-fn="queryParam.validationFn"
          :default-value="pageParameters[queryParam.name]"
          :name="queryParam.name"
          @change="
            actionSetParameter({
              page,
              name: queryParam.name,
              value: $event,
            })
          "
        />
      </template>
    </div>
    <div />
  </div>
</template>

<script>
import { splitPath } from '@baserow/modules/builder/utils/path'
import PreviewNavigationBarInput from '@baserow/modules/builder/components/page/PreviewNavigationBarInput'
import UserSelector from '@baserow/modules/builder/components/page/UserSelector'
import { mapActions } from 'vuex'
import { PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS } from '@baserow/modules/builder/enums'
import PreviewNavigationBarQueryParam from '@baserow/modules/builder/components/page/PreviewNavigationBarQueryParam.vue'

export default {
  components: {
    PreviewNavigationBarInput,
    UserSelector,
    PreviewNavigationBarQueryParam,
  },
  props: {
    page: {
      type: Object,
      required: true,
    },
  },
  computed: {
    pageParameters() {
      return this.$store.getters['pageParameter/getParameters'](this.page)
    },
    queryParams() {
      return this.page.query_params.map((queryParam, idx) => ({
        ...queryParam,
        key: `query-param-${queryParam.name}-${idx}`,
        validationFn: PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS[queryParam.type],
      }))
    },
    splitPath() {
      return splitPath(this.page.path).map((pathPart, index) => ({
        ...pathPart,
        key:
          pathPart.type === 'variable'
            ? `${this.paramTypeMap[pathPart.value]}-${pathPart.value}-${index}`
            : `${pathPart.value}-${index}`,
        validationFn:
          PAGE_PARAM_TYPE_VALIDATION_FUNCTIONS[
            this.paramTypeMap[pathPart.value]
          ],
      }))
    },
    paramTypeMap() {
      return Object.fromEntries(
        this.page.path_params.map(({ name, type }) => [name, type])
      )
    },
  },
  methods: {
    ...mapActions({ actionSetParameter: 'pageParameter/setParameter' }),
  },
}
</script>
