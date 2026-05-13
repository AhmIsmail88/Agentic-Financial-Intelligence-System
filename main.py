import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # Ensure .env is loaded before anything else
    load_dotenv()
    
    # Run FastAPI server
    # The port and host can be configured via env or defaults
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.api.server:app", host="0.0.0.0", port=port, reload=True)
