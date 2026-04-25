import json

from memisalluneed.cli import main


def test_cli_init_add_list_search_show_and_export(tmp_path, capsys):
    db_path = tmp_path / "memory.db"

    assert main(["init", "--db", str(db_path)]) == 0
    assert main(["add", "Everything before now is memory.", "--db", str(db_path)]) == 0
    assert main(["list", "--db", str(db_path)]) == 0
    list_output = capsys.readouterr().out
    assert "Everything before now is memory." in list_output

    assert main(["search", "what is memory", "--db", str(db_path)]) == 0
    search_output = capsys.readouterr().out
    assert "score=" in search_output
    memory_id = search_output.split()[0]

    assert main(["show", memory_id, "--json", "--db", str(db_path)]) == 0
    show_output = capsys.readouterr().out
    assert json.loads(show_output)["id"] == memory_id

    assert main(["export", "--db", str(db_path)]) == 0
    export_output = capsys.readouterr().out
    assert (
        json.loads(export_output.splitlines()[0])["content"]
        == "Everything before now is memory."
    )


def test_cli_show_missing_returns_error(tmp_path, capsys):
    db_path = tmp_path / "memory.db"

    assert main(["show", "missing", "--db", str(db_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Memory not found: missing" in captured.err


def test_cli_add_rejects_invalid_metadata_json(tmp_path, capsys):
    db_path = tmp_path / "memory.db"

    assert (
        main(
            [
                "add",
                "Memory with bad metadata.",
                "--metadata",
                "{bad",
                "--db",
                str(db_path),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Invalid metadata JSON" in captured.err
