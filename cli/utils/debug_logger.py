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
            content = msg.content

            if isinstance(content, str):
                text = content.strip()

            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                text = "".join(text_parts).strip()

            else:
                text = str(content).strip()

            f.write(text + "\n")

        f.write("\n")
