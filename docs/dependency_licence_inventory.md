# Dependency and licence inventory (SDLC G3.08)

Generated with `pip-licenses==4.5.1` against a clean virtualenv containing
only `backend/requirements.txt` (not the dev venv, which has extra tooling
installed) — every row below is a direct or transitive runtime dependency
that actually ships, nothing more. Regenerate after any `requirements.txt`
change:

```
python -m venv /tmp/clean && source /tmp/clean/*/activate
pip install -r backend/requirements.txt pip-licenses==4.5.1
pip-licenses --with-urls --format=markdown --order=name > docs/dependency_licence_inventory.md
```

**`License: UNKNOWN` is the tool's limitation, not a cleared finding**: it
means the package's installed metadata doesn't declare a machine-readable
license classifier — most of these (fastapi, starlette, cryptography,
pytest, anyio, click, httptools, idna, packaging, pycparser, typing packages)
are known-permissive (MIT/Apache/BSD) by reputation, but that has not been
individually confirmed against each project's own LICENSE file here, so
none are asserted as cleared. `psycopg2-binary` is LGPL — acceptable for
dynamic linking as used here, but the one entry in this table that is not
plain MIT/BSD/Apache and worth knowing about if licence terms ever matter
for distribution.

No CI enforcement of this list exists yet (e.g. failing a build on a newly
introduced copyleft/unknown dependency) — this is a point-in-time inventory,
regenerated manually, not an automated gate.

| Name              | Version   | License                                             | URL                                                        |
|-------------------|-----------|-----------------------------------------------------|------------------------------------------------------------|
| Mako              | 1.4.1     | UNKNOWN                                             | https://www.makotemplates.org/                             |
| MarkupSafe        | 3.0.3     | UNKNOWN                                             | https://github.com/pallets/markupsafe/                     |
| PyYAML            | 6.0.3     | MIT License                                         | https://pyyaml.org/                                        |
| Pygments          | 2.21.0    | UNKNOWN                                             | https://pygments.org                                       |
| SQLAlchemy        | 2.0.35    | MIT License                                         | https://www.sqlalchemy.org                                 |
| alembic           | 1.13.2    | MIT License                                         | https://alembic.sqlalchemy.org                             |
| annotated-doc     | 0.0.5     | UNKNOWN                                             | https://github.com/fastapi/annotated-doc                   |
| annotated-types   | 0.8.0     | MIT License                                         | https://github.com/annotated-types/annotated-types         |
| anyio             | 4.15.1    | UNKNOWN                                             | https://anyio.readthedocs.io/en/stable/versionhistory.html |
| bcrypt            | 4.0.1     | Apache Software License                             | https://github.com/pyca/bcrypt/                            |
| certifi           | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0)                | https://github.com/certifi/python-certifi                  |
| cffi              | 2.1.1     | UNKNOWN                                             | https://cffi.readthedocs.io/en/latest/whatsnew.html        |
| click             | 8.5.0     | UNKNOWN                                             | https://github.com/pallets/click/                          |
| colorama          | 0.4.6     | BSD License                                         | https://github.com/tartley/colorama                        |
| cryptography      | 50.0.1    | UNKNOWN                                             | https://github.com/pyca/cryptography                       |
| dnspython         | 2.8.0     | ISC License (ISCL)                                  | https://www.dnspython.org                                  |
| email_validator   | 2.2.0     | The Unlicense (Unlicense)                           | https://github.com/JoshData/python-email-validator         |
| fastapi           | 0.141.1   | UNKNOWN                                             | https://github.com/fastapi/fastapi                         |
| h11               | 0.16.0    | MIT License                                         | https://github.com/python-hyper/h11                        |
| httpcore          | 1.0.9     | BSD License                                         | https://www.encode.io/httpcore/                            |
| httptools         | 0.8.0     | UNKNOWN                                             | https://github.com/MagicStack/httptools                    |
| httpx             | 0.27.2    | BSD License                                         | https://github.com/encode/httpx                            |
| idna              | 3.20      | UNKNOWN                                             | https://github.com/kjd/idna                                |
| iniconfig         | 2.3.0     | UNKNOWN                                             | https://github.com/pytest-dev/iniconfig                    |
| itsdangerous      | 2.2.0     | BSD License                                         | https://github.com/pallets/itsdangerous/                   |
| packaging         | 26.3      | UNKNOWN                                             | https://github.com/pypa/packaging                          |
| passlib           | 1.7.4     | BSD                                                 | https://passlib.readthedocs.io                             |
| pluggy            | 1.6.0     | MIT License                                         | UNKNOWN                                                    |
| psycopg2-binary   | 2.9.10    | GNU Library or Lesser General Public License (LGPL) | https://psycopg.org/                                       |
| pycparser         | 3.0       | UNKNOWN                                             | https://github.com/eliben/pycparser                        |
| pydantic          | 2.9.2     | MIT License                                         | https://github.com/pydantic/pydantic                       |
| pydantic-settings | 2.5.2     | MIT License                                         | https://github.com/pydantic/pydantic-settings              |
| pydantic_core     | 2.23.4    | MIT License                                         | https://github.com/pydantic/pydantic-core                  |
| pyotp             | 2.9.0     | MIT License                                         | https://github.com/pyotp/pyotp                             |
| pytest            | 9.1.1     | UNKNOWN                                             | https://docs.pytest.org/en/latest/                         |
| python-dotenv     | 1.2.3     | BSD-3-Clause                                        | https://github.com/theskumar/python-dotenv                 |
| sniffio           | 1.3.1     | Apache Software License; MIT License                | https://github.com/python-trio/sniffio                     |
| starlette         | 1.6.0     | UNKNOWN                                             | https://github.com/Kludex/starlette                        |
| typing-inspection | 0.4.4     | UNKNOWN                                             | https://github.com/pydantic/typing-inspection              |
| typing_extensions | 4.16.0    | UNKNOWN                                             | https://github.com/python/typing_extensions                |
| uvicorn           | 0.30.6    | BSD License                                         | https://www.uvicorn.org/                                   |
| watchfiles        | 1.2.0     | MIT License                                         | https://github.com/samuelcolvin/watchfiles                 |
| websockets        | 17.1      | UNKNOWN                                             | https://github.com/python-websockets/websockets            |
