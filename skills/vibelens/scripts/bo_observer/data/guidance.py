"""Storage selection questions and implementation tasks, without adding business rules."""

OPTIONS = [
    {
        "id": "sqlite",
        "label": "SQLite + SQLAlchemy",
        "use": "A local Python application with relational records.",
    },
    {
        "id": "postgresql",
        "label": "PostgreSQL + SQLAlchemy or a native model layer",
        "use": "A shared service with relational records and transactions.",
    },
    {
        "id": "mongodb",
        "label": "MongoDB + Mongoose or explicit document models",
        "use": "The existing requirement stores flexible nested documents.",
    },
    {
        "id": "neo4j",
        "label": "Neo4j + explicit node and relationship models",
        "use": "The existing requirement depends on relationship traversal.",
    },
    {
        "id": "redis",
        "label": "Redis + explicit key patterns",
        "use": "The existing requirement needs a cache or key-value data.",
    },
]


def storage_questions(config=None, *, required=False):
    """Reuse recorded choices and send model/export/probe configuration to the coding agent."""
    human, coding = [], []
    stores = (config or {}).get("stores", [])
    if not stores and required:
        stores = [{"id": "application", "label": "Application storage"}]
    for store in stores:
        selection = store.get("selection", {})
        confirmed = selection.get("source") == "user" and all(
            isinstance(selection.get(key), str) and selection[key].strip()
            for key in ("answer", "locator")
        )
        if not confirmed:
            human.append(
                {
                    "id": "storage:" + store["id"],
                    "audience": "user",
                    "question": "Which database should this project use? Reuse an existing choice; select according to the data already described.",
                    "purpose": "confirm_implementation_choice",
                    "options": OPTIONS,
                    "instruction": "Explain the relevant tradeoff in the user's language. Recommend only options fitting the stated workload. The user may name another database; disclose adapter gaps before implementation.",
                }
            )
        coding.append(
            {
                "id": "storage-wiring:" + store["id"],
                "audience": "coding",
                "depends_on": [] if confirmed else ["storage:" + store["id"]],
                "tasks": [
                    "Record the confirmed choice and locator in bo_stategraph/databases.json.",
                    "Configure the native ORM/ODM or explicit model layer; export its public metadata as bo-data-catalog/v1.",
                    "Bind each read, write, transaction and selected transformation to source, targets, selected fields and real acceptance cases.",
                    "Use bo_ wiring and BO adapters; exclude observer-only connections, metadata reads and transport at capture entry.",
                    "Run bo_db sync, independent check, actual runtime cases and existing change_sync gates after code or migration changes.",
                ],
            }
        )
    return {"user": human, "coding": coding}
