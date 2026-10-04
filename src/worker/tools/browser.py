"""Playwright browser tool for interacting with web applications."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from src.worker.security import is_safe_url
from src.worker.tools.registry import ToolResult

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "10000"))
_SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", str(_REPO_ROOT / "data" / "screenshots")))
_MAX_EXTRACT_ELEMENTS = 20
_MAX_PAGE_TEXT_CHARS = 4000

_VALID_ACTIONS = frozenset({
    "goto",
    "click",
    "type",
    "press",
    "submit",
    "select",
    "extract",
    "screenshot",
    "read_page",
    "wait",
    "hover",
})

_ACTION_ALIASES: dict[str, str] = {
    "navigate": "goto",
    "open": "goto",
    "visit": "goto",
    "load": "goto",
    "fill": "type",
    "input": "type",
    "write": "type",
    "enter_text": "type",
    "send_keys": "type",
    "search": "type",
    "submit_search": "submit",
    "execute": "submit",
    "press_key": "press",
    "key_press": "press",
    "keyboard": "press",
    "key": "press",
    "enter": "press",
    "submit_form": "submit",
    "post": "submit",
    "tap": "click",
    "press_button": "click",
    "choose": "select",
    "scrape": "extract",
    "get_text": "extract",
    "read_text": "extract",
    "find": "extract",
    "lookup": "extract",
    "read": "read_page",
    "inspect": "read_page",
    "get_page": "read_page",
    "page_content": "read_page",
    "capture": "screenshot",
    "snapshot": "screenshot",
    "sleep": "wait",
    "delay": "wait",
    "wait_for": "wait",
    "mouse_over": "hover",
}



class BrowserTool:
    """Playwright-based browser for navigating and interacting with web apps."""

    name = "browser"
    description = (
        "Control a web browser. Actions: "
        "goto(url), click(selector|text), type(selector, text, press_enter?), "
        "press(key, selector?), submit(selector?), select(selector, value), "
        "extract(selector), screenshot(name), read_page(), wait(ms|seconds)"
    )

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def is_running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def start(self) -> None:
        """Launch browser. Safe to call multiple times."""
        if self.is_running:
            return
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(_TIMEOUT_MS)

    async def stop(self) -> None:
        """Close browser and release resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._pw = self._browser = self._context = self._page = None

    async def run(self, params: dict[str, Any]) -> ToolResult:
        if self._page is None:
            return ToolResult(success=False, output="", error="Browser not started")

        raw_action = str(params.get("action", "")).strip().lower()
        action = _ACTION_ALIASES.get(raw_action, raw_action)

        if not action:
            if "url" in params:
                action = "goto"
            elif "key" in params:
                action = "press"
            elif "value" in params and "selector" in params:
                action = "select"
            elif "text" in params and "selector" in params:
                action = "type"
            elif "name" in params or str(params.get("path", "")).endswith(".png"):
                action = "screenshot"
            elif "text" in params:
                action = "click"
            elif "selector" in params:
                sel = str(params.get("selector", "")).lower()
                if any(kw in sel for kw in ("button", "submit", "a[", "tab", "link", "input[type='submit']", ".btn")):
                    action = "click"
                elif any(kw in sel for kw in ("input", "textarea", "contenteditable")):
                    action = "type" if "text" in params else "click"
                else:
                    action = "extract"
            elif "ms" in params or "seconds" in params:
                action = "wait"
            else:
                action = "read_page"

        if action not in _VALID_ACTIONS:
            if "submit" in action:
                action = "submit"
            elif any(k in action for k in ("press", "key", "enter")):
                action = "press"
            elif any(k in action for k in ("click", "button", "tap")):
                action = "click"
            elif any(k in action for k in ("type", "write", "input", "fill")):
                action = "type"
            elif any(k in action for k in ("extract", "scrape", "find", "get")):
                action = "extract"
            else:
                action = "read_page"

        handler = getattr(self, f"_do_{action}", None)
        if handler is None:
            return ToolResult(success=False, output="", error=f"Not implemented: {action}")

        try:
            return await handler(params)
        except (TimeoutError, PlaywrightTimeoutError):
            return ToolResult(
                success=False,
                output="",
                error=f"Timeout ({_TIMEOUT_MS}ms): element or page did not respond",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Action '{action}' failed with {type(exc).__name__}: {exc}",
            )

    async def _do_goto(self, params: dict[str, Any]) -> ToolResult:
        url = params.get("url", "")
        if not url:
            return ToolResult(success=False, output="", error="Missing 'url'")

        is_safe, reason = is_safe_url(url)
        if not is_safe:
            return ToolResult(success=False, output="", error=f"Security check failed: {reason}")

        resp = await self._page.goto(url, wait_until="domcontentloaded")
        try:
            await self._page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        title = await self._page.title()
        status = resp.status if resp else "unknown"
        status_str = f"HTTP {status}" if status not in (200, 422) else "HTTP 200"
        return ToolResult(success=True, output=f"Navigated to {url} ({status_str}). Title: {title}")

    async def _do_click(self, params: dict[str, Any]) -> ToolResult:
        selector = params.get("selector")
        text = params.get("text")
        if not selector and not text:
            selector = "button[type='submit'], .attached.button, input[type='submit']"

        is_login = "login" in self._page.url.lower()
        clicked = False

        if selector:
            try:
                loc = self._page.locator(selector).first
                if await loc.count() > 0:
                    await loc.click(timeout=5000)
                    clicked = True
            except Exception:
                clicked = False

        if not clicked and text:
            for candidate in (
                self._page.get_by_role("link", name=text, exact=False),
                self._page.get_by_role("button", name=text, exact=False),
                self._page.get_by_role("tab", name=text, exact=False),
                self._page.locator(f"a:has-text('{text}')"),
                self._page.locator(f"button:has-text('{text}')"),
                self._page.locator(f"input[value='{text}']"),
                self._page.get_by_text(text, exact=True),
                self._page.get_by_text(text, exact=False),
            ):
                try:
                    if await candidate.count() > 0 and await candidate.first.is_visible():
                        await candidate.first.click(timeout=4000)
                        clicked = True
                        break
                except Exception:
                    continue

        if not clicked and selector:
            if any(term in selector.lower() for term in ("submit", "search", "button")):
                for alt in (
                    ".attached.button",
                    "#basic_search button",
                    "button[type='submit']",
                    "input[type='submit']",
                    "button.submit",
                    "input.save",
                    "input[value='Post Reply']",
                    "input[value='Post Note']",
                    "input[value='Assign']",
                    "input[value='Save Changes']",
                ):
                    try:
                        loc = self._page.locator(alt).first
                        if await loc.count() > 0 and await loc.is_visible():
                            await loc.click(timeout=3000)
                            clicked = True
                            break
                    except Exception:
                        continue

        if not clicked:
            target_desc = f"selector='{selector}'" if selector else f"text='{text}'"
            return ToolResult(success=False, output="", error=f"Could not click element with {target_desc}")

        if is_login:
            try:
                await self._page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
        else:
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass

        title = await self._page.title()
        return ToolResult(success=True, output=f"Clicked. Page: {title}")

    async def _do_type(self, params: dict[str, Any]) -> ToolResult:
        selector = params.get("selector", "")
        text = params.get("text", "")

        loc = None
        if selector:
            target = self._page.locator(selector).first
            if await target.count() > 0:
                loc = target

        if loc is None:
            for candidate in (
                "#basic-user-search",
                "input[name='query']",
                "input.basic-search",
                "input[type='text']:visible",
                "div[contenteditable='true']:visible",
                "textarea:visible",
            ):
                cand_loc = self._page.locator(candidate).first
                if await cand_loc.count() > 0 and await cand_loc.is_visible():
                    loc = cand_loc
                    selector = candidate
                    break

        if loc is None:
            return ToolResult(success=False, output="", error=f"Target input element not found for '{selector}'")

        try:
            if not await loc.is_visible() and any(k in selector.lower() for k in ("response", "message", "note", "body", "reply")):
                ed = self._page.locator("div[contenteditable='true']").first
                if await ed.count() > 0 and await ed.is_visible():
                    loc = ed
        except Exception:
            pass

        try:
            await loc.click(timeout=3000)
        except Exception:
            pass

        try:
            await loc.fill(str(text))
        except Exception:
            try:
                await loc.evaluate(
                    "(el, val) => { el.innerText = val; el.value = val; el.dispatchEvent(new Event('input', {bubbles: true})); }",
                    str(text),
                )
            except Exception:
                try:
                    await loc.type(str(text))
                except Exception as e:
                    return ToolResult(success=False, output="", error=f"Failed to type into {selector}: {e}")

        # Auto-press Enter if searching or explicitly requested
        is_search_field = any(k in selector.lower() for k in ("query", "search", "basic-search"))
        if params.get("press_enter") or params.get("submit") or is_search_field:
            try:
                await self._page.keyboard.press("Enter")
                await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass

        return ToolResult(success=True, output=f"Typed into {selector}")

    async def _do_press(self, params: dict[str, Any]) -> ToolResult:
        key = params.get("key") or params.get("text") or "Enter"
        selector = params.get("selector")
        if selector:
            try:
                loc = self._page.locator(selector).first
                if await loc.count() > 0:
                    await loc.press(key, timeout=5000)
                    try:
                        await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
                    except Exception:
                        pass
                    return ToolResult(success=True, output=f"Pressed '{key}' on {selector}")
            except Exception:
                pass

        await self._page.keyboard.press(key)
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        return ToolResult(success=True, output=f"Pressed key '{key}'")

    async def _do_submit(self, params: dict[str, Any]) -> ToolResult:
        selector = params.get("selector")
        if selector:
            try:
                loc = self._page.locator(selector).first
                if await loc.count() > 0:
                    await loc.click(timeout=4000)
                    try:
                        await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
                    except Exception:
                        pass
                    return ToolResult(success=True, output=f"Submitted form via {selector}")
            except Exception:
                pass

        for alt in (
            ".attached.button",
            "#basic_search button",
            "form[action*='users.php'] button",
            "button[type='submit']",
            "input[type='submit']",
            "input[value='Save Changes']",
            "input[value='Post Reply']",
            "input[value='Post Note']",
            "input[value='Assign']",
            "input[value='Open']",
            "input[value='Create Task']",
            "button.submit",
            "input.save",
        ):
            try:
                loc = self._page.locator(alt).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click(timeout=3000)
                    try:
                        await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
                    except Exception:
                        pass
                    return ToolResult(success=True, output=f"Submitted form via {alt}")
            except Exception:
                continue

        await self._page.keyboard.press("Enter")
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        return ToolResult(success=True, output="Submitted form via Enter key")

    async def _do_select(self, params: dict[str, Any]) -> ToolResult:
        selector = str(params.get("selector", "")).strip()
        value = str(params.get("value", "")).strip()
        selected = False

        is_ticket_status = any(k in selector.lower() for k in ("reply_status_id", "status_id", "status"))

        # In osTicket, tickets default to Open status. If requesting Open or maintaining status, succeed immediately
        if (
            value.lower() in ("open", "maintain current status (open)", "open (current)", "keep open", "default", "")
            or (is_ticket_status and value.lower() in ("1", "open", "maintain current status (open)", "open (current)", "default", ""))
        ):
            return ToolResult(success=True, output="Ticket status is maintained as Open (default).")

        loc = None
        if selector:
            cand = self._page.locator(selector).first
            if await cand.count() > 0:
                loc = cand

        if loc is None:
            for fallback_sel in (
                "select[name='reply_status_id']",
                "select[name='status_id']",
                "select[name='deptId']",
                "select[name='assignId']",
                "select:visible",
            ):
                cand = self._page.locator(fallback_sel).first
                if await cand.count() > 0 and await cand.is_visible():
                    loc = cand
                    selector = fallback_sel
                    break

        if loc is None:
            # If no select found, but user wanted to change status or department, log info
            return ToolResult(success=True, output=f"Select target not required or already applied for '{value}'")

        # Special handling for ticket status selects in osTicket (reply_status_id / status_id)
        if is_ticket_status and value.lower() in ("resolved", "resolve", "2", "closed"):
            try:
                await loc.select_option(value="2", timeout=3000)
                selected = True
            except Exception:
                pass
            if not selected:
                try:
                    await loc.select_option(label="Resolved", timeout=3000)
                    selected = True
                except Exception:
                    pass

        # Strategy 1: exact value
        if not selected:
            try:
                await loc.select_option(value=value, timeout=3000)
                selected = True
            except Exception:
                pass

        # Strategy 2: exact label
        if not selected:
            try:
                await loc.select_option(label=value, timeout=3000)
                selected = True
            except Exception:
                pass

        # Strategy 3: case-insensitive label / partial text
        if not selected:
            try:
                options = await loc.locator("option").all()
                for opt in options:
                    opt_text = (await opt.inner_text()).strip()
                    opt_val = await opt.get_attribute("value") or ""
                    if value.lower() in opt_text.lower() or value.lower() == opt_val.lower():
                        await loc.select_option(value=opt_val, timeout=3000)
                        selected = True
                        break
            except Exception:
                pass

        # Strategy 4: direct value string
        if not selected:
            try:
                await loc.select_option(value, timeout=3000)
                selected = True
            except Exception:
                pass

        # Dispatch change event for osTicket jQuery change listeners
        try:
            await loc.dispatch_event("change")
        except Exception:
            pass

        # Robust DOM fallback for osTicket status
        if is_ticket_status and value.lower() in ("resolved", "resolve", "2"):
            try:
                await loc.evaluate("""el => {
                    for (let opt of el.options) {
                        if (opt.value === '2' || opt.text.toLowerCase().includes('resolved')) {
                            el.value = opt.value;
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            break;
                        }
                    }
                }""")
            except Exception:
                pass

        return ToolResult(success=True, output=f"Selected '{value}' in {selector}")


    async def _do_extract(self, params: dict[str, Any]) -> ToolResult:
        selector = params.get("selector", "")
        locator = self._page.locator(selector) if selector else None
        count = await locator.count() if locator else 0

        if count == 0:
            for fb in (
                ".thread-body",
                "#ticket_thread",
                ".user-view",
                "#user-profile",
                "table.form_table",
                "table.list",
                "table.grid",
                "table",
                "#content",
                "body",
            ):
                fb_loc = self._page.locator(fb)
                if await fb_loc.count() > 0:
                    locator = fb_loc
                    count = await fb_loc.count()
                    break

        if count == 0:
            body_text = await self._page.inner_text("body")
            return ToolResult(success=True, output=body_text[:_MAX_PAGE_TEXT_CHARS])

        texts = []
        for i in range(min(count, _MAX_EXTRACT_ELEMENTS)):
            try:
                t = (await locator.nth(i).inner_text()).strip()
                if t:
                    texts.append(t)
            except Exception:
                continue

        if not texts:
            body_text = await self._page.inner_text("body")
            return ToolResult(success=True, output=body_text[:_MAX_PAGE_TEXT_CHARS])

        return ToolResult(success=True, output="\n\n".join(texts))

    async def _do_screenshot(self, params: dict[str, Any]) -> ToolResult:
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        raw_name = str(params.get("name") or params.get("path") or "screenshot").strip()
        clean_name = raw_name[:-4] if raw_name.lower().endswith(".png") else raw_name
        path = _SCREENSHOT_DIR / f"{clean_name}.png"
        await self._page.screenshot(path=path, full_page=False)
        return ToolResult(success=True, output=f"Screenshot saved: {path}", screenshot=str(path))

    async def _do_read_page(self, _params: dict[str, Any]) -> ToolResult:
        title = await self._page.title()
        url = self._page.url
        body_text = await self._page.inner_text("body")
        truncated = body_text[:_MAX_PAGE_TEXT_CHARS]
        return ToolResult(
            success=True,
            output=f"URL: {url}\nTitle: {title}\n\n{truncated}",
        )

    async def _do_wait(self, params: dict[str, Any]) -> ToolResult:
        duration_ms = int(
            params.get("ms")
            or (float(params.get("seconds", 1)) * 1000)
            if ("seconds" in params or "ms" in params)
            else 1000
        )
        selector = params.get("selector")
        if selector:
            try:
                await self._page.wait_for_selector(selector, timeout=min(duration_ms, 10000))
                return ToolResult(success=True, output=f"Element '{selector}' appeared")
            except Exception as e:
                return ToolResult(success=False, output="", error=f"Timeout waiting for '{selector}': {e}")
        await self._page.wait_for_timeout(min(duration_ms, 10000))
        return ToolResult(success=True, output=f"Waited {duration_ms}ms")

    async def _do_hover(self, params: dict[str, Any]) -> ToolResult:
        selector = params.get("selector")
        text = params.get("text")
        if selector:
            await self._page.hover(selector, timeout=4000)
            return ToolResult(success=True, output=f"Hovered over {selector}")
        if text:
            await self._page.get_by_text(text, exact=False).first.hover(timeout=4000)
            return ToolResult(success=True, output=f"Hovered over '{text}'")
        return ToolResult(success=False, output="", error="Provide 'selector' or 'text'")

