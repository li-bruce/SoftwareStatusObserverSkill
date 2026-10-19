"""Application entrypoint, runnable with the observer folders absent."""
import json
from pathlib import Path
import sys
from app.service import Delivery
from app.store import Store


def main():
    store = Store()
    app = Delivery(store)
    app.command('grant', id='G1', expires=200)
    result = app.execute()
    print(json.dumps({'state':result['state'],'effects':len(result['effects'])}))
    store.close()
    return 0 if result['state']=='completed' and len(result['effects'])==1 else 1


if __name__ == '__main__':
    raise SystemExit(main())
