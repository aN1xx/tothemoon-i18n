#!/usr/bin/env python3
"""
Batch API translation - bypasses rate limits!
Converts translation task to OpenAI Batch API format.
"""

import json
from pathlib import Path
from typing import Dict


def create_batch_requests(
    source_en: Dict, draft_ru: Dict, system_prompt: str, batch_size: int = 50
) -> list:
    """Create batch API requests."""
    requests = []

    # Group keys into batches
    keys = list(source_en.keys())
    for i in range(0, len(keys), batch_size):
        batch_keys = keys[i : i + batch_size]
        batch_data = {key: source_en[key] for key in batch_keys}

        # Create user message
        user_msg = f"""Translate the following UI strings to Russian.
Return a JSON object with the same keys.

Keys to translate:
{json.dumps(batch_data, ensure_ascii=False, indent=2)}
"""

        # Add draft hints if available
        hints = {k: draft_ru.get(k) for k in batch_keys if k in draft_ru}
        if hints:
            hints_json = json.dumps(hints, ensure_ascii=False, indent=2)
            user_msg += f"\n\nExisting translations (use as hints):\n{hints_json}"

        requests.append(
            {
                "custom_id": f"batch-{i // batch_size}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4.1-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.3,
                },
            }
        )

    return requests


def main():
    # Load data
    print("[INFO] Loading source files...")
    source_en = json.loads(Path("data/TTM_EN.json").read_text())
    draft_ru = json.loads(Path("data/TTM_RU_bad.json").read_text())

    # Load system prompt
    system_prompt = Path("prompts/system.txt").read_text()
    system_prompt = system_prompt.replace("<<TARGET_LOCALE>>", "ru")
    system_prompt = system_prompt.replace("<<TARGET_LANGUAGE_NAME>>", "Russian")

    print(f"[INFO] Total keys: {len(source_en)}")

    # Create batch requests
    print("[INFO] Creating batch requests...")
    requests = create_batch_requests(source_en, draft_ru, system_prompt, batch_size=50)
    print(f"[INFO] Created {len(requests)} batch requests")

    # Save to JSONL file
    output_file = Path("batch_input.jsonl")
    with output_file.open("w", encoding="utf-8") as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    print(f"[OK] Batch file created: {output_file}")
    print("\nNext steps:")
    print("1. Upload file to OpenAI:")
    print("   curl https://api.openai.com/v1/files \\")
    print("     -H 'Authorization: Bearer $OPENAI_API_KEY' \\")
    print("     -F purpose=batch \\")
    print(f"     -F file=@{output_file}")
    print("\n2. Create batch (use file_id from step 1):")
    print("   curl https://api.openai.com/v1/batches \\")
    print("     -H 'Authorization: Bearer $OPENAI_API_KEY' \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{")
    print('       "input_file_id": "file-abc123",')
    print('       "endpoint": "/v1/chat/completions",')
    print('       "completion_window": "24h"')
    print("     }'")
    print("\n3. Check status (use batch_id from step 2):")
    print("   curl https://api.openai.com/v1/batches/batch_abc123 \\")
    print("     -H 'Authorization: Bearer $OPENAI_API_KEY'")
    print("\n4. Download results when status=completed")


if __name__ == "__main__":
    main()
