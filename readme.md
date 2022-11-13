# Wodoo-RPC

Several Abstraction layers around [OdooRPC](https://odoorpc.readthedocs.io/en/latest/).

Made Possible by: [WEMPE Elektronic GmbH](https://wetech.de)

## Features

- Login to Odoo helper functions
- Importing Images from the Filesystem
- Import CSV/Json/Excel Data to Odoo via RPC
- Import res.config.settings
- import Translations
- Extend Base.Import feature with Language cols (fieldname:lang:en_US, fieldname:lang:de_DE)
- Copy Records from Odoo to Odoo via RPC and remap relational Atributes

## Development

### VS Code Devcontainer

This workspace contains a [Vscode devcontainer](https://code.visualstudio.com/docs/remote/containers).

## Gitlab Release

There are 2 Ways to start a release Pipeline:

1. Via gitlab UI
   1. Create new Pipeline in CI View
   2. Supply Variables "`BUMP_TARGET`" [Valid Values](https://python-poetry.org/docs/cli/#version) and optional "`TAG_NOTE`" to add a text to the Git Tag.
   3. Profit
2. Via Git while Pushing
   - Publish a path release: `git push -o ci.variable="BUMP_TARGET=patch"`
   - Major release with release comment `git push -o ci.variable="BUMP_TARGET=patch" -o ci.variable="TAG_NOTE=This is a super cool new version"`
