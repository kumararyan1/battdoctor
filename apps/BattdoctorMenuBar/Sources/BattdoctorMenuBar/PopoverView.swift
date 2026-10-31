import AppKit
import SwiftUI

struct PopoverView: View {
    @ObservedObject var model: BatteryModel
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        Group {
            if let payload = model.payload {
                content(payload)
            } else {
                emptyState
            }
        }
        .frame(width: 380)
        .background(background)
    }

    private var background: some View {
        ZStack(alignment: .topLeading) {
            Brand.canvas(scheme)
            RadialGradient(
                colors: [Brand.indigo.opacity(scheme == .dark ? 0.20 : 0.10), .clear],
                center: .topLeading,
                startRadius: 0,
                endRadius: 280
            )
        }
    }

    private func content(_ payload: MenubarPayload) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                brandHeader
                header(payload)
                metrics(payload)
                suspects(payload)
                optimise(payload)
                footer(payload)
            }
            .padding(20)
        }
        .frame(maxHeight: 560)
    }

    private var brandHeader: some View {
        HStack(spacing: 8) {
            ZStack {
                Circle()
                    .fill(Brand.accentGradient(scheme))
                    .frame(width: 20, height: 20)
                Image(systemName: "bolt.heart.fill")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(.white)
            }
            Text("battdoctor")
                .font(.system(.subheadline, design: .rounded).weight(.bold))
            Text("battery health")
                .font(.caption2)
                .foregroundStyle(.secondary)
            Spacer()
            Text("live")
                .font(.caption2.weight(.semibold))
                .padding(.horizontal, 7)
                .padding(.vertical, 2)
                .background(Capsule().fill(Brand.teal.opacity(0.14)))
                .foregroundStyle(Brand.teal)
        }
    }

    private func header(_ payload: MenubarPayload) -> some View {
        let battery = payload.snapshot.battery
        let percent = battery.percent ?? 0
        let health = battery.healthPercent ?? 0
        let cycles = battery.cycleCount ?? 0
        let temperature = battery.temperatureC

        return HStack(alignment: .center, spacing: 16) {
            ZStack {
                Circle()
                    .stroke(Color.secondary.opacity(0.14), lineWidth: 10)
                Circle()
                    .trim(from: 0, to: min(max(percent / 100, 0), 1))
                    .stroke(Brand.gaugeGradient(scheme), style: StrokeStyle(lineWidth: 10, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                VStack(spacing: 0) {
                    Text("\(Int(percent.rounded()))%")
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                    Text("battery")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(width: 86, height: 86)

            VStack(alignment: .leading, spacing: 5) {
                Text(statusText(battery))
                    .font(.headline)
                Text("\(Int(health.rounded()))% health · \(cycles) cycles")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text(deviceText(payload, temperature: temperature))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
    }

    private func metrics(_ payload: MenubarPayload) -> some View {
        let memory = payload.snapshot.memory
        let top = payload.snapshot.processes.max { ($0.cpuPct ?? 0) < ($1.cpuPct ?? 0) }

        return VStack(spacing: 10) {
            HStack(spacing: 10) {
                metric(
                    "Power",
                    value: payload.currentPowerW.map { String(format: "%.1f W", $0) } ?? "—",
                    detail: payload.snapshot.battery.externalConnected == true ? "on AC" : "on battery",
                    color: .primary
                )
                metric(
                    "Runtime",
                    value: formattedRuntime(payload.expectedRuntimeMin),
                    detail: "at current draw",
                    color: .primary
                )
            }
            HStack(spacing: 10) {
                metric(
                    "Memory",
                    value: (memory.pressure ?? "unknown").capitalized,
                    detail: "swap \(Int(memory.swapUsedMb ?? 0)) / \(Int(memory.swapTotalMb ?? 0)) MB",
                    color: pressureColor(memory.pressure)
                )
                metric(
                    "Top process",
                    value: top?.name ?? "—",
                    detail: top?.cpuPct.map { String(format: "%.1f%% CPU", $0) } ?? "no data",
                    color: .primary
                )
            }
        }
    }

    private func suspects(_ payload: MenubarPayload) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionTitle("Primary suspects")

            if payload.causes.isEmpty {
                Text("No strong signal found.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(payload.causes.prefix(3)) { cause in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: icon(for: cause))
                            .foregroundStyle(severityColor(cause.severity))
                            .frame(width: 16)
                        VStack(alignment: .leading, spacing: 3) {
                            HStack(spacing: 8) {
                                Text(cause.name)
                                    .font(.subheadline.weight(.semibold))
                                    .lineLimit(1)
                                Spacer(minLength: 4)
                                Text(cause.confidence)
                                    .font(.caption2.weight(.semibold))
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(
                                        Capsule()
                                            .fill(severityColor(cause.severity).opacity(0.12))
                                    )
                                    .foregroundStyle(severityColor(cause.severity))
                            }
                            Text(cause.evidence.first ?? "")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }
                    .padding(10)
                    .background(cardBackground)
                }
            }
        }
    }

    private func optimise(_ payload: MenubarPayload) -> some View {
        let actions = suggestions(payload)
        return VStack(alignment: .leading, spacing: 8) {
            sectionTitle("Optimise")
            ForEach(Array(actions.prefix(4).enumerated()), id: \.offset) { _, action in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(Brand.teal)
                        .font(.caption)
                    Text(action)
                        .font(.caption)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    private func footer(_ payload: MenubarPayload) -> some View {
        HStack(spacing: 12) {
            if let updated = model.lastUpdated {
                Text("Updated \(updated.formatted(date: .omitted, time: .shortened))")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                BattdoctorClient.copySummary(payload)
            } label: {
                Image(systemName: "doc.on.doc")
            }
            .help("Copy summary")
            Button {
                model.refresh()
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .help("Refresh")
            Button {
                NSApp.terminate(nil)
            } label: {
                Image(systemName: "power")
            }
            .help("Quit")
        }
        .buttonStyle(.borderless)
        .controlSize(.small)
        .tint(Brand.indigo)
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(Brand.accentGradient(scheme))
                    .frame(width: 46, height: 46)
                Image(systemName: "battery.0")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(.white)
            }
            Text(model.error ?? "Waiting for battdoctor...")
                .font(.callout)
                .multilineTextAlignment(.center)
            Text("Run `uv sync` in the battdoctor repo, then refresh.")
                .font(.caption)
                .foregroundStyle(.secondary)
            Button("Refresh") {
                model.refresh()
            }
            .buttonStyle(.borderedProminent)
            .tint(Brand.indigo)
        }
        .padding(24)
        .frame(maxWidth: .infinity)
    }

    private var cardBackground: some View {
        RoundedRectangle(cornerRadius: 10)
            .fill(Brand.card(scheme))
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Brand.cardStroke(scheme), lineWidth: 1)
            )
    }

    private func sectionTitle(_ text: String) -> some View {
        HStack(spacing: 6) {
            Circle()
                .fill(Brand.teal)
                .frame(width: 5, height: 5)
            Text(text)
                .font(.headline)
        }
    }

    @ViewBuilder
    private func metric(_ title: String, value: String, detail: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title.uppercased())
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(.title3, design: .rounded).weight(.semibold))
                .foregroundStyle(color)
                .lineLimit(1)
            Text(detail)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(cardBackground)
    }

    private func statusText(_ battery: BatteryInfo) -> String {
        if battery.charging == true {
            return "On AC · charging"
        }
        if battery.externalConnected == true {
            return battery.fullyCharged == true ? "On AC · fully charged" : "On AC"
        }
        return "On battery"
    }

    private func deviceText(_ payload: MenubarPayload, temperature: Double?) -> String {
        let chip = payload.snapshot.system.chip ?? payload.snapshot.system.model ?? "Mac"
        if let temperature {
            return "\(chip) · \(String(format: "%.1f", temperature))°C"
        }
        return chip
    }

    private func formattedRuntime(_ minutes: Double?) -> String {
        guard let minutes, minutes.isFinite, minutes > 0 else {
            return "—"
        }
        let total = Int(minutes.rounded())
        let hours = total / 60
        let mins = total % 60
        return hours > 0 ? "\(hours)h \(mins)m" : "\(mins)m"
    }

    private func pressureColor(_ pressure: String?) -> Color {
        switch pressure {
        case "critical": return Brand.coral
        case "warning": return Brand.amber
        default: return Brand.teal
        }
    }

    private func severityColor(_ severity: Int) -> Color {
        if severity >= 9 { return Brand.coral }
        if severity >= 7 { return Brand.amber }
        return Brand.indigo
    }

    private func icon(for cause: DrainCause) -> String {
        let name = cause.name.lowercased()
        if name.contains("memory") || name.contains("swap") { return "memorychip" }
        if name.contains("brave") || name.contains("app") { return "app.dashed" }
        if name.contains("display") { return "display" }
        if name.contains("battery") { return "battery.50" }
        if name.contains("wake") || name.contains("sleep") { return "moon.zzz" }
        if name.contains("thermal") { return "thermometer" }
        return "exclamationmark.triangle"
    }

    private func suggestions(_ payload: MenubarPayload) -> [String] {
        var seen = Set<String>()
        var actions: [String] = []
        for cause in payload.causes.prefix(3) where !cause.action.isEmpty {
            if seen.insert(cause.action).inserted {
                actions.append(cause.action)
            }
        }
        if payload.snapshot.battery.externalConnected == true {
            actions.append("Unplug to measure real battery runtime.")
        }
        if payload.snapshot.memory.pressure == "critical" {
            actions.append("Close tabs or restart the heaviest app to reduce swap.")
        }
        if actions.isEmpty {
            actions.append("No immediate action detected.")
        }
        return actions
    }
}
