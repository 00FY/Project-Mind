from click.testing import CliRunner
from projectmind.platform.cli.main import cli

r = CliRunner().invoke(cli, ["doctor", "--json-output"])
with open("debug_doctor.txt", "w", encoding="utf8") as f:
    f.write(repr(r.output))
