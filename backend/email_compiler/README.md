## How to run

The Docker development environment (`just dc-dev up -d`) automatically starts
`baserowEmailCompiler.js` in watch mode, so no need to run this manually if you
are using it.

For manual compilation, in this directory run:
* `yarn install`
* To watch: `yarn run watch`
* To compile once and exit: `yarn run compile`
