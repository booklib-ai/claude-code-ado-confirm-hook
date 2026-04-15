import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var result = "cancel"

    func applicationDidFinishLaunching(_ notification: Notification) {
        let width: CGFloat = 720
        let height: CGFloat = 500

        // Find the screen where the mouse cursor is (current display)
        let mouseLocation = NSEvent.mouseLocation
        let currentScreen = NSScreen.screens.first(where: { NSMouseInRect(mouseLocation, $0.frame, false) }) ?? NSScreen.main!
        let screenFrame = currentScreen.visibleFrame
        let x = screenFrame.origin.x + (screenFrame.width - width) / 2
        let y = screenFrame.origin.y + (screenFrame.height - height) / 2

        window = NSWindow(
            contentRect: NSRect(x: x, y: y, width: width, height: height),
            styleMask: [.titled, .closable, .resizable],
            backing: .buffered, defer: false)
        window.title = "Azure DevOps — Confirm Action"
        window.level = .modalPanel
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.backgroundColor = NSColor(srgbRed: 0.118, green: 0.118, blue: 0.118, alpha: 1)

        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "action")

        let buttonJS = """
        document.addEventListener('DOMContentLoaded', function() {
            var d = document.createElement('div');
            d.style.cssText = 'display:flex;justify-content:flex-end;gap:8px;margin-top:16px;padding-top:12px;border-top:1px solid #3c3c3c';
            d.innerHTML = '<button onclick="window.webkit.messageHandlers.action.postMessage(\\'approve\\')" style="font-family:-apple-system;font-size:13px;padding:6px 20px;border:none;border-radius:4px;cursor:pointer;color:#fff;background:#0e639c;font-weight:600">Approve</button><button onclick="window.webkit.messageHandlers.action.postMessage(\\'cancel\\')" style="font-family:-apple-system;font-size:13px;padding:6px 20px;border:none;border-radius:4px;cursor:pointer;color:#fff;background:#3c3c3c">Cancel</button>';
            document.body.appendChild(d);
        });
        """
        config.userContentController.addUserScript(
            WKUserScript(source: buttonJS, injectionTime: .atDocumentStart, forMainFrameOnly: true))

        let webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]

        let htmlPath = CommandLine.arguments[1]
        let url = URL(fileURLWithPath: htmlPath)
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())

        window.contentView!.addSubview(webView)
        window.orderFrontRegardless()

        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if event.keyCode == 53 {
                self.result = "cancel"
                NSApp.terminate(nil)
                return nil
            } else if event.keyCode == 36 {
                self.result = "approve"
                NSApp.terminate(nil)
                return nil
            }
            return event
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func userContentController(_ c: WKUserContentController, didReceive msg: WKScriptMessage) {
        result = msg.body as? String ?? "cancel"
        NSApp.terminate(nil)
    }

    func applicationWillTerminate(_ notification: Notification) {
        FileHandle.standardOutput.write(result.data(using: .utf8)!)
    }
}

let delegate = AppDelegate()
NSApplication.shared.delegate = delegate
NSApplication.shared.setActivationPolicy(.accessory)
NSApplication.shared.run()
