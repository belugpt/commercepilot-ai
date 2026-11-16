# Contributing

Use Python 3.11+, create a virtual environment and install `pip install -e ".[dev]"`. Run `python -m pytest -q` before submitting changes. Include tests for meaningful behavior and failure paths, tenant boundaries, migrations and updated docs. Never commit secrets, local databases or merchant data.

Keep patches focused. Discuss new integration permissions or breaking extension contracts in an issue before implementation. Include problem, resulting behavior, verification and limitations in pull requests. Architecture changes need a decision record under docs/adr. Use official provider documentation and clearly label fixtures. No mock production claims.

Version 0.x is experimental; MIT permits reuse and modification. Contributors retain copyright and submit their contributions under MIT. Maintainer/review and release ownership will be assigned when the repository is published.
