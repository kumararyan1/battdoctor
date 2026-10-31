import AppKit
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate, NSPopoverDelegate {
    private var statusItem: NSStatusItem!
    private var popover: NSPopover!
    private var timer: Timer?
    private let model = BatteryModel()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.target = self
            button.action = #selector(togglePopover)
            button.imagePosition = .imageOnly
            button.imageScaling = .scaleProportionallyDown
            button.title = ""
            button.image = StatusItemRenderer.placeholder(appearance: NSApp.effectiveAppearance)
            button.toolTip = "Battdoctor is loading"
        }

        popover = NSPopover()
        popover.behavior = .transient
        popover.delegate = self
        popover.contentSize = NSSize(width: 380, height: 560)
        popover.contentViewController = NSHostingController(rootView: PopoverView(model: model))

        model.onUpdate = { [weak self] in
            self?.updateStatusItem()
        }
        model.refresh()

        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.model.refresh()
        }
        RunLoop.main.add(timer!, forMode: .common)

        DistributedNotificationCenter.default.addObserver(
            self,
            selector: #selector(appearanceDidChange),
            name: NSNotification.Name("AppleInterfaceThemeChangedNotification"),
            object: nil
        )
    }

    @objc private func appearanceDidChange() {
        updateStatusItem()
    }

    @objc private func togglePopover() {
        guard let button = statusItem.button else {
            return
        }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            model.refresh()
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }

    private func updateStatusItem() {
        guard let button = statusItem.button else {
            return
        }

        guard let payload = model.payload else {
            button.title = ""
            button.image = StatusItemRenderer.placeholder(appearance: NSApp.effectiveAppearance)
            button.contentTintColor = nil
            button.toolTip = model.error ?? "Battdoctor is loading"
            button.setAccessibilityLabel("Battdoctor loading")
            return
        }

        let battery = payload.snapshot.battery
        let percent = battery.percent ?? 0
        let critical = payload.snapshot.memory.pressure == "critical"
        button.title = ""
        button.contentTintColor = nil
        button.image = StatusItemRenderer.image(
            percent: percent,
            charging: battery.charging == true,
            critical: critical,
            appearance: NSApp.effectiveAppearance
        )
        let health = Int((battery.healthPercent ?? 0).rounded())
        let pressure = payload.snapshot.memory.pressure ?? "unknown"
        button.toolTip = "Battdoctor: \(Int(percent.rounded()))% · \(health)% health · \(pressure) memory"
        button.setAccessibilityLabel(button.toolTip ?? "Battdoctor")
    }
}
