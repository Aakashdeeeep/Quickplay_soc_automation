"""
Flask entry point for the SOC Wall Controller.

Run with: python app.py
"""

from flask import Flask

from db import init_db
from routes.views import views_bp
from routes.api import api_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)
    return app


app = create_app()

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
