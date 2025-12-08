const { rowSample } = require('../samples/row')
const {
  getRowInputValues,
  prepareInputDataForBaserow
} = require('../helpers')

const updateRowInputFields = [
  {
    key: 'tableID',
    label: 'Table ID',
    type: 'integer',
    required: true,
    altersDynamicFields: true,
    helpText:
      'Please enter the table ID where the row must be updated. ' +
      'You can find the ID by clicking on the three dots next to the table. ' +
      'It’s the number between brackets.'
  },
  {
    key: 'rowID',
    label: 'Row ID',
    type: 'string',
    required: true,
    helpText:
      'Enter a single row ID or comma-separated IDs to update multiple rows at once.'
  },
]

const updateRow = async (z, bundle) => {
  const rowData = await prepareInputDataForBaserow(z, bundle)

  const rowIds = bundle.inputData.rowID.includes(',')
    ? bundle.inputData.rowID.split(',').map(id => id.trim())
    : [bundle.inputData.rowID]

  const rowIdPath = rowIds.join(',')

  const response = await z.request({
    url: `${bundle.authData.apiURL}/api/database/rows/table/${bundle.inputData.tableID}/${rowIdPath}/`,
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      Authorization: `Token ${bundle.authData.apiToken}`,
    },
    params: {
      user_field_names: 'true',
    },
    body: rowData,
  })

  return response.json
}

module.exports = {
  key: 'updateRow',
  noun: 'Row',
  display: {
    label: 'Update Row',
    description: 'Updates one or more existing rows.'
  },
  operation: {
    perform: updateRow,
    sample: rowSample,
    inputFields: [...updateRowInputFields, getRowInputValues]
  }
}
