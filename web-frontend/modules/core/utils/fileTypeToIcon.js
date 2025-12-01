// Original file at
// https://github.com/LoicMahieu/mimetype-to-fontawesome/blob/master/index.js

const mapping = [
  ['baserow-icon-file-image', /^image\//],
  ['baserow-icon-file-audio', /^audio\//],
  ['baserow-icon-file-video', /^video\//],
  ['baserow-icon-file-pdf', 'application/pdf'],
  ['iconoir-empty-page', 'text/plain'],
  ['baserow-icon-file-csv', 'text/csv'],
  ['baserow-icon-file-code', ['text/html', 'text/javascript']],
  [
    'baserow-icon-file-archive',
    [
      /^application\/x-(g?tar|xz|compress|bzip2|g?zip)$/,
      /^application\/x-(7z|rar|zip)-compressed$/,
      /^application\/(zip|gzip|tar)$/,
    ],
  ],
  [
    'baserow-icon-file-word',
    [
      /ms-?word/,
      'application/vnd.oasis.opendocument.text',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ],
  ],
  [
    'baserow-icon-file-powerpoint',
    [
      /ms-?powerpoint/,
      'application/vnd.oasis.opendocument.presentation',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    ],
  ],
  [
    'baserow-icon-file-excel',
    [
      /ms-?excel/,
      'application/vnd.oasis.opendocument.spreadsheet',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ],
  ],
  ['iconoir-attachment'],
]

function match(mimetype, cond) {
  if (Array.isArray(cond)) {
    return cond.reduce(function (v, c) {
      return v || match(mimetype, c)
    }, false)
  } else if (cond instanceof RegExp) {
    return cond.test(mimetype)
  } else if (cond === undefined) {
    return true
  } else {
    return mimetype === cond
  }
}

const cache = {}

export function mimetype2icon(mimetype) {
  if (cache[mimetype]) {
    return cache[mimetype]
  }

  for (let i = 0; i < mapping.length; i++) {
    if (match(mimetype, mapping[i][1])) {
      cache[mimetype] = mapping[i][0]
      return mapping[i][0]
    }
  }
}
