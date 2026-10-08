from pathlib import Path
from datetime import datetime

# Paths
ROOT = Path("./root").resolve()
LOGS = Path("./logs").resolve()
DATA = Path("./data").resolve()
CFIG = Path("./config.json").resolve()
LOGF = LOGS / f"server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
DABA = DATA / "database.db"