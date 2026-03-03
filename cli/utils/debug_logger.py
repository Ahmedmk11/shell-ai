from pathlib import Path
from datetime import datetime
from langchain_core.messages import BaseMessage

def append_llm_input(appender_name: str, messages: list[BaseMessage]) -> None:
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    file_path = logs_dir / "input_prompts.txt"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n\n" + "=" * 100 + "\n")
        f.write(f"APPENDER: {appender_name}\n")
        f.write(f"TIMESTAMP: {datetime.now().isoformat()}\n")
        f.write("=" * 100 + "\n")

        for msg in messages:
            f.write(f"\n[{msg.__class__.__name__}]\n")
            f.write(msg.content.strip() + "\n")

        f.write("\n")
