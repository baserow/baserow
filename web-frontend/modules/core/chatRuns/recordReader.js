// JSON encoders escape newlines, so this separator cannot occur in a record.
const RECORD_DELIMITER = '\n\n'
const STREAM_LOG_PREFIX = '[chat run stream]'
const CORRUPT_RECORD_PREVIEW_LENGTH = 200

/**
 * Turns the cumulative `xhr.responseText` into whole delimiter-terminated
 * records and hands them to the consumer one at a time, in arrival order.
 *
 * @param {Function} readResponseText Returns everything received so far.
 * @param {Function} onRecord Called with each parsed record, may be async.
 * @returns {{read: Function, flush: Function}} Reader driven by the XHR events.
 */
export function createRecordReader(readResponseText, onRecord) {
  let consumed = 0
  let pending = ''
  let dispatched = Promise.resolve()

  // Taking records synchronously keeps the buffer consistent across progress events.
  const take = (isFinal) => {
    const responseText = readResponseText()
    pending += responseText.substring(consumed)
    consumed = responseText.length

    const records = pending.split(RECORD_DELIMITER)
    pending = isFinal ? '' : records.pop()
    return records.filter((record) => record.trim() !== '')
  }

  const dispatch = (records) => {
    dispatched = dispatched.then(async () => {
      for (const record of records) {
        let update
        try {
          update = JSON.parse(record)
        } catch (error) {
          console.error(`${STREAM_LOG_PREFIX} dropped an unparsable record`, {
            length: record.length,
            preview: record.slice(0, CORRUPT_RECORD_PREVIEW_LENGTH),
            error,
          })
          continue
        }
        try {
          await onRecord(update)
        } catch (error) {
          console.error(`${STREAM_LOG_PREFIX} record handler failed`, error)
        }
      }
    })
    return dispatched
  }

  return {
    read: () => dispatch(take(false)),
    flush: () => dispatch(take(true)),
  }
}
