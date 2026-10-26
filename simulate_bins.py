
import json
import time
from urllib.request import Request, urlopen

API_URL = "http://127.0.0.1:5000/api/bin"
BINS_URL = "http://127.0.0.1:5000/api/bins"

bins = {
    "BIN002": 0.0,
    "BIN003": 0.0
}

previous_fill = bins.copy()

print("Software Smart Bin Simulator Started!")

while True:
    try:
        # Read latest values from backend
        with urlopen(BINS_URL, timeout=5) as response:
            server_bins = json.loads(response.read().decode())

        for item in server_bins:
            bin_id = item["bin_id"]

            if bin_id in bins:
                server_fill = float(item["fill"])

                # Detect collection reset
                if server_fill == 0 and previous_fill[bin_id] > 0:
                    bins[bin_id] = 0.0
                    print(f"{bin_id} collected. Reset to 0%")

    except Exception as error:
        print("Error reading backend:", error)

    # Send current readings
    for bin_id in bins:
        fill = bins[bin_id]

        data = {
            "bin_id": bin_id,
            "fill": round(fill, 1)
        }

        request = Request(
            API_URL,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urlopen(request, timeout=5) as response:
                print(f"{bin_id}: {fill:.1f}% | Sent successfully")

            previous_fill[bin_id] = fill

        except Exception as error:
            print(f"Error sending {bin_id}:", error)

    # Gradual waste accumulation
    bins["BIN002"] = min(100, bins["BIN002"] + 0.5)
    bins["BIN003"] = min(100, bins["BIN003"] + 0.3)

    time.sleep(5)
