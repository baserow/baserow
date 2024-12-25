<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('multiPageContainerElementForm.display')"
      class="margin-bottom-2"
      required
    >
      <Dropdown v-model="computedPageShareType" :show-search="false" small>
        <DropdownItem
          v-for="item in pageShareTypes"
          :key="item.value"
          :name="item.label"
          :value="item.value"
        >
          {{ item.label }}
        </DropdownItem>
      </Dropdown>
      <template v-if="values.share_type !== 'all'">
        <div class="multi-page-container-element-form__page-list">
          <div
            v-for="page in pages"
            :key="page.id"
            class="multi-page-container-element-form__page-checkbox"
          >
            <Checkbox
              :checked="values.pages.includes(page.id)"
              @input="togglePage(page)"
            >
              {{ page.name }}
            </Checkbox>
          </div>

          <div class="multi-page-container-element-form__actions">
            <a @click.prevent="selectAll">
              {{ $t('multiPageContainerElementForm.selectAll') }}
            </a>
            <a @click.prevent="deselectAll">
              {{ $t('multiPageContainerElementForm.deselectAll') }}
            </a>
          </div>
        </div>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { SHARE_TYPES } from '@baserow/modules/builder/enums'

export default {
  name: 'MultiPageContainerElementForm',
  mixins: [elementForm],
  data() {
    return {
      values: {
        share_type: '',
        pages: [],
        styles: {},
      },
      allowedValues: ['share_type', 'pages', 'styles'],
    }
  },
  computed: {
    computedPageShareType: {
      get() {
        return this.values.share_type
      },
      set(newValue) {
        if (
          [SHARE_TYPES.ONLY, SHARE_TYPES.EXCEPT].includes(newValue) &&
          newValue !== this.values.share_type
        ) {
          if (![SHARE_TYPES.ALL, undefined].includes(this.values.share_type)) {
            // We want to invert the page selection if we change from except <-> only
            this.values.pages = this.pageIds.filter(
              (id) => !this.values.pages.includes(id)
            )
          } else {
            // Otherwise we want to select all or none.
            this.values.pages =
              newValue === SHARE_TYPES.ONLY ? [...this.pageIds] : []
          }
        }

        this.values.share_type = newValue
      },
    },
    pageShareTypes() {
      return [
        {
          label: this.$t('pageShareType.all'),
          value: SHARE_TYPES.ALL,
        },
        {
          label: this.$t('pageShareType.only'),
          value: SHARE_TYPES.ONLY,
        },
        {
          label: this.$t('pageShareType.except'),
          value: SHARE_TYPES.EXCEPT,
        },
      ]
    },
    pages() {
      return this.$store.getters['page/getVisiblePages'](this.builder)
    },
    pageIds() {
      return this.pages.map(({ id }) => id)
    },
  },
  methods: {
    togglePage(page) {
      if (!this.values.pages.includes(page.id)) {
        this.values.pages.push(page.id)
      } else {
        this.values.pages = this.values.pages.filter(
          (pageId) => pageId !== page.id
        )
      }
    },
    selectAll() {
      this.values.pages = this.pageIds
    },
    deselectAll() {
      this.values.pages = []
    },
  },
}
</script>
