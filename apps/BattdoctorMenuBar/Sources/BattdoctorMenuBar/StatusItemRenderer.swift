import AppKit

enum StatusItemRenderer {
    static func image(
        percent: Double,
        charging: Bool,
        critical: Bool,
        appearance: NSAppearance
    ) -> NSImage {
        render(
            text: "\(Int(percent.rounded()))%",
            symbolName: charging ? "bolt.fill" : batterySymbol(percent),
            critical: critical,
            appearance: appearance
        )
    }

    static func placeholder(appearance: NSAppearance) -> NSImage {
        render(text: "...", symbolName: "battery.0", critical: false, appearance: appearance)
    }

    private static func render(
        text: String,
        symbolName: String,
        critical: Bool,
        appearance: NSAppearance
    ) -> NSImage {
        let dark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        let height: CGFloat = 18
        let font = NSFont.systemFont(ofSize: 10.5, weight: .semibold)
        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: NSColor.white,
        ]
        let textSize = (text as NSString).size(withAttributes: attributes)
        let iconSize: CGFloat = 11
        let horizontalPadding: CGFloat = 7
        let gap: CGFloat = 3
        let width = horizontalPadding * 2 + iconSize + gap + textSize.width
        let size = NSSize(width: ceil(width), height: height)

        let image = NSImage(size: size, flipped: false) { rect in
            let pill = NSBezierPath(
                roundedRect: rect.insetBy(dx: 0.5, dy: 0.5),
                xRadius: height / 2,
                yRadius: height / 2
            )

            let colors: [NSColor]
            if critical {
                colors = [
                    NSColor(calibratedRed: 0.93, green: 0.30, blue: 0.30, alpha: 1),
                    NSColor(calibratedRed: 0.98, green: 0.58, blue: 0.18, alpha: 1),
                ]
            } else if dark {
                colors = [
                    NSColor(calibratedRed: 0.40, green: 0.36, blue: 0.95, alpha: 1),
                    NSColor(calibratedRed: 0.08, green: 0.74, blue: 0.70, alpha: 1),
                ]
            } else {
                colors = [
                    NSColor(calibratedRed: 0.28, green: 0.24, blue: 0.82, alpha: 1),
                    NSColor(calibratedRed: 0.05, green: 0.60, blue: 0.62, alpha: 1),
                ]
            }

            NSGradient(colors: colors)?.draw(in: pill, angle: 0)
            NSColor.white.withAlphaComponent(dark ? 0.22 : 0.32).setStroke()
            pill.lineWidth = 0.8
            pill.stroke()

            if let symbol = NSImage(
                systemSymbolName: symbolName,
                accessibilityDescription: nil
            )?.withSymbolConfiguration(.init(pointSize: 9.5, weight: .bold)) {
                let iconRect = NSRect(
                    x: horizontalPadding,
                    y: (height - iconSize) / 2,
                    width: iconSize,
                    height: iconSize
                )
                symbol.tinted(NSColor.white).draw(in: iconRect)
            }

            let textRect = NSRect(
                x: horizontalPadding + iconSize + gap,
                y: (height - textSize.height) / 2 + 0.5,
                width: textSize.width,
                height: textSize.height
            )
            (text as NSString).draw(in: textRect, withAttributes: attributes)
            return true
        }

        image.isTemplate = false
        return image
    }

    private static func batterySymbol(_ percent: Double) -> String {
        switch percent {
        case ..<10: return "battery.0"
        case ..<25: return "battery.25"
        case ..<50: return "battery.50"
        case ..<75: return "battery.75"
        default: return "battery.100"
        }
    }
}

private extension NSImage {
    func tinted(_ color: NSColor) -> NSImage {
        guard let copy = self.copy() as? NSImage else {
            return self
        }
        copy.lockFocus()
        color.set()
        NSRect(origin: .zero, size: copy.size).fill(using: .sourceAtop)
        copy.unlockFocus()
        copy.isTemplate = false
        return copy
    }
}
