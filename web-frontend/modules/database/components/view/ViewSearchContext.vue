<template>
  <Context
    :class="{ 'context--loading-overlay': view._.loading }"
    overflow-scroll
    max-height-if-outside-viewport
    @shown="focus"
  >
    <form class="context__form" @submit.prevent="searchIfChanged">
      <FormInput
        ref="activeSearchTermInput"
        v-model="activeSearchTerm"
        size="large"
        icon-left="iconoir-search"
        :placeholder="$t('viewSearchContext.searchInRows')"
        class="margin-bottom-2"
        @keyup="searchIfChanged"
      ></FormInput>
      <div
        v-if="!alwaysHideRowsNotMatchingSearch"
        class="control control--align-right margin-bottom-0"
      >
        <SwitchInput
          v-model="hideRowsNotMatchingSearch"
          small
          @input="searchIfChanged"
        >
          {{ $t('viewSearchContext.hideNotMatching') }}
        </SwitchInput>
      </div>
    </form>
  </Context>
</template>

<script>
import debounce from 'lodash/debounce'

import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'ViewSearchContext',
  mixins: [context],
  props: {
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
    alwaysHideRowsNotMatchingSearch: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      activeSearchTerm: '',
      lastSearch: '',
      hideRowsNotMatchingSearch: true,
      lastHide: true,
      loading: false,
    }
  },
  methods: {
    focus() {
      this.$nextTick(function () {
        this.$refs.activeSearchTermInput.focus()
      })
    },
    searchIfChanged() {
      this.$emit('search-changed', this.activeSearchTerm)
      if (
        this.lastSearch === this.activeSearchTerm &&
        this.lastHide === this.hideRowsNotMatchingSearch
      ) {
        return
      }

      this.search()

      this.lastSearch = this.activeSearchTerm
      this.lastHide = this.hideRowsNotMatchingSearch
    },
    search() {
      if (this.readOnly) {
        this.$emit('refresh', { activeSearchTerm: this.activeSearchTerm })
        return
      }

      this.loading = true

      // When the user toggles from hiding rows to not hiding rows we still
      // need to refresh as we need to fetch the un-searched rows from the server first.
      if (this.hideRowsNotMatchingSearch || this.lastHide) {
        // noinspection JSValidateTypes
        this.debouncedServerSearchRefresh()
      } else {
        // noinspection JSValidateTypes
        this.debouncedClientSideSearchRefresh()
      }
    },
    debouncedServerSearchRefresh: debounce(async function () {
      await this.$store.dispatch(
        `${this.storePrefix}view/${this.view.type}/updateSearch`,
        {
          activeSearchTerm: this.activeSearchTerm,
          hideRowsNotMatchingSearch: this.hideRowsNotMatchingSearch,
          // The refresh event we fire below will cause the table to refresh it state from
          // the server using the newly set search terms.
          refreshMatchesOnClient: false,
          fields: this.fields,
        }
      )
      this.$emit('refresh', {
        callback: this.finishedLoading,
        activeSearchTerm: this.activeSearchTerm,
      })
    }, 400),
    // Debounce even the client side only refreshes as otherwise spamming the keyboard
    // can cause many refreshes to queue up quickly bogging down the UI.
    debouncedClientSideSearchRefresh: debounce(async function () {
      await this.$store.dispatch(
        `${this.storePrefix}view/${this.view.type}/updateSearch`,
        {
          activeSearchTerm: this.activeSearchTerm,
          hideRowsNotMatchingSearch: this.hideRowsNotMatchingSearch,
          refreshMatchesOnClient: true,
          fields: this.fields,
        }
      )
      this.finishedLoading()
    }, 10),
    finishedLoading() {
      this.loading = false
    },
  },
}
</script>
