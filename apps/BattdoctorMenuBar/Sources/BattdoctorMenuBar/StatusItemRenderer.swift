import AppKit

enum StatusItemRenderer {
    private enum Piece {
        case energy(String)
        case culprit(String)
        case percent(String)
        case separator
        case plain(String)
    }

    private static let height: CGFloat = 18
    private static let cornerRadius: CGFloat = 5
    private static let maxWidth: CGFloat = 180
    private static let horizontalPadding: CGFloat = 7
    private static let glyphWidth: CGFloat = 9
    private static let glyphGap: CGFloat = 4

    static func image(
        energyW: Double?,
        culprit: PrimaryCulprit?,
        batteryPercent: Double?,
        onBattery: Bool,
        severity: Int,
        appearance: NSAppearance
    ) -> NSImage {
        let energyText = energyW.map { String(format: "%.1f W", $0) } ?? "— W"
        let culpritText = culprit.map { shortened($0.name, limit: 14) } ?? "No signal"

        var pieces: [Piece] = [.energy(energyText), .separator, .culprit(culpritText)]
        if onBattery, let percent = batteryPercent {
            pieces.append(.separator)
            pieces.append(.percent("\(Int(percent.rounded()))%"))
        }

        return render(pieces: pieces, severity: severity, appearance: appearance, neutral: false)
    }

    static func placeholder(appearance: NSAppearance) -> NSImage {
        render(pieces: [.plain("...")], severity: 0, appearance: appearance, neutral: true)
    }

    private static func render(
        pieces: [Piece],
        severity: Int,
        appearance: NSAppearance,
        neutral: Bool
    ) -> NSImage {
        let dark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        let energyFont = NSFont.monospacedDigitSystemFont(ofSize: 10.5, weight: .semibold)
        let culpritFont = NSFont.systemFont(ofSize: 10, weight: .medium)
        let detailFont = NSFont.systemFont(ofSize: 10, weight: .regular)

        let text = NSMutableAttributedString()
        for piece in pieces {
            let string: String
            let font: NSFont
            let alpha: CGFloat
            switch piece {
            case let .energy(value):
                string = value
                font = energyFont
                alpha = 1
            case let .culprit(value), let .percent(value), let .plain(value):
                string = value
                font = culpritFont
                alpha = 1
            case .separator:
                string = " · "
                font = detailFont
                alpha = 0.7
            }
            text.append(NSAttributedString(string: string, attributes: [
                .font: font,
                .foregroundColor: NSColor.white.withAlphaComponent(alpha),
            ]))
        }

        let paragraph = NSMutableParagraphStyle()
        paragraph.lineBreakMode = .byTruncatingTail
        text.addAttribute(
            .paragraphStyle,
            value: paragraph,
            range: NSRange(location: 0, length: text.length)
        )

        let textSize = text.size()
        let leading = neutral ? horizontalPadding : horizontalPadding + glyphWidth + glyphGap
        let contentWidth = leading + textSize.width + horizontalPadding
        let width = max(28, min(ceil(contentWidth), maxWidth))
        let size = NSSize(width: width, height: height)

        let image = NSImage(size: size, flipped: false) { _ in
            let pill = NSBezierPath(
                roundedRect: NSRect(x: 0.5, y: 0.5, width: size.width - 1, height: height - 1),
                xRadius: cornerRadius,
                yRadius: cornerRadius
            )

            let colors: [NSColor]
            if neutral {
                let indigo = NSColor(calibratedRed: 0.30, green: 0.27, blue: 0.80, alpha: 1)
                colors = [indigo, indigo]
            } else if severity >= 9 {
                colors = [
                    NSColor(calibratedRed: 0.94, green: 0.34, blue: 0.34, alpha: 1),
                    NSColor(calibratedRed: 0.96, green: 0.62, blue: 0.18, alpha: 1),
                ]
            } else if dark {
                colors = [
                    NSColor(calibratedRed: 0.36, green: 0.32, blue: 0.92, alpha: 1),
                    NSColor(calibratedRed: 0.08, green: 0.72, blue: 0.68, alpha: 1),
                ]
            } else {
                colors = [
                    NSColor(calibratedRed: 0.28, green: 0.24, blue: 0.82, alpha: 1),
                    NSColor(calibratedRed: 0.05, green: 0.60, blue: 0.62, alpha: 1),
                ]
            }
            NSGradient(colors: colors)?.draw(in: pill, angle: 0)

            NSColor.white.withAlphaComponent(dark ? 0.22 : 0.32).setStroke()
            pill.lineWidth = 1
            pill.stroke()

            if !neutral,
               let symbol = NSImage(
                   systemSymbolName: "bolt.fill",
                   accessibilityDescription: nil
               )?.withSymbolConfiguration(.init(pointSize: 8.5, weight: .bold)) {
                let glyphRect = NSRect(
                    x: horizontalPadding,
                    y: (height - glyphWidth) / 2,
                    width: glyphWidth,
                    height: glyphWidth
                )
                symbol.tinted(NSColor.white).draw(in: glyphRect)
            }

            let textRect = NSRect(
                x: leading,
                y: (height - textSize.height) / 2 + 0.5,
                width: max(0, size.width - leading - horizontalPadding),
                height: textSize.height
            )
            text.draw(in: textRect)
            return true
        }

        image.isTemplate = false
        return image
    }

    private static func shortened(_ text: String, limit: Int) -> String {
        guard text.count > limit else {
            return text
        }
        return String(text.prefix(limit - 1)) + "…"
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
