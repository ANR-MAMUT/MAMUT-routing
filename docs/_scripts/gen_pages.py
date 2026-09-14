"""mkdocs-gen-files driver: write the generated documentation pages.

Executed by the ``gen-files`` plugin at build time (via ``runpy``, so there is
no ``__main__`` guard). All the logic lives in
``mamut_routing_publish.docs_pages`` so it can be unit-tested without MkDocs.
"""

from pathlib import Path

import mkdocs_gen_files

from mamut_routing_publish.docs_pages import generate_docs_pages

repo_root = Path(mkdocs_gen_files.config.config_file_path).parent

for page in generate_docs_pages(repo_root):
    with mkdocs_gen_files.open(page.path, "w") as handle:
        handle.write(page.markdown)
