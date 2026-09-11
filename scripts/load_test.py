"""Load test: 10 concurrent screener API calls."""
import time
import concurrent.futures
import requests

URL = "http://localhost:5000/api/v1/screener?min_roe=15"

def fetch():
    start = time.perf_counter()
    r = requests.get(URL)
    return r.status_code, time.perf_counter() - start

if __name__ == "__main__":
    print("Starting load test: 10 concurrent requests to /api/v1/screener")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch) for _ in range(10)]
        results = [f.result() for f in futures]
    
    statuses = [r[0] for r in results]
    times = [r[1] for r in results]
    
    print(f"Status codes: {set(statuses)}")
    print(f"Total wall-clock time: {max(times):.3f}s")
    print(f"Average request time: {sum(times)/len(times):.3f}s")
    print(f"Max request time: {max(times):.3f}s")
    
    if all(s == 200 for s in statuses) and max(times) < 10.0:
        print("✅ PASS: All 10 requests returned 200 OK within 10 seconds.")
    else:
        print("❌ FAIL: Load test criteria not met.")