const { rowSample } = require('../samples/row')

const deleteRowInputFields = [
  {
    key: 'tableID',
    label: 'Table ID',
    type: 'integer',
    required: true,
    helpText: 'Please enter the table ID where the row must be deleted in. You can ' +
      'find the ID by clicking on the three dots next to the table. It\'s the number ' +
      'between brackets.'
  },
  {
    key: 'rowID',
    label: 'Row ID',
    type: 'string',
    required: true,
    helpText: 'Please enter the row ID that must be deleted. You can provide a single ID or comma-separated IDs to delete multiple rows at once.'
  },
]

const DeleteRow = async (z, bundle) => {
  const rowIds = bundle.inputData.rowID.includes(',')
    ? bundle.inputData.rowID.split(',').map(id => parseInt(id.trim()))
    : [parseInt(bundle.inputData.rowID)]
  
  if (rowIds.length === 1) {
    const rowDeleteRequest = await z.request({
      url: `${bundle.authData.apiURL}/api/database/rows/table/${bundle.inputData.tableID}/${rowIds[0]}/`,
      method: 'DELETE',
      headers: {
          'Accept': 'application/json',
          'Authorization': `Token ${bundle.authData.apiToken}`,
      },
    })

    return rowDeleteRequest.status === 204
      ? { message: `Row ${rowIds[0]} deleted successfully.` }
      : { message: 'A problem occurred during DELETE operation. The row was not deleted.' }
  } else {
    const rowBatchDeleteRequest = await z.request({
      url: `${bundle.authData.apiURL}/api/database/rows/table/${bundle.inputData.tableID}/${rowIds.join(',')}/`,
      method: 'DELETE',
      headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Authorization': `Token ${bundle.authData.apiToken}`,
      },
      body: { items: rowIds },
    })

    return rowBatchDeleteRequest.status === 204
      ? { message: `Rows ${rowIds.join(', ')} deleted successfully.` }
      : { message: 'A problem occurred during batch DELETE operation.' }
  }
}

module.exports = {
  key: 'deleteRow',
  noun: 'Row',
  display: {
    label: 'Delete Row',
    description: 'Deletes an existing row.'
  },
  operation: {
    perform: DeleteRow,
    sample: rowSample,
    inputFields: deleteRowInputFields
  }
}
