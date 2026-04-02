from __future__ import annotations

import typer

app = typer.Typer(
    name="covenant",
    help="Behavioral contract CLI for AI agents.",
    no_args_is_help=True,
)


def _register_commands() -> None:
    from covenant_cli.commands import audit, diff, generate, init, publish, sign, validate

    app.command("init")(init.init_cmd)
    app.command("validate")(validate.validate_cmd)
    app.command("sign")(sign.sign_cmd)
    app.command("diff")(diff.diff_cmd)
    app.command("generate")(generate.generate_cmd)
    app.command("publish")(publish.publish_cmd)
    app.command("audit")(audit.audit_cmd)


_register_commands()

if __name__ == "__main__":
    app()
