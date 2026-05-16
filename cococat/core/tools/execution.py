"""Execution tools — bash, browser."""
import json
import os
import subprocess

from cococat.core.types import ToolContext


def _resolve(ctx) -> ToolContext:
    return ToolContext.from_dict(ctx)


async def _bash(command: str, ctx: ToolContext) -> str:
    ctx = _resolve(ctx)
    if not command:
        return "Error: 'command' is required"

    sandbox_run = ctx.sandbox.run

    if sandbox_run:
        code = (
            "import subprocess, sys\n"
            f"r = subprocess.run({command!r}, shell=True, capture_output=True, text=True, timeout=30)\n"
            "sys.stdout.write(r.stdout)\n"
            "if r.stderr:\n"
            "    sys.stderr.write(r.stderr)\n"
        )
        try:
            return await sandbox_run(code)
        except Exception as e:
            return f"Error in sandbox bash: {e}"

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        out = result.stdout
        err = result.stderr
        if err:
            out += f"\n[stderr]\n{err}"
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out (30s)"
    except Exception as e:
        return f"Error: {e}"


async def _browser(action_str: str) -> str:
    """Execute browser actions via Playwright.

    action_str is a JSON string: {"type": "...", ...}
    Supported types: navigate, get_text, get_content, screenshot, click, type, scroll, execute_js, go_back
    """
    if not action_str:
        return "Error: 'action' is required"

    try:
        action = json.loads(action_str)
    except json.JSONDecodeError as e:
        return f"Error parsing action JSON: {e}"

    action_type = action.get("type", "")
    if not action_type:
        return "Error: action 'type' is required"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "Error: playwright not installed. Run: pip install playwright && playwright install chromium"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                if action_type == "navigate":
                    url = action.get("url", "")
                    if not url:
                        return "Error: 'url' is required for navigate action"
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    text = await page.inner_text("body")
                    title = await page.title()
                    return f"Title: {title}\n\n{text[:5000]}"

                elif action_type == "get_text":
                    text = await page.inner_text("body")
                    return text[:5000] if text else "(empty page)"

                elif action_type == "get_content":
                    selector = action.get("selector")
                    if selector:
                        try:
                            el = await page.wait_for_selector(selector, timeout=5000)
                            text = await el.inner_text()
                            return text[:5000] if text else "(empty element)"
                        except Exception:
                            html = await page.content()
                            return html[:5000]
                    html = await page.content()
                    return html[:5000]

                elif action_type == "screenshot":
                    import base64
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    screenshot_bytes = await page.screenshot(full_page=action.get("full_page", False))
                    b64 = base64.b64encode(screenshot_bytes).decode()
                    path = action.get("save_path")
                    if path:
                        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                        with open(path, "wb") as f:
                            f.write(screenshot_bytes)
                        return f"Screenshot saved to {path} ({len(screenshot_bytes)} bytes)"
                    return f"Screenshot: {len(screenshot_bytes)} bytes (base64 length: {len(b64)})"

                elif action_type == "click":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    selector = action.get("selector", "")
                    if not selector:
                        return "Error: 'selector' is required for click action (CSS selector or text=...)"
                    try:
                        await page.click(selector, timeout=10000)
                        return f"Clicked '{selector}'"
                    except Exception as e:
                        try:
                            await page.click(f"text={selector}", timeout=5000)
                            return f"Clicked text '{selector}'"
                        except Exception:
                            return f"Error clicking '{selector}': {e}"

                elif action_type == "type":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    selector = action.get("selector", "")
                    text = action.get("text", "")
                    if not selector:
                        return "Error: 'selector' is required for type action"
                    await page.fill(selector, text, timeout=10000)
                    return f"Typed into '{selector}'"

                elif action_type == "scroll":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    direction = action.get("direction", "down")
                    amount = action.get("amount", 300)
                    if direction == "down":
                        await page.evaluate(f"window.scrollBy(0, {amount})")
                    elif direction == "up":
                        await page.evaluate(f"window.scrollBy(0, -{amount})")
                    else:
                        return f"Error: unknown scroll direction '{direction}'. Use 'up' or 'down'"
                    return f"Scrolled {direction} by {amount}px"

                elif action_type == "execute_js":
                    url = action.get("url")
                    if url:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    code = action.get("code", "")
                    if not code:
                        return "Error: 'code' is required for execute_js action"
                    result = await page.evaluate(code)
                    return str(result) if result is not None else "(no return value)"

                elif action_type == "go_back":
                    await page.go_back()
                    text = await page.inner_text("body")
                    title = await page.title()
                    return f"[Back] Title: {title}\n\n{text[:5000]}"

                else:
                    return "Error: unknown action type '{action_type}'. Supported: navigate, get_text, get_content, screenshot, click, type, scroll, execute_js, go_back"

            finally:
                await browser.close()
    except Exception as e:
        return f"Error in browser {action_type}: {e}"
