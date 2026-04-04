import shutil
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, BackgroundTasks
import main as cli_main

router = APIRouter()
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"

@router.post("/upload")
async def upload_files(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    saved_files = []
    
    for file in files:
        if file.filename:
            path = RAW_DIR / file.filename
            with path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file.filename)
            
    background_tasks.add_task(cli_main.parse_command, RAW_DIR, False)

    return {"status": "processing_started", "files": saved_files}
