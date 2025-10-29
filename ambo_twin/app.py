try:
    from ambo_twin.server import create_app
except ModuleNotFoundError:
    # Allow running as a script: python ambo_twin/app.py
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from ambo_twin.server import create_app

app = create_app()

if __name__ == "__main__":
    # Use polling transport to avoid websocket issues in some dev setups
    app.socketio.run(app)


