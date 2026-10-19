# Delivery core / 数据交付核心

This package retains the application's state machine, activities, authorization
and SQLite commit logic. The observer and viewer are absent; the application-owned
observation interface remains a no-op when no callback is attached.

本包保留真实状态机、活动约束、授权判断与提交逻辑，移除观测实现和页面。

Use Python 3.11–3.13:

```bash
python -m pip install -r requirements.txt
python main.py
```

Expected / 预期输出：`{"state": "completed", "effects": 1}`

This command uses synthetic text and an in-memory SQLite database.
本命令使用合成文本与内存数据库。依赖及许可证见随包文件。
