from memisalluneed.cli import build_parser


def test_chat_parser_accepts_phase2_options():
    parser = build_parser()

    args = parser.parse_args(
        [
            "chat",
            "--config",
            "runtime.toml",
            "--db",
            "memory.db",
            "--chat-provider",
            "openai",
            "--chat-model",
            "gpt-4.1",
            "--formation-provider",
            "qwen",
            "--formation-model",
            "qwen-turbo",
            "--max-turns",
            "6",
            "--max-tokens",
            "100000",
            "--recall-top-k",
            "5",
            "--new-session",
        ]
    )

    assert args.command == "chat"
    assert args.config == "runtime.toml"
    assert args.db == "memory.db"
    assert args.chat_provider == "openai"
    assert args.formation_provider == "qwen"
    assert args.new_session is True
