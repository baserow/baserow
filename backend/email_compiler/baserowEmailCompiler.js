'use strict'

const mjml2html = require('mjml')
const fs = require('fs')
const Eta = require('eta')
const path = require('path')
const { globSync } = require('glob')
const chokidar = require('chokidar')

const BASEROW_BACKEND_SRC_DIR = path.join(__dirname, '..', 'src')
const MJML_FILE_SEARCH_ROOT = process.env.MJML_FILE_SEARCH_ROOT
  ? process.env.MJML_FILE_SEARCH_ROOT
  : BASEROW_BACKEND_SRC_DIR
const MJML_ETA_FILE_GLOB = path.join(MJML_FILE_SEARCH_ROOT, '**', '*.mjml.eta')
const ETA_LAYOUT_FILE_GLOB = path.join(
  MJML_FILE_SEARCH_ROOT,
  '**',
  '*.layout.eta'
)

/**
 * Given a .mjml.eta file first renders the eta template to get a .mjml file and then
 * renders the mjml file to a normal html django template file.
 *
 * @param mjmlEtaFile The path to the .mjml.eta file.
 */
function compileEtaAndMjml(mjmlEtaFile) {
  const Reset = '\x1B[0m'
  const FgGreen = '\x1B[32m'

  console.log(`Compiling ${mjmlEtaFile}`)
  Eta.configure({
    // Set views to the directory of the file to template so it can use layout(path)
    // statements relative to its own directory.
    views: path.dirname(mjmlEtaFile),
  })

  const tmplText = fs.readFileSync(mjmlEtaFile, 'utf8')
  const mjmlText = Eta.render(tmplText, {})

  const html = mjml2html(mjmlText, {
    validationLevel: 'strict',
    beautify: true,
  }).html

  const targetHtmlFile = mjmlEtaFile.replace('.mjml.eta', '.html')
  console.log(
    `${FgGreen}Writing compiled email template to ${targetHtmlFile}${Reset}`
  )
  fs.writeFileSync(targetHtmlFile, html)
}

function recompileAllEtaAndMjmlFilesAfterLayoutFileChanges(layoutFile) {
  console.log(`Layout file changed (${layoutFile})`)
  const files = globSync(MJML_ETA_FILE_GLOB)
  files.forEach((file) => {
    compileEtaAndMjml(file)
  })
}

/**
 * Watches *.mjml.eta and *.layout.eta files and runs the eta templater followed by
 * the mjml cli over them initial run and on change if run in watch mode.
 *
 * We use the simple javascript eta templating engine to first extend any base layout
 * files as MJML does not come with any built in templating. Secondly we use the MJML
 * cli tool to convert the MJML files into html ready to be used as a Django template.
 *
 * @param args If command line arg is watch then continually watches the files,
 * otherwise just runs templating/compiling once over matching files and exits.
 */
function main(args) {
  const watchMode = args.length > 0 && args[0] === 'watch'

  const mjmlEtaWatcher = chokidar
    .watch(MJML_ETA_FILE_GLOB, { persistent: watchMode })
    .on('add', compileEtaAndMjml)

  if (watchMode) {
    console.log(
      'Watching and recompiling changes to files found using glob pattern' +
        ` ${MJML_ETA_FILE_GLOB}`
    )

    mjmlEtaWatcher.on('change', compileEtaAndMjml)
    chokidar
      .watch(ETA_LAYOUT_FILE_GLOB, { persistent: watchMode })
      .on('change', recompileAllEtaAndMjmlFilesAfterLayoutFileChanges)
  }
}

const args = process.argv.slice(2)
main(args)
