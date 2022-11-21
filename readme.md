# gOdoo-RPC

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

### Bump / Release Version

- Trigger [Version Bump](https://github.com/OpenJKSoftware/gOdoo-rpc/actions/workflows/version-bump.yml) pipeline with appropriate target.
- Merge the created PullRequest. Name: `:shipit: Bump to Version: <versionnumber>`
- This will create a Tag on `main`
- Create a release from this Tag. A Pipeline will automatically push to [Pypi](https://pypi.org/project/gOdoo-rpc/)
