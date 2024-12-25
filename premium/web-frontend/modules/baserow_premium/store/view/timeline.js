import bufferedRows from '@baserow/modules/database/store/view/bufferedRows'
import fieldOptions from '@baserow/modules/database/store/view/fieldOptions'
import TimelineService from '@baserow_premium/services/views/timeline'

export function populateRow(row, metadata = {}) {
  row._ = {
    metadata,
  }
  return row
}

const timelineBufferedRows = bufferedRows({
  service: TimelineService,
  populateRow,
})

const timelineFieldOptions = fieldOptions()

export const state = () => ({
  ...timelineBufferedRows.state(),
  ...timelineFieldOptions.state(),
})

export const mutations = {
  ...timelineBufferedRows.mutations,
  ...timelineFieldOptions.mutations,
}

export const actions = {
  ...timelineBufferedRows.actions,
  ...timelineFieldOptions.actions,
  async fetchInitial(
    { dispatch },
    { viewId, fields, adhocFiltering, adhocSorting }
  ) {
    const data = await dispatch('fetchInitialRows', {
      viewId,
      fields,
      initialRowArguments: {
        includeFieldOptions: true,
        includeRowMetadata: false,
      },
      adhocFiltering,
      adhocSorting,
    })
    await dispatch('forceUpdateAllFieldOptions', data.field_options)
  },
}

export const getters = {
  ...timelineBufferedRows.getters,
  ...timelineFieldOptions.getters,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
