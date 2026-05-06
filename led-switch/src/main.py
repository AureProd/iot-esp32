# main.py
from services.controller import LEDController

if __name__ == "__main__":
    app = LEDController()
    app.run()
