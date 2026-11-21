"""v1.9.2 U1: the Hipersign phone apps as installable web apps.

Each app (/cn-site, /cn-worker, /driver, /cn-client, /cn-partner) links its own web-app manifest and registers a small
service worker scoped to its own path, so the phone offers "Install" / "Add to Home Screen": the app then opens full screen
from its own icon, without the browser bar. Served by a page renderer (hooks.page_renderer):
  /hs-app-sw.js                 the service worker (one script, registered per app with the app's own scope)
  /hs-app/<key>.webmanifest     the manifest of one app
The worker only caches the app page itself for offline start; API calls always go to the network."""

import json

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

APPS = {
	"site": {"name": "Hipersign Site", "short": "Site", "start": "/cn-site", "color": "#13235b",
		"desc": "Site engineer app: check-in, gang check-in, DPR, photos, site cash, deliveries and site chat."},
	"worker": {"name": "Hipersign Worker", "short": "Worker", "start": "/cn-worker", "color": "#0f5132",
		"desc": "Worker app: attendance, pay slip, advances and danger reports in your own language."},
	"driver": {"name": "Hipersign Driver", "short": "Driver", "start": "/driver", "color": "#7c2d12",
		"desc": "Driver app: today's stops, item check, signature, photo, GPS and site deliveries with OTP."},
	"client": {"name": "Hipersign Client", "short": "Client", "start": "/cn-client", "color": "#1e3a8a",
		"desc": "Client app: progress, photos, RA bills, documents, variations, snags and messages."},
	"partner": {"name": "Hipersign Partner", "short": "Partner", "start": "/cn-partner", "color": "#4c1d95",
		"desc": "Subcontractor app: work orders, running bills, payments, labour documents, photos and messages."},
}

SW = r"""/* Hipersign apps — service worker (v1.9.2). Network first for the app page, cached copy when offline. */
const CACHE = "hs-app-v192";
self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
	const r = e.request;
	if (r.method !== "GET" || r.mode !== "navigate") return; // API calls, images and scripts go straight to the network
	e.respondWith(fetch(r).then((res) => { if (res && res.ok) { const c = res.clone(); caches.open(CACHE).then((k) => k.put(r, c)); } return res; })
		.catch(() => caches.match(r).then((m) => m || new Response("<!doctype html><meta name=viewport content='width=device-width'><body style='font-family:system-ui;padding:40px;text-align:center;color:#334155'><h3>You are offline</h3><p>Connect to the internet and try again.</p>", { headers: { "Content-Type": "text/html" } }))));
});
"""


def manifest(key):
	a = APPS[key]
	icon = f"/assets/hipersign_trading/images/apps/{key}"
	return {
		"id": a["start"], "name": a["name"], "short_name": a["short"], "description": a["desc"], "start_url": a["start"], "scope": a["start"],
		"display": "standalone", "orientation": "portrait", "background_color": "#f5f7fb", "theme_color": a["color"], "lang": "en-IN",
		"icons": [{"src": f"{icon}-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
			{"src": f"{icon}-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
			{"src": f"{icon}-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
	}


class AppAssets(BaseRenderer):
	def can_render(self):
		p = self.path
		return p == "hs-app-sw.js" or (p.startswith("hs-app/") and p.endswith(".webmanifest") and p[7:-12] in APPS)

	def render(self):
		if self.path == "hs-app-sw.js":
			return self.build_response(SW, headers={"Content-Type": "application/javascript; charset=utf-8", "Service-Worker-Allowed": "/",
				"Cache-Control": "no-cache"})
		key = self.path[7:-12]
		return self.build_response(json.dumps(manifest(key)), headers={"Content-Type": "application/manifest+json", "Cache-Control": "public, max-age=3600"})


def context(context, key):
	"""Set what the shell needs on a www page's context."""
	a = APPS[key]
	context.no_header = 1
	context.no_breadcrumbs = 1
	context.hs_app = key
	context.hs_app_name = a["name"]
	context.hs_app_color = a["color"]
	return context


@frappe.whitelist()
def install_links():
	"""Desk → Site & Worker App → Apps: each app's address, QR code (SVG) and what it does."""
	import io

	import pyqrcode

	base = frappe.utils.get_url()
	out = []
	for k, a in APPS.items():
		url = base + a["start"]
		buf = io.BytesIO()
		pyqrcode.create(url, error="M").svg(buf, scale=4, module_color="#13235b", background="#ffffff", xmldecl=False, svgns=True, omithw=True)
		out.append({"key": k, "name": a["name"], "url": url, "path": a["start"], "desc": a["desc"], "color": a["color"],
			"icon": f"/assets/hipersign_trading/images/apps/{k}-192.png", "qr": buf.getvalue().decode()})
	return out
