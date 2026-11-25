"""Uvicorn entrypoint for the opt-in NEXUS EDGE gateway.

Start explicitly with:
    uvicorn nexus_edge.server:app --host 127.0.0.1 --port 8765
The service refuses to load unless its encryption and provisioning secrets
have been provisioned in the environment.
"""
from .gateway import create_edge_app

app = create_edge_app()
