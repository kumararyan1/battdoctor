import AppKit
import SwiftUI

struct PopoverView: View {
    @ObservedObject var model: BatteryModel

    var body: some View {
        Group {
            if let payload = model.payload {
                content(payload)
            } else {
                emptyState
            }
        }
        .frame(width: 380)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private func content(_ payload: MenubarPayload) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
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

    private func header(_ payload: MenubarPayload) -> some View {
        let battery = payload.snapshot.battery
        let percent = battery.percent ?? 0
        let health = battery.healthPercent ?? 0
        let cycles = battery.cycleCount ?? 0
        let temperature = battery.temperatureC

        return HStack(alignment: .center, spacing: 16) {
            ZStack {
                Circle()
                    .stroke(Color.secondary.opacity(0.15), lineWidth: 10)
                Circle()
                    .trim(from: 0, to: min(max(percent / 100, 0), 1))
                    .stroke(gaugeColor(percent), style: StrokeStyle(lineWidth: 10, lineCap: .round))
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
            Text("Primary suspects")
                .font(.headline)

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
                    .background(
                        RoundedRectangle(cornerRadius: 10)
                            .fill(Color(nsColor: .controlBackgroundColor))
                    )
                }
            }
        }
    }

    private func optimise(_ payload: MenubarPayload) -> some View {
        let actions = suggestions(payload)
        return VStack(alignment: .leading, spacing: 8) {
            Text("Optimise")
                .font(.headline)
            ForEach(Array(actions.prefix(4).enumerated()), id: \.offset) { _, action in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
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
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "battery.0")
                .font(.system(size: 36))
                .foregroundStyle(.secondary)
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
        }
        .padding(24)
        .frame(maxWidth: .infinity)
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
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color(nsColor: .controlBackgroundColor))
        )
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

    private func gaugeColor(_ percent: Double) -> Color {
        if percent <= 20 { return .red }
        if percent <= 50 { return .orange }
        return .green
    }

    private func pressureColor(_ pressure: String?) -> Color {
        switch pressure {
        case "critical": return .red
        case "warning": return .orange
        default: return .green
        }
    }

    private func severityColor(_ severity: Int) -> Color {
        if severity >= 9 { return .red }
        if severity >= 7 { return .orange }
        return .blue
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
