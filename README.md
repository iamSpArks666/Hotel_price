This is a script to catch the prices of a hotel in a range of days on BOOKING and AGODA.

# Hotel_preice

## Setup

This project uses Playwright for browser automation to compare Booking and Agoda prices.
You do not need `conda` to run it.

### 1) Install dependencies

```bash
python -m pip install -r requirements.txt
python -m playwright install
```

### 2) Run the script

```bash
python compare_prices.py
```

If you are on Windows and your Python executable is at a specific path, you can run:

```powershell
& C:/Users/YourName/anaconda3/python.exe compare_prices.py
```
