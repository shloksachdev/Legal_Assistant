"""TempLex GraphRAG — CLI entry point and server launcher.

Usage:
  python main.py --seed           Load seed data into KuzuDB
  python main.py --serve          Start FastAPI server
  python main.py --query "..."    Execute a single query
  python main.py                  Interactive chat mode
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="TempLex GraphRAG: Temporal Legal Reasoning Agent"
    )
    parser.add_argument("--seed", action="store_true", help="Load seed data")
    parser.add_argument("--serve", action="store_true", help="Start API server")
    parser.add_argument("--query", type=str, help="Execute a single query")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    args = parser.parse_args()

    if args.seed:
        _seed()
    elif args.serve:
        _serve(args.host, args.port)
    elif args.query:
        _query(args.query)
    else:
        _interactive()


def _seed():
    from rich.console import Console
    console = Console()
    console.print("\n[bold blue]TempLex GraphRAG[/] — Loading seed data...\n")

    from templex.ingestion.graph_populator import load_seed_data
    load_seed_data()

    console.print("[bold green]✓[/] Seed data loaded successfully.\n")


def _serve(host: str, port: int):
    import uvicorn
    from rich.console import Console
    console = Console()
    console.print(f"\n[bold blue]TempLex GraphRAG[/] — Starting server on {host}:{port}\n")
    uvicorn.run("api.server:app", host=host, port=port, reload=True)


def _query(query_text: str):
    from rich.console import Console
    from rich.markdown import Markdown
    console = Console()

    console.print("\n[bold blue]TempLex GraphRAG[/]\n")
    console.print(f"[dim]Query:[/] {query_text}\n")

    from templex.agent import chat_agent
    session_id = chat_agent.create_session()
    result = chat_agent.chat(session_id, query_text)

    console.print(Markdown(result["response"]))

    # Show tool calls
    for tc in result.get("tool_calls", []):
        console.print(f"\n  [dim]🔧 {tc['tool']}({tc['input']})[/]")
    console.print()


def _interactive():
    from rich.console import Console
    from rich.markdown import Markdown
    console = Console()

    console.print("\n[bold blue]╔══════════════════════════════════════════╗[/]")
    console.print("[bold blue]║   TempLex GraphRAG — Chat Mode           ║[/]")
    console.print("[bold blue]╚══════════════════════════════════════════╝[/]\n")
    console.print("[dim]Commands: type a message, 'seed' to load data, 'new' for new session, 'quit' to exit[/]\n")

    from templex.agent import chat_agent
    session_id = chat_agent.create_session()
    console.print(f"[dim]Session: {session_id[:8]}...[/]\n")

    while True:
        try:
            user_msg = console.input("[bold cyan]You › [/]").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_msg:
            continue
        if user_msg.lower() in ("quit", "exit", "q"):
            break
        if user_msg.lower() == "seed":
            _seed()
            continue
        if user_msg.lower() == "new":
            session_id = chat_agent.create_session()
            console.print(f"\n[dim]New session: {session_id[:8]}...[/]\n")
            continue

        console.print()
        result = chat_agent.chat(session_id, user_msg)

        # Show tool calls
        for tc in result.get("tool_calls", []):
            console.print(f"  [dim]🔧 {tc['tool']}[/]")

        console.print()
        console.print(Markdown(result["response"]))
        console.print()


if __name__ == "__main__":
    main()
