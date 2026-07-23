from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

import auth
import jobs
import storage
from models import Credentials, InvestigationRequest, InvestigationResponse, TokenResponse

app = FastAPI(title="AI Kubernetes Troubleshooting Agent", version="2.0.0")

auth.validate_jwt_secret_on_startup()

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/contexts")
def contexts(user_id: int = Depends(auth.current_user_id)):
    import k8s_collector

    return {"contexts": k8s_collector.list_contexts()}


@app.post("/auth/register", response_model=TokenResponse)
def register(creds: Credentials):
    return auth.register(creds)


@app.post("/auth/login", response_model=TokenResponse)
def login(creds: Credentials):
    return auth.login(creds)


@app.post("/investigations", response_model=InvestigationResponse, status_code=202)
def start_investigation(
    req: InvestigationRequest,
    background: BackgroundTasks,
    user_id: int = Depends(auth.current_user_id),
):
    inv_id = storage.create_investigation(user_id, req.namespace, req.deployment, req.cluster_context)
    jobs.enqueue(background, inv_id, req.namespace, req.deployment, req.cluster_context)
    return storage.get_investigation(inv_id, user_id)


@app.get("/investigations", response_model=list[InvestigationResponse])
def list_investigations(user_id: int = Depends(auth.current_user_id)):
    return storage.list_investigations(user_id)


@app.get("/investigations/{inv_id}", response_model=InvestigationResponse)
def get_investigation(inv_id: int, user_id: int = Depends(auth.current_user_id)):
    inv = storage.get_investigation(inv_id, user_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv
