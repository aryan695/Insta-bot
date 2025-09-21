# 9_fast_xnsera.py  (fasted modified version)
# Password: xnsera

import sys
import os
import asyncio
import logging
import random
from itertools import count
from cfonts import render
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# -------- CONFIG (tune these) --------
PASSWORD = "xnsera"
HEADLESS = True           # True = fastest; False = visible browser for debug
DEFAULT_TASKS = 20        # concurrency (reduce if you get rate limited)
RENAME_DELAY = 0.01       # seconds between renames per loop (0 or very small for fastest)
STATS_INTERVAL = 0.5      # how often stats print
GEAR_WAIT = 8000          # ms wait for info button

# -------- UI/colors --------
COLORS = {
    'green': '\033[1;32m', 'red': '\033[1;31m', 'cyan': '\033[36m', 'reset': '\033[0m'
}

def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(render("• ANANYA FAST •", colors=["yellow","blue"]))
    print("Ultra-fast Instagram Group Renamer (use responsibly)")

# -------- Logging ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# -------- Input & Auth ----------
banner()
pw = input("Enter script password: ").strip()
if pw != PASSWORD:
    print("❌ Wrong password. Exiting.")
    sys.exit(1)

session_id = input("Session ID (cookie): ").strip()
if not session_id:
    print("Session ID required. Exiting.")
    sys.exit(1)

dm_url = input("Group chat URL: ").strip()
if not dm_url:
    print("DM URL required. Exiting.")
    sys.exit(1)

user_prefix = input("Prefix/name (default: XNS): ").strip() or "XNS"
try:
    task_count = int(input(f"Number of tasks [{DEFAULT_TASKS}]: ").strip() or DEFAULT_TASKS)
except:
    task_count = DEFAULT_TASKS

# -------- Name generator resources ----------
try:
    with open("ufo_bases.txt","r",encoding="utf-8") as f:
        ufo_bases = [ln.strip() for ln in f if ln.strip()]
except Exception:
    ufo_bases = ["〈ʜ∆ᴄʟᴇ〉","⚡","🔥","👑","🚀","👽","🦋","✨"]

emoji_suffixes = ["❤","💚","💙","💜","🔥","✨","💀"]
counter = count(1)
used = set()

def gen_name():
    while True:
        base = random.choice(ufo_bases)
        emo = random.choice(emoji_suffixes)
        n = f"{user_prefix}{base}{emo}{next(counter)}"
        if n not in used:
            used.add(n)
            return n

# -------- Shared counters ----------
success = 0
failed = 0
lock = asyncio.Lock()

# -------- Helper: fast find gear (minimal overhead) --------
async def click_info_button(page):
    """
    Fast attempt to click the thread info/details button.
    Prioritizes the selector we observed: div[role=button] with svg[aria-label*='Thread details']
    Returns True if clicked, False otherwise.
    """
    # primary selector (fast)
    try:
        gear = page.locator('div[role="button"]:has(svg[aria-label*="Thread details"])')
        await gear.wait_for(timeout=GEAR_WAIT)
        await gear.click()
        return True
    except Exception:
        # lightweight fallback: try a few common svg aria-label variants quickly
        fallbacks = [
            'div[role="button"]:has(svg[aria-label*="detail"])',
            'div[role="button"]:has(svg[aria-label*="Details"])',
            'button:has(svg[aria-label*="Details"])',
            'svg[aria-label*="details"]',
            'svg[aria-label*="Conversation"]'
        ]
        for sel in fallbacks:
            try:
                loc = page.locator(sel)
                if await loc.count():
                    await loc.first.click()
                    return True
            except Exception:
                continue
    return False

# -------- Core fast rename loop (caches locators) --------
async def rename_loop(context, lid):
    global success, failed
    page = await context.new_page()
    try:
        await page.goto(dm_url, wait_until="domcontentloaded", timeout=60000)
    except PWTimeout:
        logging.error(f"[L{lid}] DM load timeout")
        await page.close()
        return
    except Exception as e:
        logging.error(f"[L{lid}] DM nav error: {e}")
        await page.close()
        return

    # click info/details (fast)
    ok = await click_info_button(page)
    if not ok:
        logging.error(f"[L{lid}] Info button not found; aborting loop")
        await page.close()
        return

    # cache locators (do not recreate each loop)
    change_btn = page.locator('div[aria-label="Change group name"][role="button"], button:has-text("Change group name")')
    group_input = page.locator('input[aria-label="Group name"], input[name="change-group-name"], textarea, div[role="textbox"]')
    save_btn = page.locator('button:has-text("Save"), div[role="button"]:has-text("Save"), button:has-text("Done")')

    # quick stabilization
    await asyncio.sleep(0.15)

    while True:
        try:
            nm = gen_name()
            # click change
            await change_btn.click()
            # fill name fast
            await group_input.click(click_count=3)
            await group_input.fill(nm)
            # check disabled
            try:
                dis = await save_btn.get_attribute("aria-disabled")
            except Exception:
                dis = None
            if dis == "true":
                async with lock:
                    failed += 1
                # tiny backoff
                await asyncio.sleep(max(0.005, RENAME_DELAY))
                continue
            await save_btn.click()
            async with lock:
                success += 1
            # minimal delay
            if RENAME_DELAY:
                await asyncio.sleep(RENAME_DELAY)
        except Exception:
            async with lock:
                failed += 1
            # tiny backoff on errors
            await asyncio.sleep(0.01)

# -------- lightweight stats --------
async def stats_task():
    while True:
        async with lock:
            tot = success + failed
            print(f"\r{COLORS['cyan']}Attempts:{tot} {COLORS['green']}✔{success} {COLORS['red']}✘{failed}{COLORS['reset']}", end="", flush=True)
        await asyncio.sleep(STATS_INTERVAL)

# -------- Main ----------
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, args=["--no-sandbox","--disable-gpu"])
        context = await browser.new_context(locale="en-US")
        # add session cookie
        await context.add_cookies([{
            "name":"sessionid","value":session_id,"domain":".instagram.com","path":"/",
            "httpOnly": True, "secure": True, "sameSite": "None"
        }])

        # spawn workers
        workers = [asyncio.create_task(rename_loop(context, i+1)) for i in range(task_count)]
        workers.append(asyncio.create_task(stats_task()))

        try:
            await asyncio.gather(*workers)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
        finally:
            await context.close()
            await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Fatal:", e)
