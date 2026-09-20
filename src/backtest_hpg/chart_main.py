"""Run the VN30F1M market chart without initializing a legacy database."""

from .api.app import create_app

app = create_app()
