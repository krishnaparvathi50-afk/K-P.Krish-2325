import importlib.util
import os
from pathlib import Path

INNER_APP = Path(__file__).resolve().parent / "FRAUD_TRANSACTION" / "app.py"

spec = importlib.util.spec_from_file_location("fraud_transaction_app", INNER_APP)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load Flask app from {INNER_APP}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
