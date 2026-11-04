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
            button.imagePosition = .imageLeading
            button.title = "..."
            button.image = NSImage(systemSymbolName: "battery.75", accessibilityDescription: "Battery")
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
            button.title = "..."
            button.image = NSImage(systemSymbolName: "battery.0", accessibilityDescription: "Battery unavailable")
            button.contentTintColor = .secondaryLabelColor
            return
        }

        let battery = payload.snapshot.battery
        let percent = battery.percent ?? 0
        button.title = "\(Int(percent.rounded()))%"
        button.image = NSImage(
            systemSymbolName: symbolName(for: battery),
            accessibilityDescription: "Battery"
        )

        if payload.snapshot.memory.pressure == "critical" {
            button.contentTintColor = .systemOrange
        } else if percent < 15 {
            button.contentTintColor = .systemRed
        } else {
            button.contentTintColor = .labelColor
        }
    }

    private func symbolName(for battery: BatteryInfo) -> String {
        if battery.charging == true {
            return "battery.100.bolt"
        }
        let percent = battery.percent ?? 0
        switch percent {
        case ..<10: return "battery.0"
        case ..<25: return "battery.25"
        case ..<50: return "battery.50"
        case ..<75: return "battery.75"
        default: return "battery.100"
        }
    }
}
