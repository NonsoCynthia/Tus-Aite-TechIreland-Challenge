"""Entry point for `python -m coordinator` (spec.md FR11).

Per `conductor/code_styleguides/python.md`: all logic lives in
`coordinator.app.cli.main()`; this file only calls it from
`if __name__ == '__main__':`.
"""

import sys

from coordinator.app.cli import main

if __name__ == "__main__":
    sys.exit(main())
