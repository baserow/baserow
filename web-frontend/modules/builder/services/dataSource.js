import { callGrouper } from '@baserow/modules/core/utils/function'
import { prepareDispatchParams } from '@baserow/modules/builder/utils/params'
import { getBuilderPreviewApiPath } from '@baserow/modules/builder/utils/preview'

const GRACE_DELAY = 50 // ms before querying the backend with a get query

const groupGetNameCalls = callGrouper(GRACE_DELAY)

const csvEscape = (value) => {
  const stringValue = `${value}`
  return /[",\n]/.test(stringValue)
    ? `"${stringValue.replaceAll('"', '""')}"`
    : stringValue
}

export default (client) => {
  return {
    fetchAll(pageId) {
      return client.get(`builder/page/${pageId}/data-sources/`)
    },
    create(pageId, values = {}, beforeId = null) {
      const payload = {
        page_id: pageId,
        ...values,
      }

      if (beforeId !== null) {
        payload.before_id = beforeId
      }

      return client.post(`builder/page/${pageId}/data-sources/`, payload)
    },
    update(dataSourceId, values) {
      return client.patch(`builder/data-source/${dataSourceId}/`, values)
    },
    delete(dataSourceId) {
      return client.delete(`builder/data-source/${dataSourceId}/`)
    },
    move(dataSourceId, beforeId) {
      return client.patch(`builder/data-source/${dataSourceId}/move/`, {
        before_id: beforeId,
      })
    },
    dispatch(
      dataSourceId,
      dispatchContext,
      dispatchRefinements,
      signal = null
    ) {
      const params = prepareDispatchParams(dispatchRefinements)

      const config = { params }

      if (signal !== null) {
        config.signal = signal
      }

      return client.post(
        `builder/data-source/${dataSourceId}/dispatch/`,
        { metadata: dispatchContext },
        config
      )
    },
    dispatchAll(pageId, params) {
      return client.post(`builder/page/${pageId}/dispatch-data-sources/`, {
        metadata: params,
      })
    },
    /**
     * Group multiple calls in one query to optimize perfs
     */
    getRecordNames: groupGetNameCalls(async (argList) => {
      // [[dataSourceId, recordIds, mode, builderId], ...]
      //    ->{ <mode>:<builderId>:<dataSourceId>: Array<with all record ids> }
      const dataSourceMap = argList.reduce(
        (acc, [dataSourceId, recordIds, mode, builderId]) => {
          const key = `${mode}:${builderId || ''}:${dataSourceId}`
          if (!acc[key]) {
            acc[key] = { mode, builderId, dataSourceId, recordIds: new Set() }
          }
          recordIds.forEach(acc[key].recordIds.add, acc[key].recordIds)
          return acc
        },
        {}
      )

      const data = Object.fromEntries(
        await Promise.all(
          Object.entries(dataSourceMap).map(
            async ([key, { mode, builderId, dataSourceId, recordIds }]) => {
              try {
                const { data } = await client.get(
                  mode === 'preview'
                    ? getBuilderPreviewApiPath(
                        builderId,
                        `data-sources/${dataSourceId}/record-names/`
                      )
                    : mode === 'public'
                      ? `builder/domains/published/data-source/${dataSourceId}/record-names/`
                      : `builder/data-source/${dataSourceId}/record-names/`,
                  {
                    params: {
                      record_ids: Array.from(recordIds)
                        .map(csvEscape)
                        .join(','),
                    },
                  }
                )
                return [key, data]
              } catch (e) {
                return [key, e]
              }
            }
          )
        )
      )

      return (dataSourceId, recordIds, mode, builderId) => {
        const key = `${mode}:${builderId || ''}:${dataSourceId}`
        if (!data[key]) {
          return null
        }
        if (data[key] instanceof Error) {
          throw data[key]
        }
        return Object.fromEntries(
          Object.entries(data[key]).filter(([key]) =>
            Array.from(recordIds)
              .map((id) => `${id}`)
              .includes(key)
          )
        )
      }
    }),
  }
}
