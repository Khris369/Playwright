from __future__ import annotations

from typing import Any, Awaitable, Callable

from playwright.async_api import BrowserContext, CDPSession, Page


INJECTED_INSPECTOR_SCRIPT = r"""
(() => {
  if (window.__workflowPickerInspector) return;
  const state = { active: false, hovered: null, previousOutline: '' };
const metadata = (element) => {
    const attributes = {};
    for (const attr of element.attributes || []) {
      if (!/^(value|password|token|secret|cookie|authorization)$/i.test(attr.name)) {
        attributes[attr.name] = String(attr.value).slice(0, 160);
      }
    }
    const implicit = { BUTTON: 'button', A: 'link', SELECT: 'combobox', TEXTAREA: 'textbox' };
    let role = element.getAttribute('role') || implicit[element.tagName] || null;
    if (element.tagName === 'INPUT') role = element.type === 'checkbox' ? 'checkbox' : element.type === 'radio' ? 'radio' : 'textbox';
    const xpathLiteral = (value) => value.includes('"') && value.includes("'")
      ? `concat('${value.replaceAll("'", "',\"'\",")}')`
      : value.includes("'") ? `"${value}"` : `'${value}'`;
    const fullXpath = (node) => {
      const parts = [];
      for (let current = node; current && current.nodeType === Node.ELEMENT_NODE; current = current.parentElement) {
        let index = 1;
        for (let sibling = current.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
          if (sibling.tagName === current.tagName) index += 1;
        }
        parts.unshift(`${current.tagName.toLowerCase()}[${index}]`);
      }
      return `/${parts.join('/')}`;
    };
    const xpath = element.id
      ? `//*[@id=${xpathLiteral(element.id)}]`
      : `//${element.tagName.toLowerCase()}${element.getAttribute('data-testid') ? `[@data-testid=${xpathLiteral(element.getAttribute('data-testid'))}]` : ''}`;
    return { tag_name: element.tagName.toLowerCase(), attributes, text: (element.innerText || '').slice(0, 160), role, name: (element.getAttribute('aria-label') || element.getAttribute('title') || element.innerText || '').slice(0, 160), label: null, xpath, full_xpath: fullXpath(element) };
  };
  const clear = () => { if (state.hovered) state.hovered.style.outline = state.previousOutline; state.hovered = null; };
  const hover = (event) => { if (!state.active || !(event.target instanceof Element)) return; clear(); state.hovered = event.target; state.previousOutline = state.hovered.style.outline; state.hovered.style.outline = '3px solid #2864dc'; };
  const click = (event) => { if (!state.active || !(event.target instanceof Element)) return; event.preventDefault(); event.stopImmediatePropagation(); const selected = event.target; clear(); state.active = false; window.__picker_select(metadata(selected)); };
  document.addEventListener('pointerover', hover, true); document.addEventListener('click', click, true);
  window.__workflowPickerInspector = { start: () => { state.active = true; }, stop: () => { state.active = false; clear(); }, toggle: () => { state.active ? window.__workflowPickerInspector.stop() : window.__workflowPickerInspector.start(); } };
})();
"""


class CdpInspector:
    """CDP Overlay wrapper; a future injected fallback can implement this interface."""
    def __init__(self, page: Page, on_select: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self.page = page
        self.on_select = on_select
        self.cdp: CDPSession | None = None
        self.highlight_config = {
            "showInfo": True,
            "showAccessibilityInfo": True,
            "contentColor": {"r": 80, "g": 140, "b": 230, "a": 0.25},
            "borderColor": {"r": 40, "g": 100, "b": 220, "a": 1},
        }

    async def start(self) -> None:
        self.cdp = await self.page.context.new_cdp_session(self.page)
        await self.cdp.send("DOM.enable")
        await self.cdp.send("Overlay.enable")
        frame_tree = await self.cdp.send("Page.getFrameTree")
        self.main_frame_id = frame_tree.get("frameTree", {}).get("frame", {}).get("id")
        self.cdp.on("Overlay.inspectNodeRequested", self._selected)
        await self.cdp.send("Overlay.setInspectMode", {"mode": "searchForNode", "highlightConfig": self.highlight_config})

    async def stop(self) -> None:
        if self.cdp:
            try:
                await self.cdp.send("Overlay.setInspectMode", {"mode": "none", "highlightConfig": self.highlight_config})
            except Exception:
                # The page may have navigated or closed between selection and
                # cleanup. Browser/session teardown remains responsible for the
                # final resource cleanup.
                pass

    async def _selected(self, event: dict[str, Any]) -> None:
        if not self.cdp:
            return
        backend_node_id = event.get("backendNodeId")
        if not backend_node_id:
            return
        node = (await self.cdp.send("DOM.describeNode", {"backendNodeId": backend_node_id, "depth": 0})).get("node", {})
        node["picker_frame_id"] = event.get("frameId")
        node["picker_main_frame_id"] = getattr(self, "main_frame_id", None)
        resolved = await self.cdp.send("DOM.resolveNode", {"backendNodeId": backend_node_id})
        object_id = resolved.get("object", {}).get("objectId")
        if object_id:
            # This fixed, agent-owned function only reads minimal element metadata;
            # no server-provided JavaScript is evaluated.
            result = await self.cdp.send("Runtime.callFunctionOn", {
                "objectId": object_id,
                "returnByValue": True,
                "functionDeclaration": "function () { const e=this; const a={}; for (const x of e.attributes) a[x.name]=x.value; const implicit={BUTTON:'button',A:'link',INPUT:(e.type==='checkbox'?'checkbox':e.type==='radio'?'radio':'textbox'),SELECT:'combobox',TEXTAREA:'textbox'}; const lit=v=>v.includes('\\\"')&&v.includes(\"'\")?`concat('${v.replaceAll(\"'\",\"',\\\"'\\\",\") }')`:v.includes(\"'\")?`\\\"${v}\\\"`:`'${v}'`; const full=n=>{const p=[];for(let c=n;c&&c.nodeType===1;c=c.parentElement){let i=1;for(let s=c.previousElementSibling;s;s=s.previousElementSibling)if(s.tagName===c.tagName)i++;p.unshift(`${c.tagName.toLowerCase()}[${i}]`)}return '/'+p.join('/')}; const xpath=e.id?`//*[@id=${lit(e.id)}]`:`//${e.tagName.toLowerCase()}${e.getAttribute('data-testid')?`[@data-testid=${lit(e.getAttribute('data-testid'))}]`:''}`; return {tag_name:e.tagName.toLowerCase(), attributes:a, text:(e.innerText||'').slice(0,160), role:e.getAttribute('role')||implicit[e.tagName]||null, name:e.getAttribute('aria-label')||e.getAttribute('title')||e.innerText||'', label:null, xpath, full_xpath:full(e)}; }",
            })
            metadata = result.get("result", {}).get("value")
            if isinstance(metadata, dict):
                node["picker_metadata"] = metadata
        await self.on_select(node)


class InjectedInspector:
    """Fixed local fallback for Chromium builds without Overlay support."""

    def __init__(self, context: BrowserContext, page: Page, on_select: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self.context, self.page, self.on_select = context, page, on_select
        self._binding_ready = False

    async def prepare(self) -> None:
        if not self._binding_ready:
            await self.context.expose_binding("__picker_select", self._binding_selected)
            await self.context.add_init_script(INJECTED_INSPECTOR_SCRIPT)
            self._binding_ready = True
        await self.page.evaluate(INJECTED_INSPECTOR_SCRIPT)

    async def start(self) -> None:
        await self.prepare()
        await self.page.evaluate("window.__workflowPickerInspector && window.__workflowPickerInspector.start()")

    async def stop(self) -> None:
        try:
            await self.page.evaluate("window.__workflowPickerInspector && window.__workflowPickerInspector.stop()")
        except Exception:
            pass

    async def _binding_selected(self, _source: Any, metadata: dict[str, Any]) -> None:
        await self.on_select(metadata)

    async def rebind(self, page: Page) -> None:
        self.page = page
        await self.prepare()
