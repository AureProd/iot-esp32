# main.py
from services.controller import CoffeeController

if __name__ == "__main__":
    app = CoffeeController()
    app.run()
