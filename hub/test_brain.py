import os

os.environ["DB_PATH"] = "../project-1-brain/ja_assure.db"

from hands.db import connect, init_schema, insert_dynamic
from hub.brain_adapter import BrainAdapter
from hub.config import get_hub_settings

conn = connect()
init_schema(conn)

aid = insert_dynamic(conn, "assets", {
    "brand": "Jade",
    "platform": "LinkedIn",
    "region": "Singapore",
    "body_text": "Test post about jewellers block cover.",
    "status": "pending",
})

result = BrainAdapter(get_hub_settings()).run_compliance(conn, aid)

print(result)

conn.close()
