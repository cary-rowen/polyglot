# -*- coding: utf-8 -*-

"""
cdpBridge - Synchronous bridge to Chrome Headless via Chrome DevTools Protocol (CDP).

Thread-safe: all WebSocket operations are serialized via a lock, and each
evaluateSync call uses a unique, atomically-incremented message ID.
"""

import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import winreg
from typing import Any
from collections.abc import Callable

import globalVars
from logHandler import log

import websocket


USER_DATA_DIR = os.path.join(globalVars.appArgs.configPath, "polyglot_chrome_ai")
DEVTOOLS_ACTIVE_PORT_FILE = os.path.join(USER_DATA_DIR, "DevToolsActivePort")
PAGE_FILE = os.path.join(USER_DATA_DIR, "chrome_ai.html")


class CdpError(Exception):
	"""Raised when Chrome DevTools Protocol communication fails."""

	pass


class CdpBridge:
	_instance = None
	_chromeProcess: subprocess.Popen | None = None
	_ws: websocket.WebSocket | None = None
	_wsLock = threading.Lock()
	_nextMsgId = 0
	_msgIdLock = threading.Lock()
	_debugPort: int | None = None

	@classmethod
	def getInstance(cls) -> "CdpBridge":
		"""Returns the singleton CDP bridge instance."""
		if cls._instance is None:
			cls._instance = CdpBridge()
		return cls._instance

	def _allocateMsgId(self) -> int:
		"""Returns a unique CDP command message ID."""
		with self._msgIdLock:
			self._nextMsgId += 1
			return self._nextMsgId

	def _getChromePath(self) -> str:
		"""Finds Chrome's executable path from Windows App Paths registration."""
		regPaths = [
			(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
			(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
		]
		for hkey, subKey in regPaths:
			try:
				with winreg.OpenKey(hkey, subKey) as key:
					path, _ = winreg.QueryValueEx(key, "")
					if os.path.exists(path):
						return path
			except FileNotFoundError:
				continue
		return ""

	def startBrowser(self) -> None:
		"""Starts the managed headless Chrome instance if it is not already running."""
		if self._chromeProcess and self._chromeProcess.poll() is None:
			return
		self._debugPort = None
		chromePath = self._getChromePath()
		if not chromePath:
			raise CdpError("Chrome not found. Please install Google Chrome.")
		os.makedirs(USER_DATA_DIR, exist_ok=True)
		pageUrl = self._preparePageUrl()
		try:
			os.remove(DEVTOOLS_ACTIVE_PORT_FILE)
		except FileNotFoundError:
			pass
		except OSError:
			log.warning("Could not remove stale Chrome DevToolsActivePort file.", exc_info=True)
		log.info(f"Launching Chrome Headless: {chromePath}")
		try:
			self._chromeProcess = subprocess.Popen(
				[
					chromePath,
					"--headless=new",
					"--remote-debugging-port=0",
					f"--user-data-dir={USER_DATA_DIR}",
					"--remote-allow-origins=*",
					"--enable-features=TranslationAPI",
					"--disable-gpu",
					"--mute-audio",
					"--no-first-run",
					"--no-default-browser-check",
					pageUrl,
				],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
			)
		except Exception as e:
			raise CdpError(f"Failed to start Chrome: {e}")

	def _preparePageUrl(self) -> str:
		"""Creates a local secure-context page and returns its file URL."""
		html = "<!doctype html><meta charset=\"utf-8\"><title>Polyglot Chrome AI</title>"
		with open(PAGE_FILE, "w", encoding="utf-8") as pageFile:
			pageFile.write(html)
		return Path(PAGE_FILE).resolve().as_uri()

	def _getDebugPort(self) -> int:
		"""Reads the ephemeral CDP port assigned to the managed Chrome process."""
		if self._debugPort is not None:
			return self._debugPort
		for _ in range(40):
			if self._chromeProcess and self._chromeProcess.poll() is not None:
				raise CdpError(f"Chrome exited before CDP became available: {self._chromeProcess.returncode}")
			try:
				with open(DEVTOOLS_ACTIVE_PORT_FILE, "r", encoding="utf-8") as portFile:
					firstLine = portFile.readline().strip()
					if firstLine:
						self._debugPort = int(firstLine)
						return self._debugPort
			except (FileNotFoundError, ValueError, OSError):
				time.sleep(0.25)
		raise CdpError("Timeout waiting for Chrome DevToolsActivePort.")

	def _readJsonEndpoint(self, path: str, method: str = "GET") -> Any:
		"""Reads a JSON response from the managed Chrome debugging HTTP endpoint."""
		port = self._getDebugPort()
		url = f"http://127.0.0.1:{port}{path}"
		req = urllib.request.Request(url, method=method)
		with urllib.request.urlopen(req, timeout=1) as response:
			return json.loads(response.read().decode("utf-8"))

	def _createPageTarget(self) -> str | None:
		"""Creates a page target and returns its WebSocket URL if available."""
		quotedUrl = urllib.parse.quote(self._preparePageUrl(), safe="")
		try:
			target = self._readJsonEndpoint(f"/json/new?{quotedUrl}", method="PUT")
		except Exception:
			log.warning("Failed to create Chrome CDP page target.", exc_info=True)
			return None
		if isinstance(target, dict):
			wsUrl = target.get("webSocketDebuggerUrl")
			if isinstance(wsUrl, str):
				return wsUrl
		return None

	def _getWebSocketUrl(self) -> str:
		"""Returns a page target WebSocket URL from the managed Chrome process."""
		for _ in range(20):
			try:
				data = self._readJsonEndpoint("/json/list")
				pages = [t for t in data if t.get("type") == "page"]
				if pages:
					return pages[0]["webSocketDebuggerUrl"]
				wsUrl = self._createPageTarget()
				if wsUrl:
					return wsUrl
			except Exception:
				time.sleep(0.5)
		raise CdpError("Timeout waiting for Chrome CDP endpoint.")

	def ensureConnection(self) -> None:
		"""Ensures that a Runtime-enabled WebSocket connection is ready."""
		with self._wsLock:
			if self._ws and self._ws.connected:
				return
			self.startBrowser()
			wsUrl = self._getWebSocketUrl()
			log.info(f"Connecting to CDP WebSocket: {wsUrl}")
			try:
				self._ws = websocket.create_connection(wsUrl, timeout=300)
				enableId = self._allocateMsgId()
				self._ws.send(json.dumps({"id": enableId, "method": "Runtime.enable"}))
				while True:
					response = json.loads(self._ws.recv())
					if response.get("id") == enableId:
						if "error" in response:
							raise CdpError(f"CDP error: {response['error']}")
						break
				log.debug("CDP Runtime domain enabled.")
			except Exception as e:
				self._ws = None
				raise CdpError(f"WebSocket connection failed: {e}")

	def _formatExceptionDetails(self, exceptionDetails: dict[str, Any]) -> str:
		"""Formats CDP Runtime exception details for logs and user-facing errors."""
		text = exceptionDetails.get("text", "Runtime exception")
		exception = exceptionDetails.get("exception", {})
		description = exception.get("description") if isinstance(exception, dict) else None
		if description:
			return f"{text}: {description}"
		return str(text)

	def evaluateSync(
		self,
		jsPayload: str,
		onConsoleLog: Callable[[str], None] | None = None,
	) -> dict[str, Any]:
		"""
		Thread-safe JS evaluation. Acquires the WebSocket lock for the
		entire send/recv cycle, ensuring only one evaluation runs at a time.
		Automatically retries once on stale connection errors (e.g. WinError 10053).
		"""
		for attempt in range(2):
			self.ensureConnection()
			msgId = self._allocateMsgId()
			cmd = {
				"id": msgId,
				"method": "Runtime.evaluate",
				"params": {
					"expression": jsPayload,
					"awaitPromise": True,
					"returnByValue": True,
					"userGesture": True,
				},
			}
			with self._wsLock:
				try:
					log.debug(f"CDP: evaluate id={msgId}, payload={len(jsPayload)} chars")
					self._ws.send(json.dumps(cmd))
					while True:
						responseStr = self._ws.recv()
						if not responseStr:
							raise CdpError("WebSocket closed unexpectedly.")
						response = json.loads(responseStr)
						if response.get("method") == "Runtime.consoleAPICalled":
							args = response.get("params", {}).get("args", [])
							for arg in args:
								logText = str(arg.get("value", ""))
								if onConsoleLog and logText:
									onConsoleLog(logText)
							continue
						if response.get("id") == msgId:
							if "error" in response:
								raise CdpError(f"CDP error: {response['error']}")
							exceptionDetails = response.get("result", {}).get("exceptionDetails")
							if isinstance(exceptionDetails, dict):
								raise CdpError(self._formatExceptionDetails(exceptionDetails))
							resultValue = response.get("result", {}).get("result", {}).get("value", "{}")
							if isinstance(resultValue, dict):
								return resultValue
							if isinstance(resultValue, str):
								try:
									return json.loads(resultValue)
								except (json.JSONDecodeError, TypeError):
									return {"code": "PARSE_ERR", "raw": resultValue}
							return {"code": "PARSE_ERR", "raw": str(resultValue)}
				except websocket.WebSocketTimeoutException:
					raise CdpError("Timed out waiting for Chrome AI response.")
				except CdpError:
					raise
				except Exception as e:
					self._ws = None
					if attempt == 0:
						log.warning(f"WebSocket connection lost, reconnecting: {e}")
						continue
					raise CdpError(f"WebSocket error: {e}")

	def terminate(self) -> None:
		"""Closes the CDP connection and terminates the managed Chrome process."""
		if self._ws:
			try:
				self._ws.close()
			except Exception:
				pass
			self._ws = None
		if self._chromeProcess:
			log.info("Terminating Chrome CDP process.")
			try:
				self._chromeProcess.terminate()
				self._chromeProcess.wait(timeout=5)
			except subprocess.TimeoutExpired:
				log.warning("Chrome did not exit gracefully, force killing.")
				self._chromeProcess.kill()
				self._chromeProcess.wait(timeout=3)
			except Exception:
				pass
			self._chromeProcess = None
			self._debugPort = None
