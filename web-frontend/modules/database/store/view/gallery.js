import bufferedRows from '@baserow/modules/database/store/view/bufferedRows'
import fieldOptions from '@baserow/modules/database/store/view/fieldOptions'
import GalleryService from '@baserow/modules/database/services/view/gallery'

export function populateRow(row, metadata = {}) {
  row._ = {
    metadata,
    dragging: false,
  }
  return row
}

const galleryBufferedRows = bufferedRows({
  service: GalleryService,
  populateRow,
})

const galleryFieldOptions = fieldOptions()

export const state = () => ({
  ...galleryBufferedRows.state(),
  ...galleryFieldOptions.state(),
})

export const mutations = {
  ...galleryBufferedRows.mutations,
  ...galleryFieldOptions.mutations,
}

export const actions = {
  ...galleryBufferedRows.actions,
  ...galleryFieldOptions.actions,
  async fetchInitial(
    { dispatch },
    { viewId, fields, adhocFiltering, adhocSorting }
  ) {
    const data = await dispatch('fetchInitialRows', {
      viewId,
      fields,
      initialRowArguments: { includeFieldOptions: true },
      adhocFiltering,
      adhocSorting,
    })
    await dispatch('forceUpdateAllFieldOptions', data.field_options)
  },
}

export const getters = {
  ...galleryBufferedRows.getters,
  ...galleryFieldOptions.getters,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
