import AppKit
import SwiftUI

struct PopoverView: View {
    @ObservedObject var model: BatteryModel
    @Environment(\.colorScheme) private var scheme

    private let nonEnergyCauses: Set<String> = [
        "Battery wear",
        "Memory pressure / swap",
        "Recent macOS update",
        "Background launch agents",
    ]

    var body: some View {
        ZStack {
            background
            if let payload = model.payload {
                loaded(payload)
            } else {
                emptyState
            }
        }
        .frame(width: 380, height: 540)
    }

    private var background: some View {
        ZStack(alignment: .topLeading) {
            Brand.canvas(scheme)
            RadialGradient(
                colors: [Brand.indigo.opacity(scheme == .dark ? 0.10 : 0.06), .clear],
                center: .topLeading,
                startRadius: 0,
                endRadius: 320
            )
        }
        .ignoresSafeArea()
    }

    private func loaded(_ payload: MenubarPayload) -> some View {
        VStack(spacing: 0) {
            brandBar
            hairline
            ScrollView(.vertical, showsIndicators: false) {
                VStack(alignment: .leading, spacing: 12) {
                    hero(payload)
                    culprit(payload)
                    batteryLine(payload)
                    topUsers(payload)
                    actions(payload)
                    memoryNote(payload)
                }
                .padding(.horizontal, 16)
                .padding(.top, 10)
                .padding(.bottom, 12)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            hairline
            footer(payload)
        }
    }

    private var brandBar: some View {
        HStack(spacing: 8) {
            brandMark(size: 18)
            Text("battdoctor")
                .font(.system(size: 13, weight: .semibold, design: .rounded))
                .foregroundStyle(.primary)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 11)
    }

    private func brandMark(size: CGFloat) -> some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.3, style: .continuous)
                .fill(Brand.indigo)
                .frame(width: size, height: size)
            Image(systemName: "bolt.heart.fill")
                .font(.system(size: size * 0.46, weight: .bold))
                .foregroundStyle(.white)
        }
        .accessibilityHidden(true)
    }

    private func hero(_ payload: MenubarPayload) -> some View {
        let watts = currentWatts(payload)
        let subtitle = heroSubtitle(payload, watts: watts)
        let readableWatts = watts.map { String(format: "%.1f", $0) }

        return VStack(alignment: .leading, spacing: 2) {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(readableWatts ?? "—")
                    .font(.system(size: 44, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.primary)
                Text("W")
                    .font(.system(size: 19, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
            }
            Text(subtitle)
                .font(.system(size: 11))
                .monospacedDigit()
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(card)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            readableWatts.map { "Current energy draw, \($0) watts" }
                ?? "Current energy draw unavailable"
        )
        .accessibilityValue(subtitle)
    }

    private func culprit(_ payload: MenubarPayload) -> some View {
        let info = primaryInfo(payload)

        return HStack(alignment: .top, spacing: 9) {
            Image(systemName: info.icon)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(severityColor(info.severity))
                .frame(width: 16, height: 16)
                .padding(.top, 1)
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(info.name)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    if let trailing = culpritTrailing(info) {
                        Text(trailing)
                            .font(.system(size: 12, weight: .semibold))
                            .monospacedDigit()
                            .foregroundStyle(.primary)
                    }
                }
                Text(info.detail)
                    .font(.system(size: 11))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                if !info.note.isEmpty {
                    Text(info.note)
                        .font(.system(size: 10))
                        .monospacedDigit()
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(info.accessibility)
    }

    private func batteryLine(_ payload: MenubarPayload) -> some View {
        let battery = payload.snapshot.battery
        let health = payload.batteryHealthPct ?? battery.healthPercent
        let healthText = health.map { "\(Int($0.rounded()))%" } ?? "—"
        let meta = batteryMeta(cycles: battery.cycleCount, temperature: battery.temperatureC)
        let spokenMeta = meta.isEmpty
            ? ""
            : ", \(meta.replacingOccurrences(of: " · ", with: ", "))"

        return HStack(spacing: 8) {
            Text("Battery health")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
            Text(healthText)
                .font(.system(size: 11.5, weight: .semibold))
                .monospacedDigit()
                .foregroundStyle(healthColor(health))
            Text(meta)
                .font(.system(size: 11))
                .monospacedDigit()
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Spacer(minLength: 6)
            healthCapsule(health)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Battery health \(healthText)\(spokenMeta)")
    }

    private func healthCapsule(_ health: Double?) -> some View {
        let fraction = min(max((health ?? 0) / 100, 0), 1)

        return ZStack(alignment: .leading) {
            Capsule()
                .fill(Color.primary.opacity(0.10))
            Capsule()
                .fill(healthColor(health))
                .frame(width: 56 * fraction)
        }
        .frame(width: 56, height: 2)
        .accessibilityHidden(true)
    }

    private func topUsers(_ payload: MenubarPayload) -> some View {
        let users = Array(
            payload.causes
                .filter { !nonEnergyCauses.contains($0.name) }
                .prefix(3)
        )

        return VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Top energy users")
            if users.isEmpty {
                Text("No standout energy users right now.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                    .background(card)
            } else {
                VStack(spacing: 0) {
                    ForEach(users.indices, id: \.self) { index in
                        if index > 0 {
                            hairline
                        }
                        userRow(users[index])
                    }
                }
                .background(card)
            }
        }
    }

    private func userRow(_ cause: DrainCause) -> some View {
        let hasEstimate = cause.estimatedW != nil || cause.sharePct != nil

        return HStack(alignment: .top, spacing: 9) {
            Image(systemName: icon(forName: cause.name))
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(Brand.indigo)
                .frame(width: 16)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 2) {
                Text(cause.name)
                    .font(.system(size: 12.5, weight: .semibold))
                    .foregroundStyle(.primary)
                    .lineLimit(1)
                Text(cause.evidence.first ?? "No direct evidence")
                    .font(.system(size: 11))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 6)
            Text(wattLabel(cause))
                .font(.system(size: 11, weight: .semibold))
                .monospacedDigit()
                .foregroundStyle(.primary)
                .opacity(hasEstimate ? 1 : 0.45)
                .padding(.top, 1)
        }
        .padding(.horizontal, 13)
        .padding(.vertical, 6)
        .frame(minHeight: 42, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            "\(cause.name), \(cause.evidence.first ?? "no direct evidence"), \(accessibleTrailing(cause))"
        )
    }

    private func actions(_ payload: MenubarPayload) -> some View {
        let items = dedupedActions(payload)

        return VStack(alignment: .leading, spacing: 6) {
            sectionLabel("Do this")
            if items.isEmpty {
                Text("Nothing obvious right now — keep an eye on the top users.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            } else {
                ForEach(items.indices, id: \.self) { index in
                    actionRow(items[index], highlighted: index == 0)
                }
            }
        }
    }

    private func actionRow(_ text: String, highlighted: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "arrow.right")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(highlighted ? Brand.indigo : Color.secondary)
                .frame(width: 12, height: 14)
                .padding(.top, 1)
            Text(text)
                .font(.system(size: 11))
                .foregroundStyle(highlighted ? .primary : .secondary)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, highlighted ? 9 : 2)
        .padding(.vertical, highlighted ? 7 : 2)
        .background {
            if highlighted {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Brand.indigo.opacity(scheme == .dark ? 0.16 : 0.10))
            }
        }
    }

    @ViewBuilder
    private func memoryNote(_ payload: MenubarPayload) -> some View {
        let memory = payload.snapshot.memory
        let pressure = (memory.pressure ?? "").lowercased()

        if pressure == "warning" || pressure == "critical" {
            let swap = formatSwap(memory.swapUsedMb)
            HStack(spacing: 6) {
                Circle()
                    .fill(severityColor(pressure == "critical" ? 9 : 7))
                    .frame(width: 5, height: 5)
                Text("Memory pressure \(pressure) · swap \(swap) used")
                    .font(.system(size: 10))
                    .monospacedDigit()
                    .foregroundStyle(.tertiary)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Memory pressure \(pressure), swap \(swap) used")
        }
    }

    private func footer(_ payload: MenubarPayload) -> some View {
        HStack(spacing: 14) {
            Text(footerTimestamp)
                .font(.system(size: 10))
                .monospacedDigit()
                .foregroundStyle(.tertiary)
            Spacer(minLength: 0)
            footerButton("doc.on.doc", help: "Copy summary") {
                BattdoctorClient.copySummary(payload)
            }
            footerButton("arrow.clockwise", help: "Refresh") {
                model.refresh()
            }
            footerButton("power", help: "Quit") {
                NSApp.terminate(nil)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }

    private func footerButton(
        _ symbol: String,
        help: String,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.secondary)
                .frame(width: 20, height: 18)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(help)
        .accessibilityLabel(help)
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            brandMark(size: 38)
            Text("battdoctor")
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .foregroundStyle(.primary)
            Text(model.error ?? "Waiting for battdoctor…")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .frame(maxWidth: 260)
            Button("Refresh") {
                model.refresh()
            }
            .buttonStyle(.borderedProminent)
            .tint(Brand.indigo)
            .controlSize(.regular)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(24)
    }

    private var card: some View {
        RoundedRectangle(cornerRadius: 12, style: .continuous)
            .fill(Brand.card(scheme))
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(Brand.cardStroke(scheme), lineWidth: 1)
            )
    }

    private var hairline: some View {
        Rectangle()
            .fill(Brand.cardStroke(scheme))
            .frame(height: 1)
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 10, weight: .semibold))
            .tracking(0.8)
            .foregroundStyle(.secondary)
    }

    private var footerTimestamp: String {
        guard let updated = model.lastUpdated else {
            return "Not updated yet"
        }
        return "Updated \(updated.formatted(date: .omitted, time: .shortened))"
    }

    private func currentWatts(_ payload: MenubarPayload) -> Double? {
        let candidates = [
            payload.currentPowerW,
            payload.snapshot.battery.systemPowerW,
            payload.snapshot.battery.powerW,
        ]
        for candidate in candidates {
            guard let candidate, candidate.isFinite else {
                continue
            }
            let value = abs(candidate)
            if value > 0.05 {
                return value
            }
        }
        return nil
    }

    private func heroSubtitle(_ payload: MenubarPayload, watts: Double?) -> String {
        let battery = payload.snapshot.battery
        if battery.externalConnected == true {
            let state = battery.charging == true ? "on AC · charging" : "on AC"
            return watts == nil ? "\(state) · draw unavailable" : state
        }
        if let runtime = payload.expectedRuntimeMin, runtime.isFinite, runtime > 0 {
            return "on battery · \(duration(runtime))"
        }
        return watts == nil ? "on battery · draw unavailable" : "on battery · runtime unknown"
    }

    private func duration(_ minutes: Double) -> String {
        let total = Int(minutes.rounded())
        let hours = total / 60
        let mins = total % 60
        return hours > 0 ? "\(hours)h \(mins)m" : "\(mins)m"
    }

    private func primaryInfo(_ payload: MenubarPayload) -> PrimaryInfo {
        if let primary = payload.primaryCulprit {
            let match = payload.causes.first { $0.name == primary.name }
            let estimated = primary.estimatedW ?? match?.estimatedW
            let share = match?.sharePct
            let detail = primary.detail.isEmpty
                ? (match?.evidence.first ?? primary.name)
                : primary.detail
            return PrimaryInfo(
                name: primary.name,
                detail: detail,
                note: confidenceNote(primary.confidence, estimatedW: estimated, sharePct: share),
                severity: primary.severity,
                estimatedW: estimated,
                sharePct: share,
                icon: icon(forName: primary.name)
            )
        }

        if let cause = payload.causes.first(where: { !nonEnergyCauses.contains($0.name) }) {
            return PrimaryInfo(
                name: cause.name,
                detail: cause.evidence.first ?? cause.action,
                note: confidenceNote(cause.confidence, estimatedW: cause.estimatedW, sharePct: cause.sharePct),
                severity: cause.severity,
                estimatedW: cause.estimatedW,
                sharePct: cause.sharePct,
                icon: icon(forName: cause.name)
            )
        }

        return PrimaryInfo(
            name: "No strong signal",
            detail: "No energy-heavy app or setting stood out.",
            note: "",
            severity: 1,
            estimatedW: nil,
            sharePct: nil,
            icon: "waveform.path.ecg"
        )
    }

    private func culpritTrailing(_ info: PrimaryInfo) -> String? {
        if let watts = info.estimatedW {
            return "~\(String(format: "%.1f", watts)) W"
        }
        if let share = info.sharePct {
            return "\(String(format: "%.0f", share))% of draw"
        }
        return nil
    }

    private func confidenceNote(
        _ confidence: String,
        estimatedW: Double?,
        sharePct: Double?
    ) -> String {
        guard !confidence.isEmpty else {
            return ""
        }
        let base = "\(confidence.capitalized) confidence"
        if estimatedW != nil {
            return "\(base) · watt estimate"
        }
        if sharePct != nil {
            return "\(base) · share of draw"
        }
        return "\(base) · not watt-measured"
    }

    private func wattLabel(_ cause: DrainCause) -> String {
        if let watts = cause.estimatedW {
            return "~\(String(format: "%.1f", watts)) W"
        }
        if let share = cause.sharePct {
            return "\(String(format: "%.0f", share))%"
        }
        return "—"
    }

    private func accessibleTrailing(_ cause: DrainCause) -> String {
        if let watts = cause.estimatedW {
            return "about \(String(format: "%.1f", watts)) watts"
        }
        if let share = cause.sharePct {
            return "\(String(format: "%.0f", share)) percent of draw"
        }
        return "watt estimate unavailable"
    }

    private func batteryMeta(cycles: Int?, temperature: Double?) -> String {
        var parts: [String] = []
        if let cycles {
            parts.append("\(cycles) cycles")
        }
        if let temperature, temperature.isFinite {
            parts.append("\(String(format: "%.1f", temperature))°C")
        }
        return parts.isEmpty ? "" : " · " + parts.joined(separator: " · ")
    }

    private func formatSwap(_ megabytes: Double?) -> String {
        guard let megabytes, megabytes.isFinite else {
            return "unknown"
        }
        if megabytes >= 1024 {
            return String(format: "%.1f GB", megabytes / 1024)
        }
        return "\(Int(megabytes.rounded())) MB"
    }

    private func dedupedActions(_ payload: MenubarPayload) -> [String] {
        var seen = Set<String>()
        var result: [String] = []
        for cause in payload.causes {
            let action = cause.action.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !action.isEmpty else {
                continue
            }
            if seen.insert(action).inserted {
                result.append(action)
            }
            if result.count == 3 {
                break
            }
        }
        return result
    }

    private func healthColor(_ health: Double?) -> Color {
        guard let health else {
            return Color.secondary
        }
        if health >= 80 {
            return Brand.teal
        }
        if health >= 60 {
            return Brand.amber
        }
        return Brand.coral
    }

    private func severityColor(_ severity: Int) -> Color {
        if severity >= 9 {
            return Brand.coral
        }
        if severity >= 7 {
            return Brand.amber
        }
        return Brand.indigo
    }

    private func icon(forName name: String) -> String {
        let lower = name.lowercased()
        if lower.contains("memory") || lower.contains("swap") {
            return "memorychip"
        }
        if lower.contains("battery") {
            return "battery.50"
        }
        if lower.contains("display") {
            return "display"
        }
        if lower.contains("brave") || lower.contains("safari") || lower.contains("chrome") || lower.contains("firefox") {
            return "globe"
        }
        if lower.contains("wake") || lower.contains("sleep") {
            return "moon.zzz"
        }
        if lower.contains("thermal") || lower.contains("temperature") {
            return "thermometer.medium"
        }
        if lower.contains("update") {
            return "arrow.triangle.2.circlepath"
        }
        if lower.contains("launch") || lower.contains("agent") {
            return "bolt.horizontal"
        }
        if lower.contains("xcode") || lower.contains("build") {
            return "hammer"
        }
        if lower.contains("docker") {
            return "shippingbox"
        }
        return "app.dashed"
    }
}

private struct PrimaryInfo {
    let name: String
    let detail: String
    let note: String
    let severity: Int
    let estimatedW: Double?
    let sharePct: Double?
    let icon: String

    var accessibility: String {
        var parts = [name, detail]
        if let estimatedW {
            parts.append("about \(String(format: "%.1f", estimatedW)) watts")
        }
        if !note.isEmpty {
            parts.append(note)
        }
        return parts.joined(separator: ", ")
    }
}
