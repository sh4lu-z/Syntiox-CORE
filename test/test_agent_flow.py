import os
import sys
import time

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
sys.stdout.reconfigure(encoding="utf-8")

from backend import browser_actions as ba

# Same sequence the agent ran
t = time.time()
ba.set_agent_active(True, "flow test")
print(f"== set_agent_active done {time.time()-t:.1f}s")

t = time.time()
ba.goto("https://www.youtube.com/results?search_query=Lil+Rome+Praba")
print(f"== goto youtube done {time.time()-t:.1f}s")

# Agent clicked a video here, so tab 0 has media playing
t = time.time()
def _play(page, context):
    page.click("a#video-title", timeout=5000)
    page.wait_for_timeout(4000)
    print("playing:", page.url)
ba._execute_with_playwright(_play)
print(f"== click video done {time.time()-t:.1f}s")

t = time.time()
ba.new_tab("https://www.google.com/search?q=Rust+vs+Go")
print(f"== new_tab done {time.time()-t:.1f}s")

t = time.time()
ba.list_tabs()
print(f"== list_tabs done {time.time()-t:.1f}s")
