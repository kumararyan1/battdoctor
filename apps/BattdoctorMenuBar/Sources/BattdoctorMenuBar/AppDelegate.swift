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
        popover.contentSize = NSSize(width: 380, height: 540)
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
        let onBattery = battery.externalConnected == false
        let energy = payload.currentPowerW
            ?? battery.systemPowerW
            ?? battery.powerW.map { Swift.abs($0) }
        let culprit = payload.primaryCulprit
        let severity = max(
            culprit?.severity ?? 0,
            (battery.temperatureC ?? 0) >= 40 ? 9 : 0
        )

        button.title = ""
        button.contentTintColor = nil
        button.image = StatusItemRenderer.image(
            energyW: energy,
            culprit: culprit,
            batteryPercent: battery.percent,
            onBattery: onBattery,
            severity: severity,
            appearance: NSApp.effectiveAppearance
        )

        let energyText = energy.map { String(format: "%.1f W", $0) } ?? "— W"
        var tooltip = ["Battdoctor: \(energyText)", culprit?.name ?? "No signal"]
        if onBattery, let percent = battery.percent {
            tooltip.append("\(Int(percent.rounded()))% battery")
        }
        if let runtime = runtimeText(battery.timeRemainingMin) {
            tooltip.append(runtime)
        }
        button.toolTip = tooltip.joined(separator: " · ")
        button.setAccessibilityLabel(button.toolTip ?? "Battdoctor")
    }

    private func runtimeText(_ minutes: Int?) -> String? {
        guard let minutes = minutes, minutes > 0 else {
            return nil
        }
        let hours = minutes / 60
        let remainder = minutes % 60
        return hours > 0 ? "\(hours)h \(remainder)m" : "\(remainder)m"
    }
}
