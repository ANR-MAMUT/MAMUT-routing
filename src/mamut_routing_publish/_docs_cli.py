"""Click views of the three Typer CLIs, for the ``mkdocs-click`` reference pages.

Only the documentation build imports this module (see ``docs/reference/cli/``).
``typer.main.get_command`` returns the underlying click group, which
``mkdocs-click`` walks to render every command, option and argument. The
module is inert otherwise: it is never imported by the publisher itself.
"""

from __future__ import annotations

from typer.main import get_command

from mamut_routing_lib.cli import app as _lib_app
from mamut_routing_publish.cli import app as _publish_app
from mamut_routing_tools.cli import app as _tools_app

mamut_routing = get_command(_lib_app)
mamut_tools = get_command(_tools_app)
mamut_routing_publish = get_command(_publish_app)
