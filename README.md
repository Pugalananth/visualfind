# VisualFind

Visual search over video: a reference image is mandatory, the video is an upload or an HTTP(S) URL.
FastAPI + MongoDB backend, React (Vite) frontend.

## Run
```bash
# backend
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                      # set MONGODB_URI
cp /path/to/encoder_tri_epoch5.pth models/  # trained encoder checkpoint (loaded strictly)
python -m app.create_admin                # create the first ADMIN (prompts for name/email/password)
uvicorn app.main:app --port 8000

# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173 (proxies /api to :8000)
npm run build                               # production bundle; the API serves frontend/dist if present
```

## Notes
- If the checkpoint is missing or does not match the encoder architecture, System status shows the Encoder as not ready and searches fail with a clear error. The app never runs on random weights.
- Tests: `cd backend && pytest` (uses an in-memory Mongo mock and real YOLO; the encoder checkpoint in tests is a random-weight fixture, so they check plumbing, not embedding quality).
