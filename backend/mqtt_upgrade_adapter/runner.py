import logging
import os

from backend.app import create_app
from backend.mqtt_upgrade_adapter.adapter import MqttUpgradeAdapter


def run_adapter() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    config_name = os.getenv("FLASK_CONFIG", "dev")
    app = create_app(config_name)
    with app.app_context():
        adapter = MqttUpgradeAdapter(app)
        adapter.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    run_adapter()

