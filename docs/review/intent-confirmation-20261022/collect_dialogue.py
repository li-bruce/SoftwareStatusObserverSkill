"""Export visible trial dialogue and a tool index; never export reasoning or system prompts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(c.get('text', '') for c in content if isinstance(c, dict) and c.get('type') in {'input_text', 'output_text', 'text'})
    return ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rollout', type=Path)
    parser.add_argument('--out', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    dialogue, tools = [], []
    seen = set()
    for line in args.rollout.read_text(encoding='utf-8').splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # An active writer may have a partial last line; next export rereads it.
        payload = record.get('payload', {})
        if record.get('type') != 'response_item':
            continue
        kind = payload.get('type')
        role, body = None, None
        if kind == 'message' and payload.get('role') == 'assistant' and payload.get('phase') in {'commentary', 'final', 'final_answer'}:
            role, body = '开发助手', text_content(payload.get('content'))
        elif kind == 'message' and payload.get('role') == 'user':
            value = text_content(payload.get('content'))
            if not value.lstrip().startswith(('<environment_context>', '<system-reminder>')):
                role, body = '需求方/协调者', value
        elif kind == 'function_call_output' and payload.get('name') in {'create_thread', 'send_message_to_thread'}:
            value = text_content(payload.get('output'))
            match = re.search(r'<input>([\s\S]*?)</input>', value)
            if match:
                role, body = '需求方/协调者', match.group(1)
        if role and body:
            key = payload.get('id') or (record.get('timestamp'), role, body)
            if key not in seen:
                seen.add(key)
                dialogue.append({'timestamp': record.get('timestamp'), 'id': payload.get('id'), 'role': role, 'phase': payload.get('phase'), 'text': body})
        if kind in {'custom_tool_call', 'function_call'}:
            raw = payload.get('input', payload.get('arguments', ''))
            tools.append({'timestamp': record.get('timestamp'), 'id': payload.get('id'), 'call_id': payload.get('call_id'), 'name': payload.get('name'), 'input': raw})
        elif kind in {'custom_tool_call_output', 'function_call_output'} and payload.get('name') not in {'create_thread', 'send_message_to_thread'}:
            # Retain call correlation, not broad filesystem reads or private memory contents.
            tools.append({'timestamp': record.get('timestamp'), 'id': payload.get('id'), 'call_id': payload.get('call_id'), 'kind': 'tool_output', 'output_retained': False})
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in [('dialogue.json', dialogue), ('tool-index.json', tools)]:
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    chunks = ['# 实际对话记录\n\n需求方由协调会话模拟。以下从新会话记录提取实际可见消息，包含过程说明；没有加入推理过程、系统提示或重写过的示例对话。原始工具调用索引见 tool-index.json，检查输出保存在项目 evidence 中。\n']
    for i, item in enumerate(dialogue, 1):
        label = item['role'] + (' · 过程说明' if item['phase'] == 'commentary' else '')
        chunks.append(f"## {i}. {label}\n\n{item['timestamp']} · `{item['id']}`\n\n{item['text']}\n")
    (args.out / 'dialogue.md').write_text('\n'.join(chunks), encoding='utf-8')
    print(json.dumps({'messages': len(dialogue), 'tool_records': len(tools)}))


if __name__ == '__main__':
    main()
