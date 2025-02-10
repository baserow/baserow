import bufferedRows from '@baserow/modules/database/store/view/bufferedRows'
import TimelineService from '@baserow_premium/services/views/timeline'
import { getRowMetadata } from '@baserow/modules/database/utils/row'

export function populateRow(row, metadata = {}) {
  row._ = {
    metadata: getRowMetadata(row, metadata),
  }
  return row
}

const timelineBufferedRows = bufferedRows({
  service: TimelineService,
  customPopulateRow: populateRow,
})

export const state = () => ({
  ...timelineBufferedRows.state(),
})

export const mutations = {
  ...timelineBufferedRows.mutations,
}

export const actions = {
  ...timelineBufferedRows.actions,
  async fetchInitial(
    { dispatch },
    { viewId, fields, adhocFiltering, adhocSorting }
  ) {
    const data = await dispatch('fetchInitialRows', {
      viewId,
      fields,
      initialRowArguments: {
        includeFieldOptions: true,
      },
      adhocFiltering,
      adhocSorting,
    })
    await dispatch('forceUpdateAllFieldOptions', data.field_options)
  },
}

export const getters = {
  ...timelineBufferedRows.getters,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
