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

### Windows PowerShell notes

If you see a message about `profile.ps1` being blocked (execution policy), that is a
PowerShell security setting. You can either ignore it (it does not prevent Python
from running), or allow PowerShell to load your user profile by running:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

If `conda activate` fails with "conda is not recognized", it means `conda` is not in
your PATH for this shell. You can either use the full path to `conda.exe`:

```powershell
& C:/Users/YourName/anaconda3/Scripts/conda.exe activate base
```

Or skip conda entirely and use the Python executable directly, as shown above.
